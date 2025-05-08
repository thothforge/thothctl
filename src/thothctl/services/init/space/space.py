"""Space service for managing spaces."""
import logging
import os
from pathlib import Path
from typing import Optional

import toml
from colorama import Fore


class SpaceService:
    """Service for managing spaces."""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def initialize_space(
        self, 
        space_name: str, 
        description: Optional[str] = None,
        vcs_provider: str = "azure_repos",
        terraform_registry: str = "https://registry.terraform.io",
        terraform_auth: str = "none",
        orchestration_tool: str = "terragrunt",
    ) -> None:
        """
        Initialize a new space.
        
        :param space_name: Name of the space
        :param description: Optional description of the space
        :param vcs_provider: Version Control System provider (azure_repos, github, gitlab)
        :param terraform_registry: Terraform registry URL
        :param terraform_auth: Terraform registry authentication method (none, token, env_var)
        :param orchestration_tool: Default orchestration tool (terragrunt, terramate, none)
        :return: None
        """
        self.logger.info(f"Initializing space: {space_name}")
        
        # Create space configuration
        self._create_space_config(
            space_name=space_name, 
            description=description,
            vcs_provider=vcs_provider,
            terraform_registry=terraform_registry,
            terraform_auth=terraform_auth,
            orchestration_tool=orchestration_tool
        )
        
        # Create space directory structure
        self._create_space_directory(
            space_name=space_name,
            vcs_provider=vcs_provider,
            terraform_registry=terraform_registry,
            terraform_auth=terraform_auth,
            orchestration_tool=orchestration_tool
        )
        
        self.logger.info(f"Space {space_name} initialized successfully")

    def _create_space_config(
        self, 
        space_name: str, 
        description: Optional[str] = None,
        vcs_provider: str = "azure_repos",
        terraform_registry: str = "https://registry.terraform.io",
        terraform_auth: str = "none",
        orchestration_tool: str = "terragrunt",
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
            }
        }
        
        # Save config
        with open(config_path, mode="wt", encoding="utf-8") as fp:
            toml.dump(config, fp)
            
        print(f"{Fore.GREEN}Space '{space_name}' configuration created{Fore.RESET}")

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
        os.makedirs(space_dir.joinpath("templates"), exist_ok=True)
        os.makedirs(space_dir.joinpath("vcs"), exist_ok=True)  # Version Control System configs
        os.makedirs(space_dir.joinpath("terraform"), exist_ok=True)  # Terraform registry configs
        os.makedirs(space_dir.joinpath("orchestration"), exist_ok=True)  # Orchestration tool configs
        
        # Create default space configuration file
        space_config = {
            "space": {
                "name": space_name,
                "version": "1.0.0"
            },
            "credentials": {
                "path": "credentials"
            },
            "configurations": {
                "path": "configs"
            },
            "templates": {
                "path": "templates"
            },
            "version_control": {
                "path": "vcs",
                "default_provider": vcs_provider,
                "providers": ["azure_repos", "github", "gitlab"]
            },
            "terraform": {
                "path": "terraform",
                "registry_url": terraform_registry,
                "auth_method": terraform_auth  # Options: none, token, env_var
            },
            "orchestration": {
                "path": "orchestration",
                "default_tool": orchestration_tool,
                "tools": ["terragrunt", "terramate", "none"]
            }
        }
        
        with open(space_dir.joinpath("space.toml"), mode="wt", encoding="utf-8") as fp:
            toml.dump(space_config, fp)
            
        # Create provider-specific configuration files
        self._create_vcs_config(space_dir.joinpath("vcs"), vcs_provider)
        self._create_terraform_config(space_dir.joinpath("terraform"), terraform_registry, terraform_auth)
        self._create_orchestration_config(space_dir.joinpath("orchestration"), orchestration_tool)
            
        print(f"{Fore.GREEN}Space '{space_name}' directory structure created at {space_dir}{Fore.RESET}")

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
                "auth_method": "pat"  # Options: pat, oauth, ssh
            }
        }
        
        with open(vcs_dir.joinpath(f"{provider}.toml"), mode="wt", encoding="utf-8") as fp:
            toml.dump(config, fp)

    def _create_terraform_config(self, terraform_dir: Path, registry_url: str, auth_method: str) -> None:
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
                "token": "" if auth_method == "token" else ""
            },
            "providers": {
                "aws": {
                    "version": "~> 4.0",
                    "source": "hashicorp/aws"
                },
                "azure": {
                    "version": "~> 3.0",
                    "source": "hashicorp/azurerm"
                }
            }
        }
        
        with open(terraform_dir.joinpath("registry.toml"), mode="wt", encoding="utf-8") as fp:
            toml.dump(config, fp)

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
                            "encrypt": True
                        }
                    },
                    "generate": {
                        "provider": True,
                        "backend": True
                    }
                }
            }
            
            with open(orchestration_dir.joinpath("terragrunt.toml"), mode="wt", encoding="utf-8") as fp:
                toml.dump(config, fp)
                
        elif tool == "terramate":
            config = {
                "terramate": {
                    "version": "latest",
                    "config": {
                        "root_dir": "",
                        "stack_dir": "stacks",
                        "generate_hcl": True
                    }
                }
            }
            
            with open(orchestration_dir.joinpath("terramate.toml"), mode="wt", encoding="utf-8") as fp:
                toml.dump(config, fp)

    @staticmethod
    def _get_current_timestamp() -> str:
        """
        Get current timestamp in ISO format.
        
        :return: Current timestamp string
        """
        from datetime import datetime
        return datetime.now().isoformat()
