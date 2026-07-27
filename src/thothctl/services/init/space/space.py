"""Space service for managing spaces."""

import getpass
import logging
import os
from pathlib import Path
from typing import Optional

import toml

from ....core.cli_ui import CliUI
from ....utils.crypto import save_credentials


class SpaceService:
    """Service for managing spaces."""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.ui = CliUI()

    def initialize_space(
        self,
        space_name: str,
        description: Optional[str] = None,
        vcs_provider: str = "azure_repos",
        terraform_registry: str = "https://registry.terraform.io",
        terraform_auth: str = "none",
        orchestration_tool: str = "terragrunt",
        policy_repo: Optional[str] = None,
        vcs_token: Optional[str] = None,
        vcs_org: Optional[str] = None,
        credential_password: Optional[str] = None,
    ) -> None:
        """
        Initialize a new space.

        :param space_name: Name of the space
        :param description: Optional description of the space
        :param vcs_provider: Version Control System provider (azure_repos, github, gitlab)
        :param terraform_registry: Terraform registry URL
        :param terraform_auth: Terraform registry authentication method (none, token, env_var)
        :param orchestration_tool: Default orchestration tool (terragrunt, terramate, none)
        :param policy_repo: Git repository URL for organization-level IaC policies
        :param vcs_token: Optional VCS token for non-interactive setup (falls back to THOTH_SPACE_TOKEN env var)
        :param vcs_org: Optional VCS organization/username for non-interactive setup (falls back to THOTH_SPACE_ORG env var)
        :param credential_password: Optional encryption password for non-interactive setup (falls back to THOTH_SPACE_PASSWORD env var)
        :return: None
        """
        self.ui.print_info(f"🚀 Initializing space: {space_name}")

        # Resolve policy_repo from environment if not provided
        if not policy_repo:
            policy_repo = os.environ.get("THOTH_POLICY_REPO")

        # Create space configuration
        with self.ui.status_spinner("🔧 Creating space configuration..."):
            self._create_space_config(
                space_name=space_name,
                description=description,
                vcs_provider=vcs_provider,
                terraform_registry=terraform_registry,
                terraform_auth=terraform_auth,
                orchestration_tool=orchestration_tool,
                policy_repo=policy_repo,
            )

        # Create space directory structure
        with self.ui.status_spinner("📁 Setting up space directory structure..."):
            self._create_space_directory(
                space_name=space_name,
                vcs_provider=vcs_provider,
                terraform_registry=terraform_registry,
                terraform_auth=terraform_auth,
                orchestration_tool=orchestration_tool,
            )

        # Setup credentials if needed
        if vcs_provider == "azure_repos":
            self._setup_azure_repos_credentials(
                space_name, token=vcs_token, org=vcs_org, password=credential_password
            )
        elif vcs_provider == "github":
            self._setup_github_credentials(
                space_name, token=vcs_token, org=vcs_org, password=credential_password
            )
        elif vcs_provider == "gitlab":
            self._setup_gitlab_credentials(
                space_name, token=vcs_token, org=vcs_org, password=credential_password
            )

        # Setup Terraform credentials if needed
        if terraform_auth != "none":
            self._setup_terraform_credentials(
                space_name,
                terraform_auth,
                token=vcs_token,
                password=credential_password,
            )

        self.ui.print_success(f"🎉 Space '{space_name}' initialized successfully!")

    def _create_space_config(
        self,
        space_name: str,
        description: Optional[str] = None,
        vcs_provider: str = "azure_repos",
        terraform_registry: str = "https://registry.terraform.io",
        terraform_auth: str = "none",
        orchestration_tool: str = "terragrunt",
        policy_repo: Optional[str] = None,
    ) -> None:
        """
        Create space configuration in the global thothcf config.

        :param space_name: Name of the space
        :param description: Optional description of the space
        :param vcs_provider: Version Control System provider
        :param terraform_registry: Terraform registry URL
        :param terraform_auth: Terraform registry authentication method
        :param orchestration_tool: Default orchestration tool
        :return: None
        """
        config_path = Path.joinpath(Path.home(), ".thothcf", "spaces.toml")

        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Load existing config or create new one
        if os.path.exists(config_path):
            with open(config_path, mode="rt", encoding="utf-8") as fp:
                config = toml.load(fp)
        else:
            config = {"spaces": {}}

        # Check if space already exists
        if "spaces" in config and space_name in config["spaces"]:
            raise ValueError(f"Space '{space_name}' already exists")

        # Add space to config
        if "spaces" not in config:
            config["spaces"] = {}

        config["spaces"][space_name] = {
            "name": space_name,
            "description": description or f"Space for {space_name}",
            "created_at": self._get_current_timestamp(),
            "version_control": {
                "provider": vcs_provider,
            },
            "terraform": {
                "registry": terraform_registry,
                "auth_method": terraform_auth,
            },
            "orchestration": {
                "tool": orchestration_tool,
            },
            "governance": {
                "policy_repo": policy_repo or "",
            },
        }

        # Save config
        with open(config_path, mode="wt", encoding="utf-8") as fp:
            toml.dump(config, fp)

        self.ui.print_success(f"🔧 Space '{space_name}' configuration created")

    def _create_space_directory(
        self,
        space_name: str,
        vcs_provider: str = "azure_repos",
        terraform_registry: str = "https://registry.terraform.io",
        terraform_auth: str = "none",
        orchestration_tool: str = "terragrunt",
    ) -> None:
        """
        Create directory structure for the space.

        :param space_name: Name of the space
        :param vcs_provider: Version Control System provider
        :param terraform_registry: Terraform registry URL
        :param terraform_auth: Terraform registry authentication method
        :param orchestration_tool: Default orchestration tool
        :return: None
        """
        space_dir = Path.joinpath(Path.home(), ".thothcf", "spaces", space_name)

        # Create main space directory
        os.makedirs(space_dir, exist_ok=True)

        # Create subdirectories for space resources
        os.makedirs(space_dir.joinpath("credentials"), exist_ok=True)
        os.makedirs(space_dir.joinpath("configs"), exist_ok=True)

        # Create default scan policy configuration
        scan_policy_path = space_dir.joinpath("configs", "scan_policy.toml")
        scan_policy_path.write_text(
            "# Space-level scan policy overrides\n"
            "# These settings apply to all projects in this space unless overridden at project level.\n"
            "\n"
            "[scan]\n"
            '# Enforcement mode: "soft" (report only) or "hard" (fail on violations)\n'
            'enforcement = "soft"\n'
            '# Minimum severity to report: "low", "medium", "high", "critical"\n'
            'severity_threshold = "medium"\n'
            "# Checks to exclude (by ID)\n"
            "excluded_checks = []\n"
            "\n"
            "[supply_chain]\n"
            "# Maximum days a module can be stale before warning/denial\n"
            "max_staleness_days_warn = 90\n"
            "max_staleness_days_deny = 180\n"
            "# Require exact version pinning for all modules\n"
            "require_exact_pinning = true\n",
            encoding="utf-8",
        )
        os.makedirs(
            space_dir.joinpath("vcs"), exist_ok=True
        )  # Version Control System configs
        os.makedirs(
            space_dir.joinpath("terraform"), exist_ok=True
        )  # Terraform registry configs
        os.makedirs(
            space_dir.joinpath("orchestration"), exist_ok=True
        )  # Orchestration tool configs

        # Create minimal metadata file for directory identification only.
        # All configuration is stored in ~/.thothcf/spaces.toml (single source of truth).
        metadata = {
            "space": {
                "name": space_name,
                "created_at": self._get_current_timestamp(),
                "config_source": "~/.thothcf/spaces.toml",
            },
        }

        with open(
            space_dir.joinpath("metadata.toml"), mode="wt", encoding="utf-8"
        ) as fp:
            toml.dump(metadata, fp)

        # Create provider-specific configuration files
        self._create_vcs_config(space_dir.joinpath("vcs"), vcs_provider)
        self._create_terraform_config(
            space_dir.joinpath("terraform"), terraform_registry, terraform_auth
        )
        self._create_orchestration_config(
            space_dir.joinpath("orchestration"), orchestration_tool
        )

        self.ui.print_info(
            f"📁 Space '{space_name}' directory structure created at {space_dir}"
        )

    def _create_vcs_config(self, vcs_dir: Path, provider: str) -> None:
        """
        Create version control system configuration files.

        :param vcs_dir: Directory for VCS configuration
        :param provider: VCS provider name
        :return: None
        """
        config = {
            "provider": provider,
            "settings": {
                "organization": "",
                "project": "",
                "repository": "",
                "branch": "main",
                "auth_method": "pat",  # Options: pat, oauth, ssh
            },
        }

        with open(
            vcs_dir.joinpath(f"{provider}.toml"), mode="wt", encoding="utf-8"
        ) as fp:
            toml.dump(config, fp)

        self.ui.print_info(f"🔗 Created {provider} VCS configuration")

    def _create_terraform_config(
        self, terraform_dir: Path, registry_url: str, auth_method: str
    ) -> None:
        """
        Create Terraform configuration files.

        :param terraform_dir: Directory for Terraform configuration
        :param registry_url: Terraform registry URL
        :param auth_method: Authentication method
        :return: None
        """
        config = {
            "registry": {
                "url": registry_url,
                "auth_method": auth_method,
                "token_env_var": "TF_TOKEN" if auth_method == "env_var" else "",
                "token": "" if auth_method == "token" else "",
            },
            "providers": {
                "aws": {"version": "~> 4.0", "source": "hashicorp/aws"},
                "azure": {"version": "~> 3.0", "source": "hashicorp/azurerm"},
            },
        }

        with open(
            terraform_dir.joinpath("registry.toml"), mode="wt", encoding="utf-8"
        ) as fp:
            toml.dump(config, fp)

        self.ui.print_info("🏗️ Created Terraform registry configuration")

    def _create_orchestration_config(self, orchestration_dir: Path, tool: str) -> None:
        """
        Create orchestration tool configuration files.

        :param orchestration_dir: Directory for orchestration configuration
        :param tool: Orchestration tool name
        :return: None
        """
        if tool == "terragrunt":
            config = {
                "terragrunt": {
                    "version": "latest",
                    "remote_state": {
                        "backend": "s3",
                        "config": {
                            "bucket": "",
                            "key": "${path_relative_to_include()}/terraform.tfstate",
                            "region": "us-east-1",
                            "encrypt": True,
                        },
                    },
                    "generate": {"provider": True, "backend": True},
                }
            }

            with open(
                orchestration_dir.joinpath("terragrunt.toml"),
                mode="wt",
                encoding="utf-8",
            ) as fp:
                toml.dump(config, fp)

            self.ui.print_info("🔄 Created Terragrunt orchestration configuration")

        elif tool == "terramate":
            config = {
                "terramate": {
                    "version": "latest",
                    "config": {
                        "root_dir": "",
                        "stack_dir": "stacks",
                        "generate_hcl": True,
                    },
                }
            }

            with open(
                orchestration_dir.joinpath("terramate.toml"),
                mode="wt",
                encoding="utf-8",
            ) as fp:
                toml.dump(config, fp)

            self.ui.print_info("🔄 Created Terramate orchestration configuration")

    def _setup_azure_repos_credentials(
        self, space_name: str, token=None, org=None, password=None
    ) -> None:
        """
        Setup Azure Repos credentials for the space.

        :param space_name: Name of the space
        :param token: Optional PAT token (falls back to THOTH_SPACE_TOKEN env var, then interactive prompt)
        :param org: Optional organization name (falls back to THOTH_SPACE_ORG env var, then interactive prompt)
        :param password: Optional encryption password (falls back to THOTH_SPACE_PASSWORD env var, then interactive prompt)
        :return: None
        """
        self.ui.print_info("🔐 Setting up Azure DevOps credentials")

        # Ask for organization name
        org_name = (
            org
            or os.environ.get("THOTH_SPACE_ORG")
            or input("Enter Azure DevOps organization name: ")
        )

        # Ask for PAT securely
        self.ui.print_info(
            "You'll need a Personal Access Token (PAT) with appropriate permissions"
        )
        pat = (
            token
            or os.environ.get("THOTH_SPACE_TOKEN")
            or getpass.getpass("Enter your Azure DevOps Personal Access Token: ")
        )

        # Create credentials dictionary
        credentials = {"type": "azure_repos", "organization": org_name, "pat": pat}

        # Ask for encryption password
        encryption_password = (
            password
            or os.environ.get("THOTH_SPACE_PASSWORD")
            or getpass.getpass("Enter a password to encrypt your credentials: ")
        )

        # Save encrypted credentials
        try:
            save_credentials(
                space_name=space_name,
                credentials=credentials,
                credential_type="vcs",
                password=encryption_password,
            )
            self.ui.print_success("🔒 Azure DevOps credentials saved securely")
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
            self.ui.print_error(f"Failed to save credentials: {e}")

    def _setup_github_credentials(
        self, space_name: str, token=None, org=None, password=None
    ) -> None:
        """
        Setup GitHub credentials for the space.

        :param space_name: Name of the space
        :param token: Optional PAT token (falls back to THOTH_SPACE_TOKEN env var, then interactive prompt)
        :param org: Optional username/org (falls back to THOTH_SPACE_ORG env var, then interactive prompt)
        :param password: Optional encryption password (falls back to THOTH_SPACE_PASSWORD env var, then interactive prompt)
        :return: None
        """
        self.ui.print_info("🔐 Setting up GitHub credentials")

        # Ask for GitHub username
        username = (
            org or os.environ.get("THOTH_SPACE_ORG") or input("Enter GitHub username: ")
        )

        # Ask for token securely
        self.ui.print_info(
            "You'll need a Personal Access Token with appropriate permissions"
        )
        pat = (
            token
            or os.environ.get("THOTH_SPACE_TOKEN")
            or getpass.getpass("Enter your GitHub Personal Access Token: ")
        )

        # Create credentials dictionary
        credentials = {"type": "github", "username": username, "token": pat}

        # Ask for encryption password
        encryption_password = (
            password
            or os.environ.get("THOTH_SPACE_PASSWORD")
            or getpass.getpass("Enter a password to encrypt your credentials: ")
        )

        # Save encrypted credentials
        try:
            save_credentials(
                space_name=space_name,
                credentials=credentials,
                credential_type="vcs",
                password=encryption_password,
            )
            self.ui.print_success("🔒 GitHub credentials saved securely")
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
            self.ui.print_error(f"Failed to save credentials: {e}")

    def _setup_gitlab_credentials(
        self, space_name: str, token=None, org=None, password=None
    ) -> None:
        """
        Setup GitLab credentials for the space.

        :param space_name: Name of the space
        :param token: Optional PAT token (falls back to THOTH_SPACE_TOKEN env var, then interactive prompt)
        :param org: Optional username/org (falls back to THOTH_SPACE_ORG env var, then interactive prompt)
        :param password: Optional encryption password (falls back to THOTH_SPACE_PASSWORD env var, then interactive prompt)
        :return: None
        """
        self.ui.print_info("🔐 Setting up GitLab credentials")

        # Ask for GitLab username
        username = (
            org or os.environ.get("THOTH_SPACE_ORG") or input("Enter GitLab username: ")
        )

        # Ask for token securely
        self.ui.print_info(
            "You'll need a Personal Access Token with appropriate permissions"
        )
        pat = (
            token
            or os.environ.get("THOTH_SPACE_TOKEN")
            or getpass.getpass("Enter your GitLab Personal Access Token: ")
        )

        # Create credentials dictionary
        credentials = {"type": "gitlab", "username": username, "token": pat}

        # Ask for encryption password
        encryption_password = (
            password
            or os.environ.get("THOTH_SPACE_PASSWORD")
            or getpass.getpass("Enter a password to encrypt your credentials: ")
        )

        # Save encrypted credentials
        try:
            save_credentials(
                space_name=space_name,
                credentials=credentials,
                credential_type="vcs",
                password=encryption_password,
            )
            self.ui.print_success("🔒 GitLab credentials saved securely")
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
            self.ui.print_error(f"Failed to save credentials: {e}")

    def _setup_terraform_credentials(
        self, space_name: str, auth_method: str, token=None, password=None
    ) -> None:
        """
        Setup Terraform registry credentials for the space.

        :param space_name: Name of the space
        :param auth_method: Authentication method (token, env_var)
        :param token: Optional registry token (falls back to THOTH_SPACE_TF_TOKEN env var, then interactive prompt)
        :param password: Optional encryption password (falls back to THOTH_SPACE_PASSWORD env var, then interactive prompt)
        :return: None
        """
        if auth_method == "token":
            self.ui.print_info("🔐 Setting up Terraform registry token")

            # Ask for token securely
            tf_token = (
                token
                or os.environ.get("THOTH_SPACE_TF_TOKEN")
                or getpass.getpass("Enter your Terraform registry token: ")
            )

            # Create credentials dictionary
            credentials = {
                "type": "terraform",
                "auth_method": "token",
                "token": tf_token,
            }

            # Ask for encryption password
            encryption_password = (
                password
                or os.environ.get("THOTH_SPACE_PASSWORD")
                or getpass.getpass("Enter a password to encrypt your credentials: ")
            )

            # Save encrypted credentials
            try:
                save_credentials(
                    space_name=space_name,
                    credentials=credentials,
                    credential_type="terraform",
                    password=encryption_password,
                )
                self.ui.print_success(
                    "🔒 Terraform registry credentials saved securely"
                )
            except Exception as e:
                self.logger.error(f"Failed to save credentials: {e}")
                self.ui.print_error(f"Failed to save credentials: {e}")
        elif auth_method == "env_var":
            self.ui.print_info("🔐 Setting up Terraform registry environment variable")

            # Ask for environment variable name
            env_var = (
                input(
                    "Enter the environment variable name for Terraform token [TF_TOKEN]: "
                )
                or "TF_TOKEN"
            )

            # Create credentials dictionary
            credentials = {
                "type": "terraform",
                "auth_method": "env_var",
                "env_var": env_var,
            }

            # Save credentials (no need for encryption as it's just an env var name)
            try:
                save_credentials(
                    space_name=space_name,
                    credentials=credentials,
                    credential_type="terraform",
                    password="env_var_only",  # Simple password as it's not sensitive
                )
                self.ui.print_success(
                    f"🔒 Terraform registry environment variable set to {env_var}"
                )
                self.ui.print_info(
                    f"Remember to set the {env_var} environment variable with your token"
                )
            except Exception as e:
                self.logger.error(f"Failed to save credentials: {e}")
                self.ui.print_error(f"Failed to save credentials: {e}")

    @staticmethod
    def _get_current_timestamp() -> str:
        """
        Get current timestamp in ISO format.

        :return: Current timestamp string
        """
        from datetime import datetime

        return datetime.now().isoformat()
