import click

from ....core.commands import ClickCommand
from ....common.common import print_list_spaces


class ListSpacesCommand(ClickCommand):
    """Command to list all spaces managed by thothctl"""

    def validate(self, **kwargs) -> bool:
        """Validate list spaces parameters"""
        return True

    def execute(self, **kwargs) -> None:
        """Execute list spaces command"""
        print_list_spaces()

    def pre_execute(self, **kwargs) -> None:
        self.logger.debug("Starting list spaces")

    def post_execute(self, **kwargs) -> None:
        self.logger.debug("List spaces completed")


# Create the Click command
cli = ListSpacesCommand.as_click_command(
    help="List all spaces managed by thothctl"
)()
