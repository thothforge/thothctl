"""AI Review configuration and settings management."""
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any

import yaml


logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = ".thothctl"
DEFAULT_CONFIG_FILE = "ai_config.yaml"


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""
    model: str = ""
    max_tokens: int = 4000
    temperature: float = 0.1
    api_key: str = ""
    region: str = "us-east-1"
    agent_id: str = ""
    agent_alias_id: str = ""
    endpoint: str = ""


@dataclass
class CostControlConfig:
    """Cost control settings."""
    daily_limit: int = 100
    monthly_budget: float = 200.0
    auto_fallback: bool = True


@dataclass
class AnalysisConfig:
    """Analysis behavior settings."""
    risk_threshold: str = "medium"
    auto_comment_prs: bool = False
    include_remediation: bool = True


@dataclass
class AISettings:
    """Main AI settings container."""
    default_provider: str = "openai"
    providers: Dict[str, ProviderConfig] = field(default_factory=lambda: {
        "openai": ProviderConfig(model="gpt-4-turbo-preview"),
        "bedrock": ProviderConfig(model="anthropic.claude-3-sonnet-20240229-v1:0"),
        "bedrock_agent": ProviderConfig(model="anthropic.claude-sonnet-4-20250514"),
        "azure": ProviderConfig(model="gpt-4"),
        "ollama": ProviderConfig(model="llama3", endpoint="http://localhost:11434/v1"),
    })
    cost_controls: CostControlConfig = field(default_factory=CostControlConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "AISettings":
        """Load settings from YAML config file, env vars, or defaults."""
        settings = cls()

        # Try loading from file
        path = Path(config_path) if config_path else Path(DEFAULT_CONFIG_DIR) / DEFAULT_CONFIG_FILE
        if path.exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                ai_data = data.get("ai_review", data)
                settings.default_provider = ai_data.get("default_provider", settings.default_provider)

                for name, pconf in ai_data.get("providers", {}).items():
                    settings.providers[name] = ProviderConfig(**pconf)

                cc = ai_data.get("cost_controls", {})
                if cc:
                    settings.cost_controls = CostControlConfig(**cc)

                ac = ai_data.get("analysis", {})
                if ac:
                    settings.analysis = AnalysisConfig(**ac)
            except Exception as e:
                logger.warning(f"Error loading AI config from {path}: {e}")

        # Environment variable overrides
        settings.default_provider = os.environ.get("THOTH_AI_PROVIDER", settings.default_provider)
        if os.environ.get("THOTH_AI_DAILY_LIMIT"):
            settings.cost_controls.daily_limit = int(os.environ["THOTH_AI_DAILY_LIMIT"])

        # Provider-specific env vars
        if os.environ.get("OPENAI_API_KEY"):
            settings.providers.setdefault("openai", ProviderConfig(model="gpt-4-turbo-preview"))
            settings.providers["openai"].api_key = os.environ["OPENAI_API_KEY"]

        if os.environ.get("AWS_DEFAULT_REGION"):
            settings.providers.setdefault("bedrock", ProviderConfig())
            settings.providers["bedrock"].region = os.environ["AWS_DEFAULT_REGION"]
            settings.providers.setdefault("bedrock_agent", ProviderConfig())
            settings.providers["bedrock_agent"].region = os.environ["AWS_DEFAULT_REGION"]

        if os.environ.get("THOTH_BEDROCK_AGENT_ID"):
            ba = settings.providers.setdefault("bedrock_agent", ProviderConfig())
            ba.agent_id = os.environ["THOTH_BEDROCK_AGENT_ID"]
        if os.environ.get("THOTH_BEDROCK_AGENT_ALIAS_ID"):
            ba = settings.providers.setdefault("bedrock_agent", ProviderConfig())
            ba.agent_alias_id = os.environ["THOTH_BEDROCK_AGENT_ALIAS_ID"]

        if os.environ.get("OLLAMA_HOST"):
            host = os.environ["OLLAMA_HOST"].rstrip("/")
            if not host.endswith("/v1"):
                host += "/v1"
            settings.providers.setdefault("ollama", ProviderConfig(model="llama3"))
            settings.providers["ollama"].endpoint = host

        return settings

    def save(self, config_path: Optional[str] = None) -> None:
        """Save current settings to YAML config file."""
        path = Path(config_path) if config_path else Path(DEFAULT_CONFIG_DIR) / DEFAULT_CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "ai_review": {
                "default_provider": self.default_provider,
                "providers": {
                    name: {k: v for k, v in vars(pc).items() if v}
                    for name, pc in self.providers.items()
                },
                "cost_controls": vars(self.cost_controls),
                "analysis": vars(self.analysis),
            }
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        logger.info(f"AI config saved to {path}")

    def get_provider_config(self, provider_name: Optional[str] = None) -> ProviderConfig:
        """Get config for a specific provider or the default."""
        name = provider_name or self.default_provider
        if name not in self.providers:
            raise ValueError(f"Unknown AI provider: {name}. Available: {list(self.providers.keys())}")
        return self.providers[name]
