from contextlib import contextmanager
from pathlib import Path

import click

import os

from ....core.commands import ClickCommand
from ....services.init.environment.install_tools import bootstrap_env


class EnvInitCommand(ClickCommand):
    """Command to initialize a new project"""

    def validate(self, **kwargs) -> bool:
        """Validate project initialization parameters"""
        return True

    def execute(self, operation_system: str, **kwargs) -> None:
        """Execute Environment initialization"""
        self._init_env(operation_system)

    def _init_env(self, operation_system: str) -> None:
        """Initialize the project using the create_project function"""
        bootstrap_env(so=operation_system)

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
cli = EnvInitCommand.as_click_command(
    help="Initialize a development environment with required tools and configurations for a new project"
)(
    click.option(
        "-os",
        "--operation-system",
        help="Install base tools for you environment",
        required=False,
        default="Linux/Debian",
        type=click.Choice(["Linux/Debian"], case_sensitive=False),
    ),
    # TODO add support to devto containers
)
