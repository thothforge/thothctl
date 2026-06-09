"""Activate a space as the current context."""
from pathlib import Path

import click

from ....common.common import list_spaces
from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI


ACTIVE_SPACE_FILE = Path.home() / ".thothcf" / "active_space"


class ActivateSpaceCommand(ClickCommand):
    """Command to set a space as the active context."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, space_name: str, **kwargs) -> bool:
        spaces = list_spaces()
        if space_name not in spaces:
            self.ui.print_error(f"Space '{space_name}' does not exist")
            self.ui.print_info(f"Available spaces: {', '.join(spaces) if spaces else 'none'}")
            raise ValueError(f"Space '{space_name}' does not exist")
        return True

    def _execute(self, space_name: str, **kwargs) -> None:
        ACTIVE_SPACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        ACTIVE_SPACE_FILE.write_text(space_name, encoding="utf-8")
        self.ui.print_success(f"🌐 Active space set to '{space_name}'")
        self.ui.print_info("New projects will use this space by default unless --space is specified.")


cli = ActivateSpaceCommand.as_click_command(help="Set a space as the active context")(
    click.argument("space_name"),
)
