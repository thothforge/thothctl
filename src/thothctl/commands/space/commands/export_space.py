"""Export space configuration for sharing."""

import click

from ....common.common import list_spaces
from ....core.cli_ui import CliUI
from ....core.commands import ClickCommand
from ....services.init.space.export_import import export_space


class ExportSpaceCommand(ClickCommand):
    """Command to export a space configuration for team sharing."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, space_name: str, **kwargs) -> bool:
        spaces = list_spaces()
        if space_name not in spaces:
            self.ui.print_error(f"Space '{space_name}' does not exist")
            self.ui.print_info(
                f"Available spaces: {', '.join(spaces) if spaces else 'none'}"
            )
            raise ValueError(f"Space '{space_name}' does not exist")
        return True

    def _execute(self, space_name: str, output: str, **kwargs) -> None:
        path = export_space(space_name, output)
        self.ui.print_success(f"Exported space '{space_name}' to {path}")
        self.ui.print_info(
            "Credentials are NOT included. Recipients must configure their own."
        )


cli = ExportSpaceCommand.as_click_command(
    help="Export space configuration for sharing"
)(
    click.argument("space_name"),
    click.option(
        "-o",
        "--output",
        default=None,
        help="Output file path (default: <space>.space.toml)",
    ),
)
