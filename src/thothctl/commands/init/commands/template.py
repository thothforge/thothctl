from typing import Optional

import click

from ....core.commands import ClickCommand
from ....config.template_config import TemplateConfig
from ....core.cli_ui import CliUI


class TemplateConfigCommand(ClickCommand):
    """Command to manage template configurations"""

    def __init__(self):
        super().__init__()
        self.config = TemplateConfig()
        self.ui = CliUI()

    def _execute(
        self,
        project_type: str,
        template_url: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Execute template configuration management"""
        
        if template_url:
            # Set template URL
            self.config.set_template_url(project_type, template_url)
            self.ui.print_success(f"✅ Template URL set for {project_type}: {template_url}")
        else:
            # Get template URL
            url = self.config.get_template_url(project_type)
            if url:
                self.ui.print_info(f"Template URL for {project_type}: {url}")
            else:
                self.ui.print_warning(f"No custom template URL configured for {project_type}")
                self.ui.print_info("💡 Use 'thothctl list templates' to see available templates")


# Create the Click command
cli = TemplateConfigCommand.as_click_command(help="Configure custom template repository URLs")(
    click.option(
        "-pt",
        "--project-type",
        required=True,
        type=click.Choice(
            [
                "terraform",
                "terraform-terragrunt",
                "terragrunt",
                "terraform_module",
                "tofu",
                "cdkv2",
                "cdkv2-typescript",
                "cdkv2-python",
                "cdkv2-java",
                "cdkv2-csharp",
                "cdkv2-go",
                "custom",
            ],
            case_sensitive=True,
        ),
        help="Type of project template to configure",
    ),
    click.option(
        "-url",
        "--template-url",
        help="GitHub repository URL for the template",
        default=None,
    ),
)
