"""Command to initialize a new space for the Internal Developer Platform."""
import click
import logging
from pathlib import Path
from typing import List, Optional

from ....core.commands import ClickCommand
from ....services.init.space.space_service import SpaceService


class SpaceInitCommand(ClickCommand):
    """Command to initialize a new space for the Internal Developer Platform."""

    def __init__(self):
        super().__init__()
        self.space_service = SpaceService(self.logger)

    def validate(self, space_name: str, **kwargs) -> bool:
        """Validate space initialization parameters.
        
        Args:
            space_name: Name of the space
            **kwargs: Additional parameters
            
        Returns:
            True if validation passes
            
        Raises:
            ValueError: If validation fails
        """
        if not space_name or not space_name.strip():
            raise ValueError("Space name is required and cannot be empty")
        return True

    def execute(
        self,
        space_name: str,
        version_control_system_service: str = SpaceService.DEFAULT_VCS_SERVICE,
        ci: str = SpaceService.DEFAULT_CI_SYSTEM,
        description: str = "",
        terraform_registry: str = "https://registry.terraform.io",
        **kwargs,
    ) -> None:
        """Execute space initialization.
        
        Args:
            space_name: Name of the space
            version_control_system_service: Version control system to use
            ci: CI/CD system to use
            description: Description of the space
            terraform_registry: URL of the Terraform registry
            **kwargs: Additional parameters
        """
        space_name = space_name.strip()
        
        # Check if space already exists
        if self.space_service.get_space(space_name):
            if click.confirm(f"Space '{space_name}' already exists. Do you want to overwrite it?", default=False):
                self.logger.info(f"Overwriting existing space: {space_name}")
                force = True
            else:
                self.logger.info("Space creation cancelled.")
                return
        else:
            force = False
        
        # Initialize space
        space_config = self.space_service.initialize_space(
            space_name=space_name,
            vcs=version_control_system_service,
            ci=ci,
            description=description,
            terraform_registry=terraform_registry,
            force=force
        )
        
        # Display success message
        config_path = self.space_service.config_manager._get_space_config_path(space_name)
        click.echo(f"Space '{space_name}' created successfully!")
        click.echo(f"Configuration file: {config_path}")
        
        # Display next steps
        click.echo("\nNext steps:")
        click.echo("  1. Create a project in this space:")
        click.echo(f"     thothctl init project -sn {space_name} -pn my-project")
        click.echo("  2. Set up your development environment:")
        click.echo(f"     thothctl init env -sn {space_name}")

    def get_completions(
        self, ctx: click.Context, args: List[str], incomplete: str
    ) -> List[tuple]:
        """
        Provide context-aware autocompletion.
        
        Args:
            ctx: Click context
            args: Command arguments
            incomplete: Current incomplete argument
            
        Returns:
            List of completion tuples (completion, description)
        """
        completions = {
            '--version-control-system-service': [
                ('azure_repos', 'Azure DevOps Repos'),
                ('github', 'GitHub'),
                ('gitlab', 'GitLab'),
                ('bitbucket', 'Bitbucket')
            ],
            '--ci': [
                ('github-actions', 'GitHub Actions'),
                ('gitlab-ci', 'GitLab CI'),
                ('azure-pipelines', 'Azure Pipelines'),
                ('jenkins', 'Jenkins'),
                ('none', 'No CI/CD')
            ],
            '--terraform-registry': [
                ('https://registry.terraform.io', 'Public Terraform Registry'),
                ('https://terraform.internal.example.com', 'Example Internal Registry')
            ],
            '--space-name': []  # No specific completions for space name
        }
        
        # Check if we're completing an option
        for param in ctx.command.params:
            if param.opts[0].startswith(incomplete) or param.opts[1].startswith(incomplete):
                return [(opt, param.help) for opt in param.opts]
        
        # Check if we're completing an option value
        for arg in args:
            if arg in completions and incomplete:
                return [
                    (value, desc) 
                    for value, desc in completions[arg] 
                    if value.startswith(incomplete)
                ]
        
        return []


# Create the Click command using the ClickCommand class
cli = SpaceInitCommand.as_click_command(name="space", help="Initialize space for your IDP")(
    click.option("-sn", "--space-name", help="The space name", required=True),
    click.option(
        "-vcss",
        "--version-control-system-service",
        default="azure_repos",
        type=click.Choice(["azure_repos", "github", "gitlab", "bitbucket"], case_sensitive=True),
        help="The Version Control System Service for your IDP",
    ),
    click.option(
        "--ci",
        type=click.Choice(
            ["github-actions", "gitlab-ci", "azure-pipelines", "jenkins", "none"],
            case_sensitive=False,
        ),
        default="none",
        help="CI/CD tool to configure",
    ),
    click.option(
        "--description",
        help="Description of the space",
        default="",
    ),
    click.option(
        "--terraform-registry",
        help="URL of the Terraform registry",
        default="https://registry.terraform.io",
    ),
)
