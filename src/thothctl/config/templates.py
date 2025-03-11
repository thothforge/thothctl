# config/templates.py
"""
Template configurations and default values for different project types.
"""

from dataclasses import dataclass, field
from typing import Dict, Final, List


# Define constants for the template configurations
TERRAFORM_CONFIG: Final[Dict[str, List[str]]] = {
    "required_files": ["main.tf", "variables.tf", "outputs.tf"],
    "optional_files": ["README.md", "terraform.tfvars"],
}

TERRAGRUNT_CONFIG: Final[Dict[str, List[str]]] = {
    "required_files": ["terragrunt.hcl"],
    "optional_files": ["README.md"],
}


@dataclass(frozen=True)
class TemplateConfig:
    """Template configuration for different project types."""

    terraform: Dict[str, List[str]] = field(
        default_factory=lambda: dict(TERRAFORM_CONFIG)
    )

    terragrunt: Dict[str, List[str]] = field(
        default_factory=lambda: dict(TERRAGRUNT_CONFIG)
    )

    def __post_init__(self):
        """Validate the template configurations after initialization."""
        self._validate_config(self.terraform, "terraform")
        self._validate_config(self.terragrunt, "terragrunt")

    @staticmethod
    def _validate_config(config: Dict[str, List[str]], name: str) -> None:
        """
        Validate a template configuration.

        Args:
            config: The configuration to validate
            name: The name of the configuration (for error messages)

        Raises:
            ValueError: If the configuration is invalid
        """
        required_keys = {"required_files", "optional_files"}
        if not all(key in config for key in required_keys):
            missing = required_keys - set(config.keys())
            raise ValueError(f"{name} configuration missing required keys: {missing}")

        for key, value in config.items():
            if not isinstance(value, list):
                raise ValueError(f"{name} configuration {key} must be a list")
            if not all(isinstance(item, str) for item in value):
                raise ValueError(
                    f"All items in {name} configuration {key} must be strings"
                )
