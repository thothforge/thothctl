"""AWS Bedrock provider for AI review."""
import json
import logging
from typing import Dict, Any

from ..config.ai_settings import ProviderConfig

logger = logging.getLogger(__name__)


class BedrockProvider:
    """AWS Bedrock integration for security analysis."""

    def __init__(self, config: ProviderConfig):
        self.model = config.model or "anthropic.claude-3-sonnet-20240229-v1:0"
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self.region = config.region or "us-east-1"
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("bedrock-runtime", region_name=self.region)
            except ImportError:
                raise ImportError("boto3 package required. Install with: pip install boto3")
        return self._client

    def analyze(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        """Send analysis request to Bedrock and return parsed JSON response."""
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

        # Extract JSON from response (Claude may wrap it in markdown)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        result = json.loads(text)
        result["_usage"] = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        }
        return result

    @property
    def name(self) -> str:
        return "bedrock"
