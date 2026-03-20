"""Ollama provider for AI review — uses local models via OpenAI-compatible API."""
import json
import logging
from typing import Dict, Any

from ..config.ai_settings import ProviderConfig

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "llama3"


class OllamaProvider:
    """Ollama local model integration via its OpenAI-compatible API."""

    def __init__(self, config: ProviderConfig):
        self.model = config.model or DEFAULT_OLLAMA_MODEL
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self.base_url = config.endpoint or DEFAULT_OLLAMA_BASE_URL
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    base_url=self.base_url,
                    api_key="ollama",  # Ollama doesn't need a real key
                )
            except ImportError:
                raise ImportError("openai package required. Install with: pip install openai")
        return self._client

    def analyze(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        """Send analysis request to Ollama and return parsed JSON response."""
        # Append explicit JSON instruction since not all Ollama models
        # support response_format=json_object reliably
        json_hint = "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation outside the JSON."
        messages = [
            {"role": "system", "content": system_prompt + json_hint},
            {"role": "user", "content": user_content},
        ]

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        # Try with response_format first; fall back if model doesn't support it
        try:
            kwargs["response_format"] = {"type": "json_object"}
            response = self.client.chat.completions.create(**kwargs)
        except Exception:
            kwargs.pop("response_format", None)
            response = self.client.chat.completions.create(**kwargs)

        text = response.choices[0].message.content
        usage = response.usage

        # Extract JSON from response if wrapped in markdown
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        result = json.loads(text)
        result["_usage"] = {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        }
        return result

    @property
    def name(self) -> str:
        return "ollama"
