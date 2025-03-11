from pathlib import Path

import click

from ....core.commands import ClickCommand
from ....services.project.convert.conversion_service import ProjectConversionService
from ....services.project.convert.project_converter import ProjectConversionConfig


class ConvertProjectCommand(ClickCommand):
    """Command to convert projects between different formats."""

    def __init__(self):
        super().__init__()

    def validate(self, **kwargs) -> bool:
        """Validate conversion parameters."""
        return True

    def execute(
        self,
        make_terramate_stacks: bool = False,
        make_project: bool = False,
        make_template: bool = False,
        template_project_type: str = None,
        **kwargs,
    ) -> None:
        """Execute project conversion."""
        try:
            ctx = click.get_current_context()
            config = ProjectConversionConfig(
                code_directory=Path(ctx.obj.get("CODE_DIRECTORY")),
                debug=ctx.obj.get("DEBUG"),
                project_type=template_project_type,
                make_project=make_project,
                make_template=make_template,
                make_terramate=make_terramate_stacks,
            )

            ProjectConversionService().convert_project(config)

        except Exception as e:
            self.logger.error(f"Conversion failed: {e}")
            raise click.ClickException(str(e))

    def pre_execute(self, **kwargs) -> None:
        self.logger.debug("Starting conversion process")

    def post_execute(self, **kwargs) -> None:
        self.logger.debug("Conversion process completed")


# Create the Click command
cli = ConvertProjectCommand.as_click_command(
    help="Convert project to template, template to project or between IaC frameworks (Terragrunt, Terramate)"
)(
    click.option(
        "-tm",
        "--make-terramate-stacks",
        help="Create terramate stack for advance deployments",
        is_flag=True,
        default=False,
    ),
    click.option(
        "-mpro",
        "--make-project",
        help="Create project from template",
        is_flag=True,
        default=False,
    ),
    click.option(
        "-mtem",
        "--make-template",
        help="Create template from project",
        is_flag=True,
        default=False,
    ),
    click.option(
        "-tpt",
        "--template-project-type",
        help="Project type according to Internal Developer Portal",
        type=click.Choice(["terraform", "tofu", "cdkv2"], case_sensitive=True),
        default="terraform",
    ),
    click.option(
        "-br", "--branch-name", help="Branch name for terramate stacks", default="main"
    ),
)
