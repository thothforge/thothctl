"""AI Review CLI command group."""
import importlib.util
import logging
from pathlib import Path

import click

logger = logging.getLogger(__name__)


class AIReviewCLI(click.Group):
    """Custom Click Group for ai-review commands."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = {}
        self._load_commands()

    def _load_commands(self):
        commands_path = Path(__file__).parent / "commands"
        try:
            for item in commands_path.iterdir():
                if item.name.endswith(".py") and not item.name.startswith("_"):
                    # Use hyphens in command names for consistency
                    self.commands[item.stem.replace("_", "-")] = item
        except Exception as e:
            logger.error(f"Error loading ai-review subcommands: {e}")

    def list_commands(self, ctx):
        return sorted(self.commands.keys())

    def get_command(self, ctx, cmd_name):
        try:
            # Normalize: accept both hyphens and underscores
            normalized = cmd_name.replace("-", "_")
            module_path = Path(__file__).parent / "commands" / f"{normalized}.py"
            if not module_path.exists():
                return None

            module_name = f"thothctl.commands.ai_review.commands.{normalized}"
            spec = importlib.util.spec_from_file_location(module_name, str(module_path))
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, "cli"):
                logger.error(f"Command {cmd_name} has no 'cli' attribute")
                return None
            return module.cli
        except Exception as e:
            logger.error(f"Error loading ai-review subcommand {cmd_name}: {e}")
            return None


@click.group(cls=AIReviewCLI, name="ai-review")
@click.pass_context
def cli(ctx):
    """AI-powered security analysis and code review for IaC."""
    pass
