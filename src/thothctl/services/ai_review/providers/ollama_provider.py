"""Ollama provider for AI review — uses local models via OpenAI-compatible API."""
import json
import logging
import os
import uuid
from typing import Dict, Any

from ..config.ai_settings import ProviderConfig
from ..tracing import span

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "llama3"

# Session ID for grouping related traces in Langfuse
_session_id = None


def get_session_id() -> str:
    """Get or create a session ID for this thothctl run."""
    global _session_id
    if _session_id is None:
        _session_id = f"thothctl-{uuid.uuid4().hex[:8]}"
    return _session_id


def reset_session():
    """Reset session for a new workflow run."""
    global _session_id
    _session_id = None


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
                # Use Langfuse-wrapped OpenAI client if configured
                import os
                if os.environ.get("LANGFUSE_PUBLIC_KEY"):
                    try:
                        from langfuse.openai import OpenAI
                        logger.info("Using Langfuse-instrumented OpenAI client")
                    except Exception:
                        from openai import OpenAI
                else:
                    from openai import OpenAI
                self._client = OpenAI(
                    base_url=self.base_url,
                    api_key="ollama",  # Ollama doesn't need a real key
                    timeout=1800.0,  # 30 min — large models on limited VRAM are very slow
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

            # Add Langfuse metadata if available
            if os.environ.get("LANGFUSE_PUBLIC_KEY"):
                kwargs["metadata"] = {
                    "session_id": get_session_id(),
                    "tags": ["thothctl", "ai-review"],
                }

            try:
                response = self.client.chat.completions.create(**kwargs)
                if not response.choices[0].message.content:
                    raise ValueError("Empty response")
            except Exception:
                kwargs.pop("metadata", None)
                response = self.client.chat.completions.create(**kwargs)

            text = response.choices[0].message.content or ""
            usage = response.usage

            if not text:
                raise ValueError("Empty response from model")

            # Try to extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            elif text.strip().startswith("{"):
                text = text.strip()
            else:
                # Model didn't return JSON — find any JSON block in the response
                import re
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
                if json_match:
                    text = json_match.group(0)
                else:
                    # No JSON at all — wrap the text response as a result
                    text = json.dumps({
                        "summary": {"total_findings": 0},
                        "findings": [],
                        "risk_score": 0,
                        "recommendations": [text[:500]],
                        "architecture_assessment": text[:1000],
                        "_raw_text": text[:2000],
                    })

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
