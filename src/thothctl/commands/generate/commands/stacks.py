import logging
from pathlib import Path

import click

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....services.generate.create_stacks.stack_service import StackService


class GenStacksCommand(ClickCommand):
    """Command to generate infrastructure stacks based on configuration"""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()
        self.stack_service = StackService(logger=self.logger)

    def validate(self, **kwargs) -> bool:
        """Validate the command inputs"""
        if not kwargs.get('config_file') and not kwargs.get('stack_name') and not kwargs.get('create_example'):
            self.ui.print_error("Either config file, stack name, or create-example flag is required")
            return False
        return True

    def _execute(self, **kwargs) -> None:
        """Execute the stacks generation command"""
        ctx = click.get_current_context()
        directory = Path(ctx.obj.get("CODE_DIRECTORY", "."))

        config_file = kwargs.get('config_file')
        stack_name = kwargs.get('stack_name')
        output_dir = Path(kwargs.get('output_dir') or directory / "stacks")
        create_example = kwargs.get('create_example')

        try:
            if create_example:
                example_path = directory / "stack-config-example.yaml"
                self.stack_service.create_example_config(example_path)
                self.ui.print_success(f"Created example configuration file: {example_path}")
                return

            if config_file:
                self.stack_service.generate_stacks_from_config(config_file, output_dir)
            else:
                modules = kwargs.get('modules', [])
                self.stack_service.generate_single_stack(stack_name, modules, output_dir)

            self.ui.print_success(f"Successfully generated stack(s) in {output_dir}")
        except Exception as e:
            self.logger.error(f"Failed to generate stacks: {e}", exc_info=True)
            self.ui.print_error(f"Failed to generate stacks: {e}")
            raise click.Abort()


# Create the Click command
cli = GenStacksCommand.as_click_command(
    help="Generate infrastructure stacks based on configuration"
)(
    click.option(
        "-c",
        "--config-file",
        help="Path to YAML configuration file defining stacks and modules",
        type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    ),
    click.option(
        "-s",
        "--stack-name",
        help="Name of the stack to generate (when not using config file)",
    ),
    click.option(
        "-m",
        "--modules",
        help="Comma-separated list of modules to include in the stack",
        callback=lambda ctx, param, value: value.split(",") if value else [],
    ),
    click.option(
        "-o",
        "--output-dir",
        help="Directory where stacks will be generated",
        type=click.Path(file_okay=False),
    ),
    click.option(
        "--create-example",
        is_flag=True,
        help="Create an example stack configuration file",
        default=False,
    ),
)
