import getpass
from pathlib import Path
from typing import Optional

import click

from ....core.commands import ClickCommand
from ....services.init.project.project import ProjectService


class ProjectInitCommand(ClickCommand):
    """Command to initialize a new project"""

    def __init__(self):
        super().__init__()
        self.project_service = ProjectService(self.logger)

    def validate(self, project_name: str, **kwargs) -> bool:
        """Validate project initialization parameters"""
        if not project_name or not project_name.strip():
            raise ValueError("Project name is required and cannot be empty")
        return True

    def execute(
        self,
        project_name: str,
        setup_conf: bool,
        version_control_system_service: str = ProjectService.DEFAULT_VCS_SERVICE,
        az_org_name: Optional[str] = None,
        reuse: bool = False,
        r_list: bool = False,
        project_type: str = "terraform",
        **kwargs,
    ) -> None:
        """Execute project initialization"""
        project_name = project_name.strip()
        project_path = Path(f"./{project_name}")

        # Initialize project
        self.project_service.initialize_project(project_name, project_type, reuse=reuse)

        # Setup configuration if requested
        if setup_conf:
            self.project_service.setup_project_config(project_name)

        # Setup Azure repos if conditions are met
        if self._should_setup_azure_repos(
            version_control_system_service, reuse, az_org_name
        ):
            pat = self._get_azure_pat()
            self.project_service.setup_azure_repos(
                project_name=project_name,
                project_path=project_path,
                az_org_name=az_org_name,
                r_list=r_list,
                pat=pat,
            )

    @staticmethod
    def _should_setup_azure_repos(
        vcs_service: str, reuse: bool, az_org_name: Optional[str]
    ) -> bool:
        """Check if Azure Repos setup should be performed"""
        return all(
            [
                vcs_service == ProjectService.DEFAULT_VCS_SERVICE,
                reuse,
                az_org_name is not None,
            ]
        )

    @staticmethod
    def _get_azure_pat() -> str:
        """Securely get Azure Personal Access Token"""
        print("Pass your Personal Access Token")
        return getpass.getpass()


# Create the Click command
cli = ProjectInitCommand.as_click_command(help="Initialize a new project")(
    click.option(
        "-pj",
        "--project-name",
        prompt="Project name",
        help="Name of the project",
        required=True,
    ),
    click.option(
        "-t",
        "--project-type",
        type=click.Choice(
            [
                "terraform",
                "tofu",
                "cdkv2",
                "terraform_module",
                "terragrunt_project",
                "custom",
            ],
            case_sensitive=False,
        ),
        default="terraform",
        show_default=True,
        help="Type of project to create",
    ),
    click.option(
        "-sp",
        "--setup_conf",
        help="Setup .thothcf.toml for thothctl configuration file",
        is_flag=True,
        default=False,
    ),
    click.option(
        "-vcss",
        "--version-control-systems-service",
        default="azure_repos",
        type=click.Choice(["azure_repos"], case_sensitive=True),
        help="The Version Control System Service for you IDP",
    ),
    click.option(
        "-reuse",
        "--reuse",
        help="Reuse templates, pattern, PoC, projects and more from your IDP catalog",
        is_flag=True,
        default=False,
    ),
    click.option(
        "-az-org", "--az-org-name", help="Azure organization name", default=None
    ),
    click.option(
        "-r-list", help="List all available templates", is_flag=True, default=False
    ),
)
