# src/thothctl/commands/init/cli.py
import click
from pathlib import Path
import importlib.util
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ScanCLI(click.MultiCommand):
    def list_commands(self, ctx: click.Context) -> list[str]:
        commands = []
        commands_path = Path(__file__).parent / "commands"

        try:
            for item in commands_path.iterdir():
                if item.name.endswith('.py') and not item.name.startswith('_'):
                    commands.append(item.stem)
        except Exception as e:
            logger.error(f"Error listing init commands: {e}")
            return []

        commands.sort()
        return commands

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        try:
            module_path = Path(__file__).parent / "commands" / f"{cmd_name}.py"

            if not module_path.exists():
                return None

            # Import the module
            module_name = f"thothctl.commands.project.commands.{cmd_name}"
            spec = importlib.util.spec_from_file_location(module_name, str(module_path))
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the command
            if not hasattr(module, 'cli'):
                logger.error(f"Command {cmd_name} has no 'cli' attribute")
                return None

            return module.cli

        except Exception as e:
            logger.error(f"Error loading project subcommand {cmd_name}: {str(e)}")
            return None


@click.group(cls=ScanCLI)
@click.pass_context
def cli(ctx):
    """Scan IaC project and create report with summary.
    You can send to AI to suggest the recommendations and fix your code"""
    pass

