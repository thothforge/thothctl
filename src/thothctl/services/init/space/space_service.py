"""Space service for ThothForge IDP."""
import logging
from pathlib import Path
from typing import List, Optional

from .space_config import SpaceConfigManager, SpaceConfig

logger = logging.getLogger(__name__)


class SpaceService:
    """Service for managing ThothForge spaces."""

    DEFAULT_VCS_SERVICE = "azure_repos"
    DEFAULT_CI_SYSTEM = "none"

    def __init__(self, logger=None):
        """Initialize the space service.
        
        Args:
            logger: Logger to use
        """
        self.logger = logger or logging.getLogger(__name__)
        self.config_manager = SpaceConfigManager()
    
    def initialize_space(
        self,
        space_name: str,
        vcs: str = DEFAULT_VCS_SERVICE,
        ci: str = DEFAULT_CI_SYSTEM,
        description: str = "",
        terraform_registry: str = "https://registry.terraform.io",
        force: bool = False
    ) -> SpaceConfig:
        """Initialize a new space.
        
        Args:
            space_name: Name of the space
            vcs: Version control system to use
            ci: CI/CD system to use
            description: Description of the space
            terraform_registry: URL of the Terraform registry
            force: Whether to overwrite an existing space
            
        Returns:
            The created space configuration
            
        Raises:
            ValueError: If the space already exists and force is False
        """
        # Check if space already exists
        if self.config_manager.space_exists(space_name) and not force:
            raise ValueError(f"Space '{space_name}' already exists. Use force=True to overwrite.")
        
        # Delete existing space if force is True
        if self.config_manager.space_exists(space_name) and force:
            self.config_manager.delete_space(space_name)
        
        # Create space configuration
        self.logger.info(f"Initializing new space: {space_name}")
        space_config = self.config_manager.create_space(
            space_name=space_name,
            vcs=vcs,
            ci=ci,
            description=description,
            terraform_registry=terraform_registry
        )
        
        self.logger.info(f"Space '{space_name}' created successfully!")
        return space_config
    
    def list_spaces(self) -> List[str]:
        """List all available spaces.
        
        Returns:
            List of space names
        """
        return self.config_manager.list_spaces()
    
    def get_space(self, space_name: str) -> Optional[SpaceConfig]:
        """Get a space configuration.
        
        Args:
            space_name: Name of the space
            
        Returns:
            The space configuration, or None if it doesn't exist
        """
        try:
            return self.config_manager.load_space(space_name)
        except FileNotFoundError:
            return None
    
    def delete_space(self, space_name: str) -> bool:
        """Delete a space.
        
        Args:
            space_name: Name of the space
            
        Returns:
            True if the space was deleted, False otherwise
        """
        return self.config_manager.delete_space(space_name)
    
    def update_space(
        self,
        space_name: str,
        vcs: Optional[str] = None,
        ci: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[SpaceConfig]:
        """Update a space configuration.
        
        Args:
            space_name: Name of the space
            vcs: New version control system
            ci: New CI/CD system
            description: New description
            
        Returns:
            The updated space configuration, or None if it doesn't exist
        """
        try:
            # Load existing space
            space_config = self.config_manager.load_space(space_name)
            
            # Update fields if provided
            if vcs is not None:
                from .space_config import VersionControlSystem
                try:
                    space_config.version_control = VersionControlSystem(vcs)
                except ValueError:
                    self.logger.warning(f"Invalid VCS '{vcs}', ignoring")
            
            if ci is not None:
                from .space_config import CISystem
                try:
                    space_config.ci_system = CISystem(ci)
                except ValueError:
                    self.logger.warning(f"Invalid CI system '{ci}', ignoring")
            
            if description is not None:
                space_config.description = description
            
            # Update timestamp
            from datetime import datetime
            space_config.updated_at = datetime.now().isoformat()
            
            # Save updated configuration
            self.config_manager.save_space(space_config)
            
            return space_config
        except FileNotFoundError:
            self.logger.error(f"Space '{space_name}' not found")
            return None
