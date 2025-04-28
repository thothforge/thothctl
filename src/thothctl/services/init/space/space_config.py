"""Space configuration manager for ThothForge IDP."""
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import toml

logger = logging.getLogger(__name__)


class VersionControlSystem(Enum):
    """Supported version control systems."""
    AZURE_REPOS = "azure_repos"
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class CISystem(Enum):
    """Supported CI/CD systems."""
    GITHUB_ACTIONS = "github-actions"
    GITLAB_CI = "gitlab-ci"
    AZURE_PIPELINES = "azure-pipelines"
    JENKINS = "jenkins"
    NONE = "none"


@dataclass
class RegistryConfig:
    """Configuration for a module registry."""
    name: str
    url: str
    type: str = "terraform"
    auth_required: bool = False
    auth_token: Optional[str] = None
    default: bool = False


@dataclass
class SpaceConfig:
    """Configuration for a ThothForge space."""
    name: str
    version_control: VersionControlSystem
    ci_system: CISystem
    description: str = ""
    registries: List[RegistryConfig] = field(default_factory=list)
    endpoints: Dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class SpaceConfigManager:
    """Manages space configurations for ThothForge IDP."""

    def __init__(self, config_dir: str = "~/.thothcf"):
        """Initialize the space configuration manager.
        
        Args:
            config_dir: Directory where configuration files are stored
        """
        self.config_dir = os.path.expanduser(config_dir)
        self._ensure_config_dir()
    
    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists."""
        os.makedirs(self.config_dir, exist_ok=True)
        
    def _get_space_config_path(self, space_name: str) -> Path:
        """Get the path to a space configuration file.
        
        Args:
            space_name: Name of the space
            
        Returns:
            Path to the space configuration file
        """
        return Path(os.path.join(self.config_dir, f"{space_name}.toml"))
    
    def space_exists(self, space_name: str) -> bool:
        """Check if a space configuration exists.
        
        Args:
            space_name: Name of the space
            
        Returns:
            True if the space configuration exists, False otherwise
        """
        return self._get_space_config_path(space_name).exists()
    
    def create_space(self, 
                    space_name: str, 
                    vcs: str = "azure_repos", 
                    ci: str = "none",
                    description: str = "",
                    terraform_registry: str = "https://registry.terraform.io") -> SpaceConfig:
        """Create a new space configuration.
        
        Args:
            space_name: Name of the space
            vcs: Version control system to use
            ci: CI/CD system to use
            description: Description of the space
            terraform_registry: URL of the Terraform registry
            
        Returns:
            The created space configuration
            
        Raises:
            ValueError: If the space already exists
        """
        if self.space_exists(space_name):
            raise ValueError(f"Space '{space_name}' already exists")
        
        # Create default configuration
        from datetime import datetime
        
        # Convert string values to enum values
        try:
            vcs_enum = VersionControlSystem(vcs)
        except ValueError:
            logger.warning(f"Invalid VCS '{vcs}', using default")
            vcs_enum = VersionControlSystem.AZURE_REPOS
            
        try:
            ci_enum = CISystem(ci)
        except ValueError:
            logger.warning(f"Invalid CI system '{ci}', using default")
            ci_enum = CISystem.NONE
        
        # Create space configuration
        now = datetime.now().isoformat()
        space_config = SpaceConfig(
            name=space_name,
            version_control=vcs_enum,
            ci_system=ci_enum,
            description=description,
            created_at=now,
            updated_at=now,
            registries=[
                RegistryConfig(
                    name="terraform-registry",
                    url=terraform_registry,
                    default=True
                )
            ],
            endpoints={}
        )
        
        # Save configuration
        self.save_space(space_config)
        
        return space_config
    
    def save_space(self, space_config: SpaceConfig) -> None:
        """Save a space configuration.
        
        Args:
            space_config: Space configuration to save
        """
        # Convert to dictionary
        config_dict = {
            "space": {
                "name": space_config.name,
                "description": space_config.description,
                "version_control": space_config.version_control.value,
                "ci_system": space_config.ci_system.value,
                "created_at": space_config.created_at,
                "updated_at": space_config.updated_at
            },
            "registries": [
                {
                    "name": reg.name,
                    "url": reg.url,
                    "type": reg.type,
                    "auth_required": reg.auth_required,
                    "default": reg.default
                }
                for reg in space_config.registries
            ],
            "endpoints": space_config.endpoints
        }
        
        # Save to file
        config_path = self._get_space_config_path(space_config.name)
        with open(config_path, "w") as f:
            toml.dump(config_dict, f)
        
        logger.info(f"Space configuration saved to {config_path}")
    
    def load_space(self, space_name: str) -> SpaceConfig:
        """Load a space configuration.
        
        Args:
            space_name: Name of the space
            
        Returns:
            The loaded space configuration
            
        Raises:
            FileNotFoundError: If the space configuration does not exist
        """
        config_path = self._get_space_config_path(space_name)
        if not config_path.exists():
            raise FileNotFoundError(f"Space configuration '{space_name}' not found")
        
        # Load from file
        with open(config_path, "r") as f:
            config_dict = toml.load(f)
        
        # Convert to SpaceConfig
        space_data = config_dict.get("space", {})
        
        # Create registries
        registries = []
        for reg_data in config_dict.get("registries", []):
            registry = RegistryConfig(
                name=reg_data.get("name", ""),
                url=reg_data.get("url", ""),
                type=reg_data.get("type", "terraform"),
                auth_required=reg_data.get("auth_required", False),
                default=reg_data.get("default", False)
            )
            registries.append(registry)
        
        # Create space config
        space_config = SpaceConfig(
            name=space_data.get("name", space_name),
            version_control=VersionControlSystem(space_data.get("version_control", "azure_repos")),
            ci_system=CISystem(space_data.get("ci_system", "none")),
            description=space_data.get("description", ""),
            created_at=space_data.get("created_at", ""),
            updated_at=space_data.get("updated_at", ""),
            registries=registries,
            endpoints=config_dict.get("endpoints", {})
        )
        
        return space_config
    
    def list_spaces(self) -> List[str]:
        """List all available spaces.
        
        Returns:
            List of space names
        """
        spaces = []
        for file_path in Path(self.config_dir).glob("*.toml"):
            spaces.append(file_path.stem)
        return spaces
    
    def delete_space(self, space_name: str) -> bool:
        """Delete a space configuration.
        
        Args:
            space_name: Name of the space
            
        Returns:
            True if the space was deleted, False otherwise
        """
        config_path = self._get_space_config_path(space_name)
        if config_path.exists():
            config_path.unlink()
            return True
        return False
