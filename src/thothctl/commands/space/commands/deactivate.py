"""Deactivate the current active space."""

from pathlib import Path

from ....core.cli_ui import CliUI
from ....core.commands import ClickCommand

ACTIVE_SPACE_FILE = Path.home() / ".thothcf" / "active_space"


class DeactivateSpaceCommand(ClickCommand):
    """Command to deactivate the current active space."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        return True

    def _execute(self, **kwargs) -> None:
        if not ACTIVE_SPACE_FILE.exists():
            self.ui.print_info("No active space to deactivate")
            return

        space_name = ACTIVE_SPACE_FILE.read_text(encoding="utf-8").strip()
        ACTIVE_SPACE_FILE.unlink()
        self.ui.print_success(f"Space '{space_name}' deactivated")


cli = DeactivateSpaceCommand.as_click_command(
    help="Deactivate the current active space"
)()
