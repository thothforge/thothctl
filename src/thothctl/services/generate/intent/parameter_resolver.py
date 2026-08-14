"""Parameter resolver for Intent-to-IaC project mode.

Resolves #{...}# placeholders in scaffold templates to concrete values.

Value sources (priority order):
1. Intent-derived: extracted from natural language (e.g., "in us-east-1" → region)
2. Space config: loaded from ~/.thothcf/spaces/<name>/orchestration/terragrunt.toml
3. CLI/environment: explicit overrides
4. Scaffold defaults: template_value from .thothcf.toml [template_input_parameters]
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Regex patterns for extracting values from natural language intent
_REGION_PATTERNS = [
    r"(?:in|region|deploy(?:ed)?\s+(?:to|in))\s+(us-east-[12]|us-west-[12]|eu-west-[123]|eu-central-1|ap-southeast-[12]|ap-northeast-[123]|sa-east-1|ca-central-1|me-south-1|af-south-1)",
    r"\b(us-east-[12]|us-west-[12]|eu-west-[123]|eu-central-1|ap-southeast-[12]|ap-northeast-[123]|sa-east-1|ca-central-1)\b",
]

_ENV_PATTERNS = [
    r"(?:for|in)\s+(production|staging|development|prod|dev|stg|qa|test)\b",
    r"\b(prod(?:uction)?|dev(?:elopment)?|stg|staging|qa|test)\b",
]

_ENV_NORMALIZE = {
    "production": "prod",
    "development": "dev",
    "staging": "stg",
}


class ParameterResolver:
    """Resolves scaffold template parameters from multiple sources."""

    def __init__(
        self,
        intent: str = "",
        space_name: Optional[str] = None,
        project_name: Optional[str] = None,
        scaffold_params: Optional[Dict] = None,
    ):
        """Initialize the resolver.

        Args:
            intent: Natural language intent (for extracting region, env, etc.)
            space_name: Space to load config from (~/.thothcf/spaces/<name>/)
            project_name: Project name override (from --output-dir or explicit)
            scaffold_params: [template_input_parameters] from scaffold .thothcf.toml
        """
        self.intent = intent
        self.space_name = space_name
        self.project_name = project_name
        self.scaffold_params = scaffold_params or {}

    def resolve_all(self) -> Dict[str, str]:
        """Resolve all parameters from all sources.

        Returns:
            Dict mapping parameter names to resolved values.
            Keys match the #{...}# placeholder names.
        """
        # Start with scaffold defaults
        values = self._load_scaffold_defaults()

        # Layer space config values (override defaults)
        space_values = self._load_space_config()
        values.update({k: v for k, v in space_values.items() if v})

        # Layer intent-derived values (override space config)
        intent_values = self._extract_from_intent()
        values.update({k: v for k, v in intent_values.items() if v})

        # Layer explicit overrides
        if self.project_name:
            values["project_name"] = self.project_name

        # Derive computed values
        values = self._compute_derived(values)

        logger.info(
            f"Parameters resolved: {len(values)} values "
            f"(from intent={len(intent_values)}, "
            f"space={len(space_values)}, "
            f"defaults={len(self.scaffold_params)})"
        )
        logger.debug(f"Resolved values: {values}")

        return values

    def resolve_content(self, content: str, values: Dict[str, str]) -> str:
        """Replace all #{key}# placeholders in content with resolved values.

        Args:
            content: Text with #{...}# placeholders.
            values: Resolved parameter values.

        Returns:
            Content with placeholders replaced.
        """
        for key, value in values.items():
            placeholder = f"#{{{key}}}#"
            content = content.replace(placeholder, value)
        return content

    def has_unresolved(self, content: str, values: Dict[str, str]) -> list:
        """Check if content still has unresolved placeholders.

        Returns:
            List of unresolved placeholder names.
        """
        resolved_content = self.resolve_content(content, values)
        remaining = re.findall(r"#\{([^}]+)\}#", resolved_content)
        return remaining

    # ------------------------------------------------------------------
    # Source: Scaffold defaults
    # ------------------------------------------------------------------

    def _load_scaffold_defaults(self) -> Dict[str, str]:
        """Load default values from scaffold's template_input_parameters."""
        values = {}
        for key, param_config in self.scaffold_params.items():
            if isinstance(param_config, dict):
                default = param_config.get("template_value", "")
                if default:
                    values[key] = default
        return values

    # ------------------------------------------------------------------
    # Source: Space configuration
    # ------------------------------------------------------------------

    def _load_space_config(self) -> Dict[str, str]:
        """Load values from space configuration files.

        Reads from:
        - ~/.thothcf/spaces/<name>/orchestration/terragrunt.toml (region)
        - ~/.thothcf/spaces/<name>/space.toml (name)
        - ~/.thothcf/spaces/<name>/terraform/registry.toml (provider)
        """
        values = {}

        if not self.space_name:
            # Try to detect space from environment or current directory
            self.space_name = os.environ.get("THOTH_SPACE")

        if not self.space_name:
            return values

        space_dir = Path.home() / ".thothcf" / "spaces" / self.space_name

        if not space_dir.exists():
            logger.debug(f"Space '{self.space_name}' not found at {space_dir}")
            return values

        try:
            import toml

            # Load orchestration config (has region)
            tg_config = space_dir / "orchestration" / "terragrunt.toml"
            if tg_config.exists():
                data = toml.load(tg_config)
                remote_state = data.get("terragrunt", {}).get("remote_state", {})
                config = remote_state.get("config", {})
                if config.get("region"):
                    values["deployment_region"] = config["region"]
                    values["backend_region"] = config["region"]
                if config.get("bucket"):
                    values["backend_bucket"] = config["bucket"]

            # Load terraform config (has provider info)
            tf_config = space_dir / "terraform" / "registry.toml"
            if tf_config.exists():
                data = toml.load(tf_config)
                providers = data.get("providers", {})
                if "aws" in providers:
                    values["cloud_provider"] = "aws"
                elif "azure" in providers or "azurerm" in providers:
                    values["cloud_provider"] = "azurerm"
                elif "google" in providers or "gcp" in providers:
                    values["cloud_provider"] = "google"

        except Exception as e:
            logger.debug(f"Failed to load space config: {e}")

        return values

    # ------------------------------------------------------------------
    # Source: Intent parsing (NLP-lite)
    # ------------------------------------------------------------------

    def _extract_from_intent(self) -> Dict[str, str]:
        """Extract parameter values from the natural language intent.

        Uses regex patterns to find:
        - AWS region mentions (e.g., "in us-east-1")
        - Environment mentions (e.g., "for production")
        - Project name hints (e.g., "microservices platform")
        """
        values = {}
        intent_lower = self.intent.lower()

        # Extract region
        for pattern in _REGION_PATTERNS:
            match = re.search(pattern, intent_lower)
            if match:
                values["deployment_region"] = match.group(1)
                values["backend_region"] = match.group(1)
                break

        # Extract environment
        for pattern in _ENV_PATTERNS:
            match = re.search(pattern, intent_lower)
            if match:
                env = match.group(1).lower()
                values["environment"] = _ENV_NORMALIZE.get(env, env)
                break

        return values

    # ------------------------------------------------------------------
    # Computed/derived values
    # ------------------------------------------------------------------

    def _compute_derived(self, values: Dict[str, str]) -> Dict[str, str]:
        """Compute derived values from the base parameters.

        Examples:
        - backend_bucket = "{project_name}-{environment}-tfstate" if not set
        - backend_dynamodb = "db-terraform-lock" (default)
        - deployment_profile defaults to space name or "default"
        """
        project = values.get("project_name", "my-project")
        env = values.get("environment", "dev")
        region = values.get("deployment_region", "us-east-1")

        # Backend bucket: derive from project name if not explicitly set
        if not values.get("backend_bucket") or values.get("backend_bucket") == "test-wrapper-tfstate":
            values["backend_bucket"] = f"{project}-{env}-tfstate"

        # Backend region: same as deployment if not set
        if not values.get("backend_region"):
            values["backend_region"] = region

        # DynamoDB lock table: default
        if not values.get("backend_dynamodb") or values.get("backend_dynamodb") == "db-terraform-lock":
            values["backend_dynamodb"] = f"{project}-{env}-tflock"

        # Deployment profile: use space name or default
        if not values.get("deployment_profile") or values.get("deployment_profile") == "default":
            values["deployment_profile"] = self.space_name or "default"

        # Backend profile: same as deployment
        if not values.get("backend_profile") or values.get("backend_profile") == "default":
            values["backend_profile"] = values.get("deployment_profile", "default")

        # Owner: from space name or default
        if not values.get("owner") or values.get("owner") == "thothctl":
            values["owner"] = self.space_name or "platform-team"

        # Client: from space name or default
        if not values.get("client") or values.get("client") == "thothctl":
            values["client"] = self.space_name or "internal"

        # Cloud provider: default aws
        if not values.get("cloud_provider"):
            values["cloud_provider"] = "aws"

        return values
