"""Intent decomposer for multi-stack IaC generation.

Calls the configured AI provider to break a natural language intent into
discrete infrastructure stacks organized by architectural layer, with
dependency information for correct deployment ordering.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .composition_models import LAYER_ORDER, CompositionPlan, StackPlan

logger = logging.getLogger(__name__)

DECOMPOSITION_SYSTEM_PROMPT = """\
You are an expert Infrastructure as Code architect. Your task is to decompose
a high-level infrastructure intent into discrete, deployable stacks organized
by architectural layers.

## Layer Model

Stacks MUST be assigned to one of these layers (in deployment order):

1. **foundation** — Networking, identity, DNS, base infrastructure.
   No dependencies on other layers.
2. **platform** — Shared services: databases, caches, message queues,
   container orchestration. Depends on foundation.
3. **application** — Workloads, functions, APIs, frontends.
   Depends on platform (and transitively on foundation).
4. **observability** — Monitoring, logging, alerting, dashboards.
   Depends on platform (and transitively on foundation).

## Rules

- Each stack should be a single logical unit (e.g., one VPC, one EKS cluster,
  one RDS instance).
- Use granular stacks rather than monolithic ones.
- `depends_on` lists the *stack names* (not layers) that must be deployed
  before this stack.
- Foundation stacks have empty `depends_on`.
- Suggest official Terraform registry modules when applicable (e.g.,
  "terraform-aws-modules/vpc/aws").
- The `domain` field categorizes the stack (e.g., networking, compute, data,
  security, container, serverless, storage, dns, identity, monitoring, logging).

## Output Format

Return ONLY valid JSON with this structure (no markdown fences, no explanation):

{{
  "stacks": [
    {{
      "name": "vpc",
      "layer": "foundation",
      "domain": "networking",
      "intent": "Create a VPC with public and private subnets across 3 AZs",
      "depends_on": [],
      "module_source": "terraform-aws-modules/vpc/aws"
    }}
  ],
  "project_type": "{project_type}",
  "needs_root_config": true,
  "needs_common": true
}}
"""

DECOMPOSITION_USER_PROMPT = """\
## Intent
{intent}

## Project Type
{project_type}

## Context
{context}

Decompose this intent into discrete infrastructure stacks following the
layer model. Return the JSON response only.
"""


class IntentDecomposer:
    """Decomposes a natural language intent into a multi-stack composition plan.

    Uses the same AI provider infrastructure as the CodeGenerator to call
    an LLM that breaks the intent into individual stacks with layer
    assignments and dependency information.
    """

    def __init__(self, provider: str = "ollama", model: str = None):
        """Initialize with an AI provider.

        Args:
            provider: Provider name (ollama, bedrock, openai, azure).
            model: Optional model override.
        """
        self.provider_name = provider
        self.model_name = model
        self._provider = None
        self._init_ai_provider(provider, model)

    def _init_ai_provider(self, provider_name: str, model: str = None) -> None:
        """Initialize the AI provider using the existing infrastructure.

        Reuses the same provider classes and settings as ai_review.
        """
        try:
            from ...ai_review.config.ai_settings import AISettings
            from ...ai_review.providers.azure_provider import (
                AzureOpenAIProvider,
            )
            from ...ai_review.providers.bedrock_provider import (
                BedrockProvider,
            )
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
            # Decomposition needs moderate token limit (JSON output)
            config.max_tokens = max(config.max_tokens, 4096)
            self._provider = cls(config)
            logger.info(
                "AI provider initialized for decomposition: "
                f"{provider_name} (model: {config.model})"
            )

        except Exception as e:
            logger.error(f"Failed to initialize AI provider '{provider_name}': {e}")
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decompose(
        self,
        intent: str,
        project_type: str,
        context: str,
    ) -> CompositionPlan:
        """Decompose an intent into a multi-stack composition plan.

        Args:
            intent: Natural language infrastructure description.
            project_type: Target IaC type (terraform, terragrunt, etc.).
            context: Compiled organizational context string.

        Returns:
            CompositionPlan with ordered stacks.

        Raises:
            RuntimeError: If decomposition fails after retry.
        """
        system_prompt = DECOMPOSITION_SYSTEM_PROMPT.format(
            project_type=project_type,
        )
        user_prompt = DECOMPOSITION_USER_PROMPT.format(
            intent=intent,
            project_type=project_type,
            context=context or "No additional context provided.",
        )

        logger.info(f"Decomposing intent: '{intent[:80]}...' (type={project_type})")

        try:
            raw_result = self._provider.analyze(system_prompt, user_prompt)
            plan = self._parse_response(raw_result, project_type)

            # Retry once if parsing produced empty plan
            if plan.stack_count == 0:
                logger.warning(
                    "First decomposition attempt returned no stacks — retrying"
                )
                raw_result = self._provider.analyze(system_prompt, user_prompt)
                plan = self._parse_response(raw_result, project_type)

            if plan.stack_count == 0:
                raise RuntimeError(
                    "AI returned no stacks after two attempts. "
                    "Raw response may be malformed."
                )

            # Validate and log any issues
            issues = plan.validate()
            if issues:
                for issue in issues:
                    logger.warning(f"Composition issue: {issue}")

            logger.info(
                f"Decomposition complete: {plan.stack_count} stacks "
                f"across layers: "
                + ", ".join(
                    f"{layer}={len(plan.get_stacks_by_layer(layer))}"
                    for layer in LAYER_ORDER
                    if plan.get_stacks_by_layer(layer)
                )
            )

            return plan

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Intent decomposition failed: {e}")
            raise RuntimeError(f"Failed to decompose intent: {e}") from e

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw_result: Any, project_type: str) -> CompositionPlan:
        """Parse AI provider response into a CompositionPlan.

        Uses the same multi-strategy JSON extraction as CodeGenerator.
        """
        # Provider may return dict or string depending on implementation
        if isinstance(raw_result, dict):
            # Check if already has 'stacks' key
            if "stacks" in raw_result:
                return self._build_plan(raw_result, project_type)

            # Check nested response patterns (varies by provider)
            for key in ("response", "content", "text", "message"):
                if key in raw_result and isinstance(raw_result[key], str):
                    extracted = self._extract_json(raw_result[key])
                    if extracted and "stacks" in extracted:
                        return self._build_plan(extracted, project_type)

            # Try raw key
            if "_raw" in raw_result:
                extracted = self._extract_json(str(raw_result["_raw"]))
                if extracted and "stacks" in extracted:
                    return self._build_plan(extracted, project_type)

        # String response — extract JSON
        if isinstance(raw_result, str):
            extracted = self._extract_json(raw_result)
            if extracted and "stacks" in extracted:
                return self._build_plan(extracted, project_type)

        logger.warning(
            "Could not parse decomposition response. "
            f"Raw (truncated): {str(raw_result)[:500]}"
        )
        return CompositionPlan(project_type=project_type)

    def _build_plan(self, data: Dict[str, Any], project_type: str) -> CompositionPlan:
        """Build a CompositionPlan from parsed JSON data."""
        stacks: List[StackPlan] = []

        for stack_data in data.get("stacks", []):
            if not isinstance(stack_data, dict):
                continue
            if "name" not in stack_data or "layer" not in stack_data:
                logger.debug(f"Skipping malformed stack entry: {stack_data}")
                continue

            stacks.append(
                StackPlan(
                    name=stack_data["name"],
                    layer=stack_data.get("layer", "foundation"),
                    domain=stack_data.get("domain", "general"),
                    intent=stack_data.get("intent", ""),
                    depends_on=stack_data.get("depends_on", []),
                    module_source=stack_data.get("module_source"),
                )
            )

        return CompositionPlan(
            stacks=stacks,
            project_type=data.get("project_type", project_type),
            needs_root_config=data.get("needs_root_config", True),
            needs_common=data.get("needs_common", True),
        )

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """Extract JSON from text that may contain markdown fences or prose.

        Tries multiple strategies (same as CodeGenerator._extract_json):
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
