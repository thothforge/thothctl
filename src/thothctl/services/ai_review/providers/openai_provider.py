"""OpenAI provider for AI review."""
import json
import logging
from typing import Dict, Any, Optional

from ..config.ai_settings import ProviderConfig

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI API integration for security analysis."""

    def __init__(self, config: ProviderConfig):
        self.model = config.model or "gpt-4-turbo-preview"
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self.api_key = config.api_key
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key) if self.api_key else OpenAI()
            except ImportError:
                raise ImportError("openai package required. Install with: pip install openai")
        return self._client

    def analyze(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        """Send analysis request to OpenAI and return parsed JSON response."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )
        usage = response.usage
        result = json.loads(response.choices[0].message.content)
        result["_usage"] = {
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
        }
        return result

    @property
    def name(self) -> str:
        return "openai"
