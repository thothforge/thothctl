"""Code generator for Intent-to-IaC.

Calls the configured AI provider with the generation/fix prompt and parses
the JSON response into GeneratedFile objects. Handles malformed responses
with regex JSON extraction (same pattern as ai_review).
"""

import json
import logging
import re
from typing import Any, Dict, Optional

from .models import GeneratedFile, GenerationOutput, ValidationResult
from .prompts import build_fix_prompt, build_generation_prompt, format_previous_files

logger = logging.getLogger(__name__)


class CodeGenerator:
    """Generates IaC code by calling an AI provider."""

    def __init__(self, provider: str = "ollama", model: str = None):
        """Initialize with an AI provider.

        Args:
            provider: Provider name (ollama, bedrock, openai, azure)
            model: Optional model override
        """
        self.provider_name = provider
        self.model_name = model
        self._provider = None
        self._init_ai_provider(provider, model)

    def _init_ai_provider(self, provider_name: str, model: str = None) -> None:
        """Initialize the AI provider using the existing infrastructure."""
        try:
            from ...ai_review.config.ai_settings import AISettings
            from ...ai_review.providers.azure_provider import AzureOpenAIProvider
            from ...ai_review.providers.bedrock_provider import BedrockProvider
            from ...ai_review.providers.ollama_provider import OllamaProvider
            from ...ai_review.providers.openai_provider import OpenAIProvider

            settings = AISettings.load()
            providers = {
                "ollama": OllamaProvider,
                "openai": OpenAIProvider,
                "bedrock": BedrockProvider,
                "azure": AzureOpenAIProvider,
            }

            cls = providers.get(provider_name)
            if not cls:
                raise ValueError(
                    f"Unknown provider: {provider_name}. "
                    f"Available: {', '.join(providers.keys())}"
                )

            config = settings.get_provider_config(provider_name)
            if model:
                config.model = model
            # IaC generation needs higher token limit than review (full modules)
            config.max_tokens = max(config.max_tokens, 16000)
            self._provider = cls(config)
            logger.info(
                f"AI provider initialized: {provider_name} (model: {config.model})"
            )

        except Exception as e:
            logger.error(f"Failed to initialize AI provider '{provider_name}': {e}")
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self, intent: str, context: str, project_type: str
    ) -> GenerationOutput:
        """Generate IaC code from natural language intent.

        Args:
            intent: Natural language description of desired infrastructure
            context: Compiled organizational context (from ContextBuilder)
            project_type: Target project type (terraform, terraform-terragrunt, etc.)

        Returns:
            GenerationOutput with generated files and metadata
        """
        system_prompt = build_generation_prompt(project_type, context)

        logger.info(f"Generating IaC: intent='{intent[:80]}...', type={project_type}")
        logger.debug(f"System prompt length: {len(system_prompt)} chars")

        try:
            raw_result = self._provider.analyze(system_prompt, intent)
            output = self._parse_response(raw_result)

            # Retry once if parsing failed (model sometimes returns malformed JSON)
            if not output.files and output.raw_response:
                logger.warning("First attempt returned no files — retrying generation")
                raw_result = self._provider.analyze(system_prompt, intent)
                output = self._parse_response(raw_result)

            return output
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return GenerationOutput(
                explanation=f"Generation failed: {str(e)}",
                raw_response=str(e),
            )

    def fix(
        self,
        previous_output: GenerationOutput,
        validation: ValidationResult,
        context: str,
    ) -> GenerationOutput:
        """Re-generate code with violation fixes (self-correction).

        Args:
            previous_output: The previously generated code
            validation: Validation result with violations to fix
            context: Organizational context (same as generation)

        Returns:
            GenerationOutput with corrected files
        """
        violations_text = validation.format_for_ai()
        previous_files_text = format_previous_files(previous_output.files)

        system_prompt = build_fix_prompt(
            context=context,
            violations=violations_text,
            previous_files=previous_files_text,
        )

        user_content = (
            f"Fix all {validation.total_violations} violation(s) listed above. "
            f"Critical: {validation.critical_count}, High: {validation.high_count}. "
            f"Return the corrected files in JSON format."
        )

        logger.info(
            f"Self-correcting: {validation.total_violations} violations "
            f"({validation.critical_count} critical, {validation.high_count} high)"
        )

        try:
            raw_result = self._provider.analyze(system_prompt, user_content)
            return self._parse_response(raw_result)
        except Exception as e:
            logger.error(f"AI fix generation failed: {e}")
            # Return original output on fix failure
            return previous_output

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw_result: Dict[str, Any]) -> GenerationOutput:
        """Parse AI provider response into GenerationOutput.

        The AI response may be:
        1. A dict with the expected structure (ideal)
        2. A dict with a nested 'response' or 'content' key containing JSON string
        3. A string containing JSON (needs extraction)
        """
        # If provider returned parsed dict directly
        if isinstance(raw_result, dict):
            # Check if it already has 'files' key
            if "files" in raw_result:
                return self._build_output(raw_result)

            # Check nested response patterns (varies by provider)
            for key in ("response", "content", "text", "message"):
                if key in raw_result and isinstance(raw_result[key], str):
                    extracted = self._extract_json(raw_result[key])
                    if extracted and "files" in extracted:
                        return self._build_output(extracted)

            # Some providers return the full response as the dict
            # Try to find files in any nested structure
            if "_raw" in raw_result:
                extracted = self._extract_json(str(raw_result["_raw"]))
                if extracted and "files" in extracted:
                    return self._build_output(extracted)

        # Last resort: try to extract JSON from string representation
        if isinstance(raw_result, str):
            extracted = self._extract_json(raw_result)
            if extracted and "files" in extracted:
                return self._build_output(extracted)

        # Complete failure — return empty with raw response for debugging
        logger.warning("Could not parse AI response into files")
        return GenerationOutput(
            explanation="Failed to parse AI response. Raw response saved for debugging.",
            raw_response=str(raw_result)[:2000],
        )

    def _build_output(self, data: Dict[str, Any]) -> GenerationOutput:
        """Build GenerationOutput from a parsed dict."""
        files = []
        for file_data in data.get("files", []):
            if (
                isinstance(file_data, dict)
                and "path" in file_data
                and "content" in file_data
            ):
                files.append(
                    GeneratedFile(
                        path=file_data["path"],
                        content=file_data["content"],
                    )
                )

        if not files:
            logger.warning("AI returned JSON but no valid files found")

        return GenerationOutput(
            files=files,
            explanation=data.get("explanation", ""),
            modules_used=data.get("modules_used", []),
            estimated_resources=data.get("estimated_resources", []),
            raw_response=None,
        )

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """Extract JSON from text that may contain markdown fences or extra content.

        Tries multiple strategies:
        1. Direct JSON parse
        2. Extract from ```json ... ``` fences
        3. Find first { ... } block via brace matching
        """
        if not text or not text.strip():
            return None

        text = text.strip()

        # Strategy 1: Direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # Strategy 2: Extract from markdown code fences
        fence_patterns = [
            r"```json\s*\n?(.*?)\n?\s*```",
            r"```\s*\n?(.*?)\n?\s*```",
        ]
        for pattern in fence_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except (json.JSONDecodeError, TypeError):
                    continue

        # Strategy 3: Find the outermost JSON object via brace matching
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        end = start
        in_string = False
        escape_next = False

        for i in range(start, len(text)):
            c = text[i]
            if escape_next:
                escape_next = False
                continue
            if c == "\\":
                escape_next = True
                continue
            if c == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if depth == 0 and end > start:
            try:
                return json.loads(text[start:end])
            except (json.JSONDecodeError, TypeError):
                pass

        return None
