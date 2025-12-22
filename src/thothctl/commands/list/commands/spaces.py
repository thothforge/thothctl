import click

from ....core.commands import ClickCommand
from ....common.common import print_list_spaces
from ....core.cli_ui import CliUI


class ListSpacesCommand(ClickCommand):
    """Command to list all spaces managed by thothctl"""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        """Validate list spaces parameters"""
        return True

    def _execute(self, **kwargs) -> None:
        """Execute list spaces command"""
        self.ui.print_info("🌌 Listing all available spaces:")
        print_list_spaces()

    def pre_execute(self, **kwargs) -> None:
        self.logger.debug("Starting list spaces")

    def post_execute(self, **kwargs) -> None:
        self.logger.debug("List spaces completed")
        self.ui.print_info("💡 To create a new space, use: thothctl init space")


# Create the Click command
cli = ListSpacesCommand.as_click_command(
    help="List all spaces managed by thothctl"
)()
