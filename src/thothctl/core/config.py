# src/thothctl/core/config.py
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .logger import get_logger


logger = get_logger(__name__)


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._config_file: Optional[Path] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file"""
        config_file = Path.home() / ".thothctl" / "config.yaml"

        if config_file.exists():
            try:
                with config_file.open() as f:
                    self._config = yaml.safe_load(f)
                self._config_file = config_file
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                self._config = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self._config[key] = value
        self._save_config()

    def _save_config(self) -> None:
        """Save configuration to file"""
        if self._config_file:
            try:
                self._config_file.parent.mkdir(parents=True, exist_ok=True)
                with self._config_file.open("w") as f:
                    yaml.safe_dump(self._config, f)
            except Exception as e:
                logger.error(f"Error saving config: {e}")
