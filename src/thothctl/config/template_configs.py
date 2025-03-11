# config/template_configs.py
"""Default template configurations."""

from dataclasses import dataclass, field
from typing import Dict, Final, List

from .template_configs import CDK_CONFIG, TERRAFORM_CONFIG, TERRAGRUNT_CONFIG


# Terraform configuration
TERRAFORM_CONFIG: Final[Dict[str, List[str]]] = {
    "required_files": ["main.tf", "variables.tf", "outputs.tf"],
    "optional_files": ["README.md", "terraform.tfvars"],
}

# Terragrunt configuration
TERRAGRUNT_CONFIG: Final[Dict[str, List[str]]] = {
    "required_files": ["terragrunt.hcl"],
    "optional_files": ["README.md"],
}

# CDK configuration
CDK_CONFIG: Final[Dict[str, List[str]]] = {
    "required_files": ["app.py", "requirements.txt"],
    "optional_files": ["README.md", "cdk.json"],
}

# config/templates.py
"""
Template configurations and default values for different project types.
"""


@dataclass(frozen=True)
class TemplateConfig:
    """Template configuration for different project types."""

    terraform: Dict[str, List[str]] = field(
        default_factory=lambda: dict(TERRAFORM_CONFIG)
    )

    terragrunt: Dict[str, List[str]] = field(
        default_factory=lambda: dict(TERRAGRUNT_CONFIG)
    )

    cdk: Dict[str, List[str]] = field(default_factory=lambda: dict(CDK_CONFIG))

    def get_template_config(self, template_type: str) -> Dict[str, List[str]]:
        """
        Get configuration for a specific template type.

        Args:
            template_type: The type of template

        Returns:
            The template configuration

        Raises:
            ValueError: If template type is not supported
        """
        template_configs = {
            "terraform": self.terraform,
            "terragrunt": self.terragrunt,
            "cdk": self.cdk,
        }

        if template_type not in template_configs:
            raise ValueError(
                f"Unsupported template type: {template_type}. "
                f"Supported types: {list(template_configs.keys())}"
            )

        return template_configs[template_type]
