# config/__init__.py
"""Configuration management for the application."""

from typing import Any, Dict

import toml

from .defaults import ProjectDefaults
from .settings import Settings


class ConfigManager:
    """Manages application configuration."""

    def __init__(self):
        self.settings = Settings.from_env()
        self.defaults = ProjectDefaults()
        self._user_config = self._load_user_config()

    def _load_user_config(self) -> Dict[str, Any]:
        """Load user configuration from file."""
        if not self.settings.config_file.exists():
            return {}

        try:
            return toml.load(self.settings.config_file)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}

    def get_project_properties(self, project_name: str) -> Dict[str, str]:
        """Get project properties with user overrides."""
        user_props = self._user_config.get("projects", {}).get(project_name, {})
        return {**self.defaults.properties, **user_props}

    def get_catalog_tags(self) -> List[str]:
        """Get catalog tags with user additions."""
        user_tags = self._user_config.get("catalog_tags", [])
        return list(set(self.defaults.catalog_tags + user_tags))

    def get_catalog_spec(self) -> Dict[str, str]:
        """Get catalog specification with user overrides."""
        user_spec = self._user_config.get("catalog_spec", {})
        return {**self.defaults.catalog_spec, **user_spec}
