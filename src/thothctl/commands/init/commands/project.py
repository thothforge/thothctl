import getpass
from pathlib import Path
from typing import Optional, List, Any

import click
from click.shell_completion import CompletionItem

from ....core.commands import ClickCommand
from ....services.init.project.project import ProjectService
from ....core.cli_ui import CliUI
from ....common.common import get_space_vcs_provider


class ProjectInitCommand(ClickCommand):
    """Command to initialize a new project"""

    def __init__(self):
        super().__init__()
        self.project_service = ProjectService(self.logger)
        self.ui = CliUI()

    def validate(self, project_name: str, **kwargs) -> bool:
        """Validate project initialization parameters"""
        if not project_name or not project_name.strip():
            self.ui.print_error("Project name is required and cannot be empty")
            raise ValueError("Project name is required and cannot be empty")
        return True

    def execute(
        self,
        project_name: str,
        setup_conf: bool,
        version_control_system_service: str = ProjectService.DEFAULT_VCS_SERVICE,
        az_org_name: Optional[str] = None,
        github_username: Optional[str] = None,
        reuse: bool = False,
        r_list: bool = False,
        project_type: str = "terraform",
        space: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Execute project initialization"""
        project_name = project_name.strip()
        project_path = Path(f"./{project_name}")

        self.ui.print_info(f"🚀 Initializing project: {project_name}")
        
        # If space is provided, show info and get VCS provider
        vcs_provider = version_control_system_service
        if space:
            self.ui.print_info(f"🌌 Using space: {space}")
            space_vcs = get_space_vcs_provider(space)
            if space_vcs:
                vcs_provider = space_vcs
                self.ui.print_info(f"🔄 Using VCS provider from space: {vcs_provider}")
        
        # Initialize project
        with self.ui.status_spinner("🏗️ Creating project structure..."):
            self.project_service.initialize_project(project_name, project_type=project_type, reuse=reuse, space=space)

        # Setup configuration if requested
        if setup_conf:
            with self.ui.status_spinner("📝 Setting up project configuration..."):
                self.project_service.setup_project_config(project_name, space=space)

        # Setup version control if reuse is enabled
        if reuse:
            # Pass the appropriate parameters based on VCS provider
            vcs_params = {}
            if vcs_provider == "azure_repos" and az_org_name:
                vcs_params["az_org_name"] = az_org_name
            elif vcs_provider == "github" and github_username:
                vcs_params["github_username"] = github_username
            
            with self.ui.status_spinner("🔄 Setting up version control..."):
                self.project_service.setup_azure_repos(project_name, **vcs_params)
        
        self.ui.print_success(f"✨ Project '{project_name}' initialized successfully!")

    def get_completions(self, ctx: click.Context, args: List[str], incomplete: str) -> List[click.shell_completion.CompletionItem]:
        """
        Provide context-aware autocompletion
        """
        # Define subcommands and their options
        completions = {
            'create': {
                '--project-name': ['basic', 'advanced', 'custom'],
                '--project-type': ['python3.8', 'python3.9', 'python3.10', 'terraform', 'tofu', 'cdkv2', 'terraform_module', 'terragrunt_project', 'custom'],
                '--region': ['us-east-1', 'us-west-2', 'eu-west-1']
            },
            'delete': {
                '--force': ['true', 'false'],
                '--backup': ['true', 'false']
            }
        }

        # If no args provided, suggest subcommands
        if not args:
            return [
                CompletionItem(cmd, help=f"Command to {cmd} project")
                for cmd in completions.keys()
                if cmd.startswith(incomplete)
            ]

        # Get current subcommand
        subcommand = next((arg for arg in args if arg in completions), None)
        if not subcommand:
            return []

        # If incomplete starts with '-', suggest options for current subcommand
        if incomplete.startswith('-'):
            return [
                CompletionItem(opt, help=f"Option for {opt.lstrip('-')}")
                for opt in completions[subcommand].keys()
                if opt.startswith(incomplete)
            ]

        # If we have a current option, suggest its values
        current_option = next((arg for arg in reversed(args)
                               if arg in completions[subcommand]), None)
        if current_option:
            values = completions[subcommand][current_option]
            return [
                CompletionItem(val, help=f"Value for {current_option}")
                for val in values
                if val.startswith(incomplete)
            ]

        return []


# Create the Click command
cli = ProjectInitCommand.as_click_command(help="Initialize a new project")(
    click.option(
        "-p",
        "--project-name",
        prompt="Project name",
        help="Name of the project",
        required=True,
    ),
    click.option(
        "-pt",
        "--project-type",
        default="terraform",
        type=click.Choice(
            [
                "terraform",
                "tofu",
                "cdkv2",
                "terraform_module",
                "terragrunt_project",
                "custom",
            ],
            case_sensitive=True,
        ),
        help="Type of project to create",
    ),
    click.option(
        "-sc",
        "--setup-conf",
        is_flag=True,
        default=True,
        help="Setup project configuration",
    ),
    click.option(
        "-vcss",
        "--version-control-systems-service",
        default="azure_repos",
        type=click.Choice(["azure_repos", "github", "gitlab"], case_sensitive=True),
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
        "-az-org", 
        "--az-org-name", 
        help="Azure organization name (for Azure Repos)", 
        default=None
    ),
    click.option(
        "-gh-user", 
        "--github-username", 
        help="GitHub username or organization (for GitHub)", 
        default=None
    ),
    click.option(
        "-r-list",
        "--r-list",
        help="List all available templates", 
        is_flag=True, 
        default=False
    ),
    click.option(
        "-s",
        "--space",
        help="Space name for the project (used for loading credentials and configurations)",
        default=None,
    ),
)
