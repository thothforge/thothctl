# config/settings.py
"""
Application settings that can be overridden by environment variables.
"""

from dataclasses import dataclass
from pathlib import Path

import os


@dataclass
class Settings:
    """Application settings."""

    config_dir: Path = Path.home() / ".thoth"
    config_file: Path = config_dir / "thothcf.toml"
    log_level: str = os.getenv("THOTH_LOG_LEVEL", "INFO")

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        return cls(
            config_dir=Path(os.getenv("THOTH_CONFIG_DIR", str(cls.config_dir))),
            config_file=Path(os.getenv("THOTH_CONFIG_FILE", str(cls.config_file))),
            log_level=os.getenv("THOTH_LOG_LEVEL", cls.log_level),
        )
