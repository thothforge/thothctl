from pathlib import Path

import click

from ...core.commands import ClickCommand
from ...services.project.cleanup.clean_space import remove_space


class RemoveSpaceCommand(ClickCommand):
    """Command to remove a space and optionally its projects"""

    def validate(self, space_name: str, **kwargs) -> bool:
        """Validate space removal parameters"""
        if not space_name or not space_name.strip():
            raise ValueError("Space name is required and cannot be empty")
        return True

    def execute(self, space_name: str, remove_projects: bool = False, **kwargs) -> None:
        """Execute space removal"""
        space_name = space_name.strip()
        self._clean_up_space(space_name=space_name, remove_projects=remove_projects)

    def _clean_up_space(self, space_name: str, remove_projects: bool) -> None:
        """Remove the space and optionally its projects"""
        remove_space(space_name=space_name, remove_projects=remove_projects)

    def pre_execute(self, **kwargs) -> None:
        self.logger.debug("Starting space cleanup")

    def post_execute(self, **kwargs) -> None:
        self.logger.debug("Space cleanup completed")


# Create the Click command
cli = RemoveSpaceCommand.as_click_command(
    help="Remove a space and optionally its associated projects"
)(
    click.option(
        "-s",
        "--space-name",
        prompt="Space name",
        help="Name of the space to remove",
        required=True,
    ),
    click.option(
        "-rp",
        "--remove-projects",
        help="Remove all projects associated with this space",
        is_flag=True,
        default=False,
    ),
)
