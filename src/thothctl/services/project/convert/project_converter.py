import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from abc import ABC, abstractmethod
from colorama import Fore

from ....common.common import load_iac_conf
from ..create_terramate.manage_terramate_stacks import TerramateConfig
from .get_project_data import (
    check_project_properties,
    get_project_props,
    walk_folder_replace,
)
from .set_project_parameters import set_project_conf


@dataclass
class ProjectConversionConfig:
    """Configuration for project conversion."""

    code_directory: Path
    debug: bool = False
    branch_name: str = "main"
    project_type: Optional[str] = None
    make_project: bool = False
    make_template: bool = False
    make_terramate: bool = False


class ProjectConverter(ABC):
    """Abstract base class for project converters."""

    @abstractmethod
    def convert(self) -> None:
        """Execute the conversion process."""
        pass


class TerramateConverter(ProjectConverter):
    """Handles conversion to Terramate stacks."""

    def __init__(self, config: ProjectConversionConfig, stack_manager):
        self.config = config
        self.stack_manager = stack_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def convert(self) -> None:
        """Convert to Terramate stacks."""
        try:
            print(f"👷 {Fore.BLUE}Starting Terramate conversion...{Fore.RESET}")

            # Create configuration
            config = TerramateConfig(
                directory=self.config.code_directory,
                optimized=False,
                default_branch=self.config.branch_name or "main",
            )

            # Create main configuration file
            print(f"👷{Fore.BLUE}Creating main Terramate configuration...{Fore.RESET}")
            self.stack_manager.create_main_file(config=config)

            # Process directories
            print(
                f"👷{Fore.BLUE}Processing directories for Terramate stacks...{Fore.RESET}"
            )
            self.stack_manager.process_directory_recursively(config.directory)

            print(
                f"{Fore.GREEN}✅ Terramate conversion completed successfully!{Fore.RESET}"
            )

        except Exception as e:
            self.logger.error(f"Terramate conversion failed: {e}")
            print(f"{Fore.RED}❌ Terramate conversion failed: {e}{Fore.RESET}")
            raise


class ProjectTemplateConverter(ProjectConverter):
    """Handles conversion between projects and templates."""

    def __init__(self, config: ProjectConversionConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def convert(self) -> None:
        """Convert between project and template."""
        try:
            project_props = self._get_project_properties()
            project_name = self._get_project_name()
            print(f"👷 {Fore.BLUE} Creating project {project_name} {Fore.RESET}")

            self._apply_project_configuration(project_props)
            self._process_directory(project_props, project_name)

        except Exception as e:
            self.logger.error(f"Project conversion failed: {e}")
            raise

    def _get_project_properties(self) -> dict:
        """Get project properties based on project type."""
        project_props = {}
        if self.config.project_type in [
            "terraform",
            "tofu",
        ] and check_project_properties(
            directory=self.config.code_directory,
        ):
            project_props = get_project_props(
                cloud_provider="aws", remote_bkd_cloud_provider="aws"
            )
            set_project_conf(project_properties=project_props)

        return project_props

    def _get_project_name(self) -> str:
        """Get project name from configuration file."""
        return load_iac_conf(
            directory=self.config.code_directory, file_name=".thothcf.toml"
        )["thothcf"]["project_id"]

    def _apply_project_configuration(self, project_props: dict) -> None:
        """Apply project configuration if properties exist."""
        if project_props:
            set_project_conf(project_properties=project_props)

    def _process_directory(self, project_props: dict, project_name: str) -> None:
        """Process directory for conversion."""
        action = "make_project"
        if self.config.make_template:
            action = "make_template"

        walk_folder_replace(
            directory=self.config.code_directory,
            action=action,
            project_properties=project_props,
            project_name=project_name,
        )
