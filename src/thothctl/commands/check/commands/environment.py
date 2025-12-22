import click
from rich.console import Console

from ....core.commands import ClickCommand
from ....services.check.environment.check_environment import EnvironmentChecker


class CheckEnvironmentCommand(ClickCommand):
    """Command to check development environment tools"""

    def __init__(self):
        super().__init__()
        self.console = Console()
        self.environment_checker = EnvironmentChecker()

    def validate(self, **kwargs) -> bool:
        """Validate environment check parameters"""
        return True

    def _execute(self, **kwargs) -> None:
        """Execute environment check"""
        results = self.environment_checker.check_environment()
        
        # Exit with error code if tools are missing (for CI/CD integration)
        if results["missing"]:
            exit(1)


# Create the Click command
cli = CheckEnvironmentCommand.as_click_command(
    help="Check if development environment tools are installed and available"
)()
