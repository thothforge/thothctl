from pathlib import Path
from typing import Optional, List

import click
from click.shell_completion import CompletionItem

from ....core.commands import ClickCommand
from ....services.init.space.space import SpaceService
from ....core.cli_ui import CliUI


class SpaceInitCommand(ClickCommand):
    """Command to initialize a new space"""

    def __init__(self):
        super().__init__()
        self.space_service = SpaceService(self.logger)
        self.ui = CliUI()

    def validate(self, space_name: str, **kwargs) -> bool:
        """Validate space initialization parameters"""
        if not space_name or not space_name.strip():
            self.ui.print_error("Space name is required and cannot be empty")
            raise ValueError("Space name is required and cannot be empty")
        return True

    def execute(
        self,
        space_name: str,
        description: Optional[str] = None,
        vcs_provider: str = "azure_repos",
        terraform_registry: str = "https://registry.terraform.io",
        terraform_auth: str = "none",
        orchestration_tool: str = "terragrunt",
        **kwargs,
    ) -> None:
        """Execute space initialization"""
        space_name = space_name.strip()
        
        self.ui.print_info(f"🌌 Creating new space: {space_name}")
        
        # Initialize space
        self.space_service.initialize_space(
            space_name=space_name,
            description=description,
            vcs_provider=vcs_provider,
            terraform_registry=terraform_registry,
            terraform_auth=terraform_auth,
            orchestration_tool=orchestration_tool
        )
        
        self.ui.print_success(f"✨ Space '{space_name}' is ready to use!")
        self.ui.print_info(f"💡 You can now create projects in this space with:")
        self.ui.print_info(f"   thothctl init project --project-name <name> --space {space_name}")

    def get_completions(
            self, ctx: click.Context, args: List[str], incomplete: str
    ) -> List[click.shell_completion.CompletionItem]:
        """
        Provide context-aware autocompletion
        """
        # Import CompletionItem here to avoid circular imports
        from click.shell_completion import CompletionItem
        
        # Define subcommands and their options
        completions = {
            'create': {
                '--space-name': ['development', 'staging', 'production'],
                '--description': ['Development environment', 'Staging environment', 'Production environment'],
                '--vcs-provider': ['azure_repos', 'github', 'gitlab'],
                '--terraform-auth': ['none', 'token', 'env_var'],
                '--orchestration-tool': ['terragrunt', 'terramate', 'none']
            }
        }

        # If no args provided, suggest subcommands
        if not args:
            return [CompletionItem(cmd, help=f"Command to {cmd} space")
                    for cmd in completions.keys()
                    if cmd.startswith(incomplete)]

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
cli = SpaceInitCommand.as_click_command(help="Initialize a new space")(
    click.option(
        "-s",
        "--space-name",
        prompt="Space name",
        help="Name of the space",
        required=True,
    ),
    click.option(
        "-d",
        "--description",
        help="Description of the space",
        default=None,
    ),
    click.option(
        "-vcs",
        "--vcs-provider",
        help="Version Control System provider",
        type=click.Choice(["azure_repos", "github", "gitlab"], case_sensitive=True),
        default="azure_repos",
    ),
    click.option(
        "-tr",
        "--terraform-registry",
        help="Terraform registry URL",
        default="https://registry.terraform.io",
    ),
    click.option(
        "-ta",
        "--terraform-auth",
        help="Terraform registry authentication method",
        type=click.Choice(["none", "token", "env_var"], case_sensitive=True),
        default="none",
    ),
    click.option(
        "-ot",
        "--orchestration-tool",
        help="Default orchestration tool for the space",
        type=click.Choice(["terragrunt", "terramate", "none"], case_sensitive=True),
        default="terragrunt",
    ),
)
