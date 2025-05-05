import click

from ....core.commands import ClickCommand
from ....common.common import print_list_projects


class ListProjectsCommand(ClickCommand):
    """Command to list all projects managed by thothctl"""

    def validate(self, **kwargs) -> bool:
        """Validate list projects parameters"""
        return True

    def execute(self, show_space: bool = True, **kwargs) -> None:
        """Execute list projects command"""
        print_list_projects(show_space=show_space)

    def pre_execute(self, **kwargs) -> None:
        self.logger.debug("Starting list projects")

    def post_execute(self, **kwargs) -> None:
        self.logger.debug("List projects completed")


# Create the Click command
cli = ListProjectsCommand.as_click_command(
    help="List all projects managed by thothctl"
)(
    click.option(
        "-s",
        "--show-space",
        help="Show space information for each project",
        is_flag=True,
        default=True,
    ),
)
