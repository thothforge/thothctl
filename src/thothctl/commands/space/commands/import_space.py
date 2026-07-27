"""Import space configuration from file or git URL."""

import click

from ....core.cli_ui import CliUI
from ....core.commands import ClickCommand
from ....services.init.space.export_import import import_space


class ImportSpaceCommand(ClickCommand):
    """Command to import a space configuration from a file or git repository."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def _execute(self, source: str, name: str, **kwargs) -> None:
        try:
            created = import_space(source, name)
            self.ui.print_success(f"Imported space '{created}' successfully")
            self.ui.print_info(
                "Run 'thothctl space activate' and configure credentials."
            )
        except ValueError as e:
            self.ui.print_error(str(e))
        except Exception as e:
            self.ui.print_error(f"Import failed: {e}")


cli = ImportSpaceCommand.as_click_command(
    help="Import space configuration from file or git URL"
)(
    click.argument("source"),
    click.option(
        "-n",
        "--name",
        default=None,
        help="Override space name (default: use name from export)",
    ),
)
