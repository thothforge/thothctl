"""Kiro CLI provider for AI operations — uses Kiro headless mode as an AI agent.

Kiro CLI in headless mode (--no-interactive) acts as a full AI agent with tool access:
- Reads project structure and existing code
- Searches documentation (Terraform, AWS, CDK)
- Self-corrects using built-in validation
- Manages its own context window and compaction

This makes it a more capable provider than raw LLM API calls for complex
IaC generation tasks, at the cost of higher latency.

Usage:
    thothctl generate iac --intent "Create a VPC..." --provider kiro
"""

import json
import logging
import os
import re
import shutil
import subprocess
from typing import Any, Dict, Optional

from ..config.ai_settings import ProviderConfig
from ..tracing import span

logger = logging.getLogger(__name__)

# Environment variable used to detect recursive invocation
RECURSION_GUARD_ENV = "THOTHCTL_KIRO_PROVIDER_ACTIVE"

# Default timeout for Kiro headless execution (5 minutes)
DEFAULT_TIMEOUT = 300

# Default agent to use (can be overridden via config.model)
DEFAULT_AGENT = "kiro_default"


class KiroProvider:
    """Uses Kiro CLI in headless mode as an AI provider.

    Kiro headless mode provides:
    - Full tool access (file read/write, grep, shell, web search)
    - AWS documentation search
    - Terraform/CDK/CloudFormation doc lookup
    - Built-in context management and compaction
    - Self-correction capabilities

    The tradeoff is higher latency (10-30s vs 2-5s for direct API calls)
    but significantly richer context and tool-augmented generation.
    """

    def __init__(self, config: ProviderConfig):
        """Initialize the Kiro provider.

        Args:
            config: Provider configuration. Fields used:
                - model: Agent name to use (default: kiro_default)
                - endpoint: Path to kiro-cli binary (default: auto-detect)
                - max_tokens: Unused (Kiro manages its own context)
                - temperature: Unused (Kiro uses server-side defaults)
        """
        self.agent = config.model or DEFAULT_AGENT
        self.timeout = DEFAULT_TIMEOUT
        self.kiro_binary = config.endpoint or self._find_kiro_binary()

        if not self.kiro_binary:
            raise RuntimeError(
                "kiro-cli not found. Install Kiro CLI or specify path via "
                "provider endpoint config. "
                "See: https://kiro.dev/docs/installation"
            )

        # Check for recursive invocation
        if os.environ.get(RECURSION_GUARD_ENV):
            raise RuntimeError(
                "Recursive invocation detected: thothctl is being called from within "
                "a Kiro session that was started by thothctl. This would create an "
                "infinite loop. Use a different provider (ollama, bedrock, openai) "
                "when thothctl is invoked as an MCP tool from Kiro."
            )

    @staticmethod
    def _find_kiro_binary() -> Optional[str]:
        """Find kiro-cli binary in PATH."""
        return shutil.which("kiro-cli")

    @staticmethod
    def is_available() -> bool:
        """Check if Kiro CLI is available on this system."""
        return shutil.which("kiro-cli") is not None

    def analyze(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        """Send prompt to Kiro headless mode and parse JSON response.

        Args:
            system_prompt: System instructions (role, output format).
            user_content: The actual request content.

        Returns:
            Parsed JSON response from Kiro, with _usage metadata.

        Raises:
            RuntimeError: If Kiro execution fails or times out.
            ValueError: If response cannot be parsed as JSON.
        """
        with span("provider.kiro.analyze", {"agent": self.agent}) as s:
            # Build the combined prompt with explicit JSON output instruction
            prompt = self._build_prompt(system_prompt, user_content)

            # Execute Kiro in headless mode
            text = self._execute_headless(prompt)

            if not text:
                raise ValueError("Empty response from Kiro CLI")

            # Extract JSON from Kiro's output (which may include tool-use artifacts)
            result = self._extract_json(text)

            # Ensure result is a dict (arrays are wrapped by _extract_json,
            # but Strategy 1 may return a raw list if the entire text is a JSON array)
            if isinstance(result, list):
                result = {"files": result, "_raw_array": True}

            # Add usage metadata (estimated — Kiro doesn't expose token counts)
            result["_usage"] = {
                "input_tokens": len(prompt) // 4,  # rough estimate
                "output_tokens": len(text) // 4,
            }
            s.set_attribute("tokens.input", result["_usage"]["input_tokens"])
            s.set_attribute("tokens.output", result["_usage"]["output_tokens"])
            s.set_attribute("response_length", len(text))

            return result

    def _build_prompt(self, system_prompt: str, user_content: str) -> str:
        """Combine system and user prompts for headless mode.

        In headless mode, there's no separate system message — we combine
        them into a single prompt with clear delineation.
        """
        json_hint = (
            "\n\nCRITICAL: Your final output MUST be ONLY valid JSON. "
            "No markdown fences, no explanation outside the JSON object. "
            "Start your response with { and end with }."
        )
        return f"{system_prompt}{json_hint}\n\n---\n\n{user_content}"

    def _execute_headless(self, prompt: str) -> str:
        """Execute kiro-cli in headless mode with the given prompt.

        Sets THOTHCTL_KIRO_PROVIDER_ACTIVE env var to prevent recursive
        invocation if Kiro tries to call thothctl MCP tools.

        Args:
            prompt: The full prompt to send.

        Returns:
            Kiro's stdout output.

        Raises:
            RuntimeError: On execution failure or timeout.
        """
        cmd = [
            self.kiro_binary,
            "chat",
            "--no-interactive",
            "--trust-all-tools",
        ]

        # Use specific agent if not default
        if self.agent and self.agent != "kiro_default":
            cmd.extend(["--agent", self.agent])

        # Append the prompt as positional argument
        cmd.append(prompt)

        # Set recursion guard in child environment
        env = os.environ.copy()
        env[RECURSION_GUARD_ENV] = "1"

        logger.info(
            f"Executing Kiro headless: agent={self.agent}, "
            f"prompt_length={len(prompt)}, timeout={self.timeout}s"
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                cwd=os.getcwd(),
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                # Log stderr for debugging but don't fail if stdout has content
                if stderr:
                    logger.warning(f"Kiro stderr: {stderr[:500]}")

                if not result.stdout.strip():
                    raise RuntimeError(
                        f"Kiro CLI failed (exit {result.returncode}): "
                        f"{stderr[:300] or 'no output'}"
                    )

            output = result.stdout.strip()
            logger.debug(f"Kiro response length: {len(output)} chars")
            return output

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Kiro CLI timed out after {self.timeout}s. "
                f"The generation task may be too complex for headless mode. "
                f"Try a simpler intent or use --provider ollama/bedrock."
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Kiro CLI binary not found at: {self.kiro_binary}. "
                f"Ensure kiro-cli is installed and in PATH."
            )

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from Kiro's output, handling mixed content.

        Kiro headless output may include:
        - Tool use artifacts (file reads, searches)
        - Progress messages
        - The actual JSON response

        We try multiple strategies to find valid JSON.

        Args:
            text: Raw output from Kiro CLI.

        Returns:
            Parsed JSON dictionary.

        Raises:
            ValueError: If no valid JSON can be extracted.
        """
        # Strategy 1: Try the entire text as JSON
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: Look for JSON in markdown code blocks
        json_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)```"
        blocks = re.findall(json_block_pattern, text)
        for block in reversed(blocks):  # Last block is most likely the answer
            try:
                return json.loads(block.strip())
            except (json.JSONDecodeError, ValueError):
                continue

        # Strategy 3: Find the largest valid JSON object in the text
        # Scan for all top-level { positions and try each, preferring the largest
        brace_positions = [m.start() for m in re.finditer(r"\{", text)]
        valid_objects = []
        for start_pos in brace_positions:
            depth = 0
            in_string = False
            escape_next = False
            for i in range(start_pos, len(text)):
                ch = text[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\":
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start_pos : i + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict):
                                valid_objects.append(parsed)
                        except (json.JSONDecodeError, ValueError):
                            pass
                        break

        if valid_objects:
            # Prefer the largest (most keys) valid JSON object
            return max(valid_objects, key=lambda obj: len(json.dumps(obj)))

        # Strategy 4: Try to find JSON array (for file generation output)
        bracket_positions = [m.start() for m in re.finditer(r"\[", text)]
        for start_pos in reversed(bracket_positions):
            depth = 0
            in_string = False
            escape_next = False
            for i in range(start_pos, len(text)):
                ch = text[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\":
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start_pos : i + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, list):
                                # Wrap array in object for consistent interface
                                return {"files": parsed, "_raw_array": True}
                        except (json.JSONDecodeError, ValueError):
                            pass
                        break

        # Strategy 5: Wrap raw text as a structured response
        logger.warning(
            "Could not extract JSON from Kiro output. "
            "Wrapping raw text as structured response."
        )
        return {
            "summary": {"total_findings": 0},
            "findings": [],
            "risk_score": 0,
            "recommendations": [],
            "architecture_assessment": "",
            "_raw_text": text[:4000],
            "_parse_failed": True,
        }

    @property
    def name(self) -> str:
        """Provider name for logging and config."""
        return "kiro"
