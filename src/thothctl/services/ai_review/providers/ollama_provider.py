"""Ollama provider for AI review — uses local models via OpenAI-compatible API."""
import json
import logging
from typing import Dict, Any

from ..config.ai_settings import ProviderConfig
from ..tracing import span

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
        with span("provider.ollama.analyze", {"model": self.model}) as s:
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

            try:
                kwargs["response_format"] = {"type": "json_object"}
                response = self.client.chat.completions.create(**kwargs)
            except Exception:
                kwargs.pop("response_format", None)
                response = self.client.chat.completions.create(**kwargs)

            text = response.choices[0].message.content
            usage = response.usage

            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)
            input_tokens = getattr(usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage, "completion_tokens", 0) or 0
            result["_usage"] = {"input_tokens": input_tokens, "output_tokens": output_tokens}
            s.set_attribute("tokens.input", input_tokens)
            s.set_attribute("tokens.output", output_tokens)
            return result

    @property
    def name(self) -> str:
        return "ollama"
