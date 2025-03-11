import importlib.util
import logging
from pathlib import Path

import click


logger = logging.getLogger(__name__)


class ScanCLI(click.Group):
    """Custom Click Group class for scan commands."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = {}
        self._load_commands()

    def _load_commands(self):
        """Load all available commands from the commands directory."""
        commands_path = Path(__file__).parent / "commands"

        try:
            for item in commands_path.iterdir():
                if item.name.endswith(".py") and not item.name.startswith("_"):
                    command_name = item.stem
                    self.commands[command_name] = item
        except Exception as e:
            logger.error(f"Error loading  scan subcommands: {e}")

    def list_commands(self, ctx):
        """Return sorted list of commands."""
        return sorted(self.commands.keys())

    def get_command(self, ctx, cmd_name):
        """Get a specific command by name."""
        try:
            module_path = Path(__file__).parent / "commands" / f"{cmd_name}.py"

            if not module_path.exists():
                return None

            module_name = f"thothctl.commands.scan.commands.{cmd_name}"

            spec = importlib.util.spec_from_file_location(module_name, str(module_path))
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Get the command
            if not hasattr(module, "cli"):
                logger.error(f"Command {cmd_name} has no 'cli' attribute")
                return None

            return module.cli

        except Exception as e:
            logger.error(f"Error loading scan subcommand {cmd_name}: {str(e)}")
            return None


@click.group(cls=ScanCLI)
@click.pass_context
def cli(ctx):
    """Scan infrastructure code for security issues. Integrate with AI to analyze and suggest corrections"""
    pass
