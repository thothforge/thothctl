from contextlib import contextmanager
from pathlib import Path

import click

import os

from ...core.commands import ClickCommand
from ...services.project.cleanup.clean_project import remove_projects


class RemoveProjectCommand(ClickCommand):
    """Command to initialize a new project"""

    def validate(self, **kwargs) -> bool:
        """Validate project initialization parameters"""

        return True

    def execute(self, project_name: str, **kwargs) -> None:
        """Execute Environment initialization"""
        ctx = click.get_current_context()
        debug = ctx.obj.get("DEBUG")
        self._clean_up_project(project_name=project_name)

    def _clean_up_project(self, project_name: str) -> None:
        """Initialize the project using the create_project function"""
        remove_projects(project_name=project_name)

    def pre_execute(self, **kwargs) -> None:
        self.logger.debug("Starting project cleanup")

    def post_execute(self, **kwargs) -> None:
        self.logger.debug("Project cleanup completed")

    @contextmanager
    def _change_directory(self, path: Path):
        """Safely change directory and return to original"""
        original_dir = Path.cwd()
        try:
            os.chdir(path)
            yield
        finally:
            os.chdir(original_dir)


# Create the Click command
cli = RemoveProjectCommand.as_click_command(
    help="Remove project from local .thothcf tracking file"
)(
    click.option(
        "-pj",
        "--project-name",
        help="Project Name to delete",
        default=None,
    )
)
