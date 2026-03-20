"""AWS Bedrock Agent provider using bedrock-agent-runtime APIs.

Supports two modes:
- Inline agent: ephemeral, no pre-created agent needed (CI/CD, dev)
- Persistent agent: pre-created agent with ID + alias (production)
"""
import json
import logging
import uuid
from typing import Dict, Any

from ..config.ai_settings import ProviderConfig

logger = logging.getLogger(__name__)


class BedrockAgentProvider:
    """Bedrock Agent Runtime integration (InvokeInlineAgent / InvokeAgent)."""

    def __init__(self, config: ProviderConfig):
        self.model = config.model or "anthropic.claude-sonnet-4-20250514"
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self.region = config.region or "us-east-1"
        self.agent_id = config.agent_id or ""
        self.agent_alias_id = config.agent_alias_id or ""
        self._session_id = uuid.uuid4().hex[:12]
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("bedrock-agent-runtime", region_name=self.region)
            except ImportError:
                raise ImportError("boto3 required. Install with: pip install boto3")
        return self._client

    @property
    def is_persistent(self) -> bool:
        return bool(self.agent_id)

    def analyze(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        """Send analysis request via agent runtime and return parsed JSON."""
        if self.is_persistent:
            text = self._invoke_persistent(system_prompt, user_content)
        else:
            text = self._invoke_inline(system_prompt, user_content)

        return self._parse_response(text)

    def _invoke_inline(self, instruction: str, input_text: str) -> str:
        """Invoke ephemeral inline agent — no pre-created agent needed."""
        params = {
            "sessionId": self._session_id,
            "foundationModel": self.model,
            "instruction": instruction,
            "inputText": input_text,
            "enableTrace": False,
            "endSession": False,
        }

        response = self.client.invoke_inline_agent(**params)
        return self._read_event_stream(response.get("completion", []))

    def _invoke_persistent(self, system_prompt: str, input_text: str) -> str:
        """Invoke a pre-created Bedrock Agent by ID + alias."""
        # Prepend system context to input since persistent agents have fixed instructions
        combined = f"[Context: {system_prompt}]\n\n{input_text}"

        params = {
            "agentId": self.agent_id,
            "agentAliasId": self.agent_alias_id or "TSTALIASID",
            "sessionId": self._session_id,
            "inputText": combined,
            "enableTrace": False,
            "endSession": False,
        }

        response = self.client.invoke_agent(**params)
        return self._read_event_stream(response.get("completion", []))

    @staticmethod
    def _read_event_stream(event_stream) -> str:
        """Read all chunks from the agent event stream."""
        parts = []
        for event in event_stream:
            chunk = event.get("chunk", {})
            if "bytes" in chunk:
                parts.append(chunk["bytes"].decode("utf-8"))
        return "".join(parts)

    def _parse_response(self, text: str) -> Dict[str, Any]:
        """Extract JSON from agent response text."""
        # Agent responses may wrap JSON in markdown
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Agent response is not valid JSON, wrapping as text")
            result = {
                "summary": {"total_findings": 0},
                "findings": [],
                "risk_score": 0,
                "recommendations": [text[:2000]],
            }

        # Agent runtime doesn't expose token counts directly
        result.setdefault("_usage", {"input_tokens": 0, "output_tokens": 0})
        return result

    def new_session(self) -> str:
        """Start a new session (new conversation)."""
        self._session_id = uuid.uuid4().hex[:12]
        return self._session_id

    @property
    def name(self) -> str:
        return "bedrock_agent"
