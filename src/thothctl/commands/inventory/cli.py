import importlib.util
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from click.shell_completion import CompletionItem


logger = logging.getLogger(__name__)


class InventoryCLI(click.MultiCommand):
    def list_commands(self, ctx: click.Context) -> list[str]:
        commands = []
        commands_path = Path(__file__).parent / "commands"

        try:
            for item in commands_path.iterdir():
                if item.name.endswith(".py") and not item.name.startswith("_"):
                    commands.append(item.stem)
        except Exception as e:
            logger.error(f"Error listing inventory commands: {e}")
            return []

        commands.sort()
        return commands

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        try:
            module_path = Path(__file__).parent / "commands" / f"{cmd_name}.py"

            if not module_path.exists():
                return None

            # Import the module
            module_name = f"thothctl.commands.inventory.commands.{cmd_name}"
            
            # Try to import using importlib.util first
            try:
                spec = importlib.util.spec_from_file_location(module_name, str(module_path))
                if spec is None or spec.loader is None:
                    return None

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as import_error:
                logger.error(f"Error importing module {module_name} using spec_from_file_location: {str(import_error)}")
                
                # Fallback to direct import
                try:
                    if module_name not in sys.modules:
                        __import__(module_name)
                    module = sys.modules[module_name]
                except Exception as direct_import_error:
                    logger.error(f"Error importing module {module_name} directly: {str(direct_import_error)}")
                    return None

            # Get the command
            if not hasattr(module, "cli"):
                logger.error(f"Command {cmd_name} has no 'cli' attribute")
                return None

            return module.cli

        except Exception as e:
            logger.error(f"Error loading inventory subcommand {cmd_name}: {str(e)}")
            return None

    def shell_complete(self, ctx: click.Context, incomplete: str):
        """
        Support shell completion for subcommands.
        """
        commands = self.list_commands(ctx)
        return [CompletionItem(cmd) for cmd in commands if cmd.startswith(incomplete)]


@click.group(cls=InventoryCLI)
@click.pass_context
def cli(ctx):
    """Create Inventory for the iac composition."""
    pass
