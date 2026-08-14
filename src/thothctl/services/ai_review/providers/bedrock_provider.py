"""AWS Bedrock provider for AI review."""

import json
import logging
from typing import Any, Dict

from ..config.ai_settings import ProviderConfig
from ..tracing import span

logger = logging.getLogger(__name__)


class BedrockProvider:
    """AWS Bedrock integration for security analysis."""

    def __init__(self, config: ProviderConfig):
        self.model = config.model or "anthropic.claude-sonnet-4-6"
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self.region = config.region or "us-east-1"
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config

                # IaC generation responses can be large; increase read timeout
                config = Config(
                    read_timeout=300,
                    connect_timeout=10,
                    retries={"max_attempts": 2},
                )
                self._client = boto3.client(
                    "bedrock-runtime", region_name=self.region, config=config
                )
            except ImportError:
                raise ImportError(
                    "boto3 package required. Install with: pip install boto3"
                )
        return self._client

    def analyze(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        """Send analysis request to Bedrock and return parsed JSON response."""
        with span(
            "provider.bedrock.analyze", {"model": self.model, "region": self.region}
        ) as s:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_content}],
            }

            response = self.client.invoke_model(
                modelId=self.model,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())
            text = response_body["content"][0]["text"]
            usage = response_body.get("usage", {})

            # Extract JSON from LLM response (may have markdown fences)
            json_text = text
            if "```json" in text:
                json_text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                json_text = text.split("```")[1].split("```")[0].strip()

            # Try parsing the extracted JSON
            try:
                result = json.loads(json_text)
            except (json.JSONDecodeError, TypeError):
                # LLM returned malformed JSON (common: unescaped newlines in HCL)
                # Try repairing unescaped newlines/tabs inside string values
                repaired = self._repair_json_strings(json_text)
                try:
                    result = json.loads(repaired)
                except (json.JSONDecodeError, TypeError):
                    # Still can't parse — return raw text for downstream handling
                    logger.debug(
                        f"Bedrock response not valid JSON, returning raw text "
                        f"({len(text)} chars)"
                    )
                    return {"response": text, "_raw": text}

            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            result["_usage"] = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
            s.set_attribute("tokens.input", input_tokens)
            s.set_attribute("tokens.output", output_tokens)
            return result

    @staticmethod
    def _repair_json_strings(text: str) -> str:
        """Repair unescaped newlines/tabs in LLM-generated JSON strings.

        LLMs frequently generate JSON with literal newlines inside string
        values (especially when the string contains HCL/Terraform code).
        This method escapes them properly.
        """
        result = []
        in_string = False
        escape_next = False

        for c in text:
            if escape_next:
                result.append(c)
                escape_next = False
                continue
            if c == "\\" and in_string:
                escape_next = True
                result.append(c)
                continue
            if c == '"':
                in_string = not in_string
                result.append(c)
                continue
            if in_string:
                if c == "\n":
                    result.append("\\n")
                elif c == "\r":
                    result.append("\\r")
                elif c == "\t":
                    result.append("\\t")
                else:
                    result.append(c)
            else:
                result.append(c)

        import re

        repaired = "".join(result)
        # Fix trailing commas (another common LLM issue)
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        return repaired

    @property
    def name(self) -> str:
        return "bedrock"
