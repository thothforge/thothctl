"""Space management CLI."""
import importlib.util
import logging
from pathlib import Path
from typing import Optional

import click

logger = logging.getLogger(__name__)


class SpaceCLI(click.MultiCommand):
    def list_commands(self, ctx: click.Context) -> list[str]:
        commands = []
        commands_path = Path(__file__).parent / "commands"
        try:
            for item in commands_path.iterdir():
                if item.name.endswith(".py") and not item.name.startswith("_"):
                    commands.append(item.stem)
        except Exception as e:
            logger.error(f"Error listing space commands: {e}")
            return []
        commands.sort()
        return commands

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        try:
            module_path = Path(__file__).parent / "commands" / f"{cmd_name}.py"
            if not module_path.exists():
                return None
            spec = importlib.util.spec_from_file_location(
                f"thothctl.commands.space.commands.{cmd_name}", str(module_path)
            )
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, "cli", None)
        except Exception as e:
            logger.error(f"Error loading space subcommand {cmd_name}: {e}")
            return None


@click.group(cls=SpaceCLI)
def cli():
    """Manage spaces - activate, update, and configure IDP contexts"""
    pass
