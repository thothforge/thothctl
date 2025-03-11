from contextlib import contextmanager
from pathlib import Path

import click

import os

from ....core.commands import ClickCommand
from ....services.project.cleanup.clean_project import cleanup_project


class CleanUpProjectCommand(ClickCommand):
    """Command to initialize a new project"""

    def validate(self, **kwargs) -> bool:
        """Validate project initialization parameters"""

        return True

    def execute(
        self, clean_additional_files: str, clean_additional_folders: str, **kwargs
    ) -> None:
        """Execute Environment initialization"""
        ctx = click.get_current_context()
        debug = ctx.obj.get("DEBUG")
        code_directory = ctx.obj.get("CODE_DIRECTORY")
        self._clean_up_project(
            code_directory, clean_additional_files, clean_additional_folders
        )

    def _clean_up_project(
        self,
        code_directory: str,
        clean_additional_files: str,
        clean_additional_folders: str,
    ) -> None:
        """Initialize the project using the create_project function"""
        cleanup_project(
            directory=code_directory,
            additional_files=clean_additional_files,
            additional_folders=clean_additional_folders,
        )

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
cli = CleanUpProjectCommand.as_click_command(
    help="Clean Up residual files and directories from your project"
)(
    click.option(
        "-cfs",
        "--clean-additional-files",
        help="Add folders file to clean specify:  -cfs file_1,file_2",
        default=None,
    ),
    click.option(
        "-cfd",
        "--clean-additional-folders",
        help="Add folders file to clean specify:  -cfd folder_1,folder_2",
        default=None,
    ),
)
