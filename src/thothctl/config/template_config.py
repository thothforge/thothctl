"""Configuration for template repositories."""
import os
import toml
from pathlib import Path
from typing import Dict, Optional


class TemplateConfig:
    """Manage template repository configuration."""
    
    DEFAULT_CONFIG_FILE = ".thothctl_templates.toml"
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or self.DEFAULT_CONFIG_FILE
        self.config_path = Path.home() / ".thothcf" / self.config_file
        self._config = None
    
    def get_template_url(self, project_type: str) -> Optional[str]:
        """
        Get template URL for a project type.
        
        :param project_type: Type of project
        :return: Template URL or None if not found
        """
        config = self._load_config()
        return config.get("templates", {}).get(project_type)
    
    def set_template_url(self, project_type: str, template_url: str) -> None:
        """
        Set template URL for a project type.
        
        :param project_type: Type of project
        :param template_url: GitHub repository URL
        """
        config = self._load_config()
        if "templates" not in config:
            config["templates"] = {}
        
        config["templates"][project_type] = template_url
        self._save_config(config)
    
    def _load_config(self) -> Dict:
        """Load configuration from file."""
        if self._config is not None:
            return self._config
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = toml.load(f)
            except Exception:
                self._config = {}
        else:
            self._config = {}
        
        return self._config
    
    def _save_config(self, config: Dict) -> None:
        """Save configuration to file."""
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            toml.dump(config, f)
        
        self._config = config
