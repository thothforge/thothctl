import click
from contextlib import contextmanager
from typing import Final, Optional
from pathlib import Path
import os
import getpass


from thothctl.core.commands import ClickCommand
from thothctl.common.common import create_info_project
from thothctl.utils.parser_iac_templates.set_project_parameters import set_project_conf
from thothctl.utils.parser_iac_templates.get_project_data import (
    get_project_props,
    walk_folder_replace,
    check_project_properties,
    get_project_props,

)
from thothctl.core.integrations.azure_devops.get_azure_devops import get_pattern_from_azure
from thothctl.services.generate.create_template.create_template import (
    create_project,
)

# Define constants at module level
AZURE_DEVOPS_URL: Final = "https://dev.azure.com"
DEFAULT_CLOUD_PROVIDER: Final = "aws"
DEFAULT_VCS_SERVICE: Final = "azure_repos"


class ProjectInitCommand(ClickCommand):
    """Command to initialize a new project"""

    def validate(self, project_name: str, **kwargs) -> bool:
        """Validate project initialization parameters"""
        if not project_name or not project_name.strip():
            raise ValueError("Project name is required and cannot be empty")
        return True

    def execute(
            self,
            project_name: str,
            setup_conf: bool,
            version_control_system_service: str = DEFAULT_VCS_SERVICE,
            az_org_name: Optional[str] = None,
            reuse: bool = False,
            r_list: bool = False,
            project_type: str = "terraform",
            **kwargs
    ) -> None:
        """Execute project initialization"""
        project_name = project_name.strip()
        project_path = Path(f"./{project_name}")

        self._init_project(project_name)

        if setup_conf:
            self._setup_project_config(project_name)

        if self._should_setup_azure_repos(version_control_system_service, reuse, az_org_name):
            self._setup_azure_repos(project_name, project_path, az_org_name, r_list)
        if not reuse:
            self._init_create_project(project_name, project_type)

    @staticmethod
    def _init_create_project(self, project_name: str, project_type: str) -> None:
        """Initialize the project using the create_project function"""
        create_project(project_name=project_name, project_type=project_type)


    @staticmethod
    def _init_project(self, project_name: str) -> None:
        """Initialize the basic project structure"""
        self.logger.info(f"Initializing project: {project_name}")
        create_info_project(project_name=project_name)
        self.logger.info(f"Project {project_name} initialized successfully")

    @staticmethod
    def _setup_project_config(self, project_name: str) -> None:
        """Setup project configuration"""
        project_props = get_project_props(
            project_name=project_name,
            cloud_provider=DEFAULT_CLOUD_PROVIDER,
            remote_bkd_cloud_provider=DEFAULT_CLOUD_PROVIDER,
        )
        set_project_conf(
            project_name=project_name,
            project_properties=project_props,
        )

    @staticmethod
    def _should_setup_azure_repos(
            self,
            vcs_service: str,
            reuse: bool,
            az_org_name: Optional[str]
    ) -> bool:
        """Check if Azure Repos setup should be performed"""
        return all([
            vcs_service == DEFAULT_VCS_SERVICE,
            reuse,
            az_org_name is not None
        ])

    def _setup_azure_repos(
            self,
            project_name: str,
            project_path: Path,
            az_org_name: str,
            r_list: bool
    ) -> None:
        """Setup Azure Repos configuration"""
        self.logger.info("Azure Repos Service selected")

        org_url = f"{AZURE_DEVOPS_URL}/{az_org_name}/"
        action = "list" if r_list else "reuse"

        # Get PAT securely
        pat = self._get_azure_pat()

        repo_meta = get_pattern_from_azure(
            pat=pat,
            org_url=org_url,
            directory=project_name,
            action=action,
        )

        project_props = get_project_props(
            project_name=project_name,
            cloud_provider=DEFAULT_CLOUD_PROVIDER,
            remote_bkd_cloud_provider=DEFAULT_CLOUD_PROVIDER,
            directory=project_path,
        )

        # Change directory safely using context manager
        with self._change_directory(project_path):
            walk_folder_replace(
                directory=Path("."),
                project_properties=project_props,
                project_name=project_name,
            )

            set_project_conf(
                project_properties=project_props,
                project_name=project_name,
                directory=Path("."),
                repo_metadata=repo_meta,
            )

    @staticmethod
    def _get_azure_pat() -> str:
        """Securely get Azure Personal Access Token"""
        print("Pass your Personal Access Token")
        return getpass.getpass()

    @contextmanager
    def _change_directory(self, path: Path):
        """Safely change directory and return to original"""
        original_dir = Path.cwd()
        try:
            os.chdir(path)
            yield
        finally:
            os.chdir(original_dir)


# Create the Click command
cli = ProjectInitCommand.as_click_command(
    help="Initialize a new project"
)(
    click.option('-pj', '--project-name',
                 prompt='Project name',
                 help='Name of the project',
                 required=True
                 ),
    # Choice option with default
    # TODO include in filters for IDP projects
    click.option('-t', '--project-type',
                 type=click.Choice(["terraform", "tofu",
                                    "cdkv2",
                                    "terraform_module",
                                    "terragrunt_project",
                                    "custom", ], case_sensitive=False
                                   ),
                 default='terraform',
                 show_default=True,
                 help='Type of project to create'),
    click.option("-sp",
                 "--setup_conf",
                 help='Setup .thothcf.toml for thothctl configuration file"',
                 is_flag=True,
                 default=False
                 ),

    click.option("-vcss",
                 "--version-control-systems-service",
                 default="azure_repos",
                 type=click.Choice(['azure_repos'], case_sensitive=True),
                 help="The Version Control System Service for you IDP"),
    click.option(
        "-reuse",
        "--reuse",
        help="Reuse templates, pattern, PoC, projects and more from your IDP catalog",
        is_flag=True,
        default=False
    ),
    click.option('-az-org', '--az-org-name',
                 help='Azure organization name',
                 default=None
                 ),
    click.option('-r-list',
                 help='List all available templates',
                 is_flag=True,
                 default=False
                 ),
    click.option("-rm", "--rm-project",
        help="Remove project from .thothcf global local config and residual files",
        default=None,
                 )
)
