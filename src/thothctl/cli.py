"""thothctl main cli."""

import importlib.util
import logging
import os
import sys
from functools import wraps
from importlib.metadata import version
from pathlib import Path
from typing import Optional

import click

from .utils.banner import get_banner


def global_options(f):
    @click.option("--debug", is_flag=True, help="Enable debug mode (most verbose)")
    @click.option(
        "--verbose", "-v", is_flag=True, help="Enable verbose mode (show info messages)"
    )
    @click.option(
        "-d",
        "--code-directory",
        type=click.Path(exists=True),
        help="Configuration file path",
        default=".",
    )
    @wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapper


class ThothCLI(click.MultiCommand):
    def list_commands(self, ctx: click.Context) -> list[str]:
        commands = []
        commands_path = Path(__file__).parent / "commands"

        try:
            for item in commands_path.iterdir():
                if item.is_dir() and not item.name.startswith("_"):
                    commands.append(item.name.replace("_", "-"))
        except Exception as e:
            click.echo(f"Error listing commands: {e}", err=True)
            return []

        commands.sort()
        return commands

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        try:
            # Support both hyphens and underscores (e.g. ai-review -> ai_review)
            normalized = cmd_name.replace("-", "_")
            module_path = Path(__file__).parent / "commands" / normalized / "cli.py"

            if not module_path.exists():
                return None

            spec = importlib.util.spec_from_file_location(
                f"thothctl.commands.{normalized}.cli", str(module_path)
            )
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return getattr(module, "cli", None)

        except Exception as e:
            click.echo(f"Error loading command {cmd_name}: {e}", err=True)
            return None

    COMMAND_CATEGORIES = {
        "DevSecOps Workflow": ["workflow", "scan", "check"],
        "Project Lifecycle": ["init", "generate", "inventory", "project"],
        "Governance": ["space", "dashboard", "ai-review"],
        "Utilities": ["list", "remove", "document", "upgrade", "mcp", "quickstart"],
    }

    def format_commands(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        """Override to show commands in categorized groups."""
        commands = {}
        for name in self.list_commands(ctx):
            cmd = self.get_command(ctx, name)
            if cmd and not cmd.hidden:
                commands[name] = cmd

        if not commands:
            return

        # Render each category
        for category, cmd_names in self.COMMAND_CATEGORIES.items():
            rows = []
            for name in cmd_names:
                if name in commands:
                    help_text = commands[name].get_short_help_str(limit=50)
                    rows.append((name, help_text))
            if rows:
                with formatter.section(category):
                    formatter.write_dl(rows)

        # Uncategorized commands (safety net for new commands)
        categorized = {n for names in self.COMMAND_CATEGORIES.values() for n in names}
        uncategorized = [
            (n, commands[n].get_short_help_str(limit=50))
            for n in sorted(commands)
            if n not in categorized
        ]
        if uncategorized:
            with formatter.section("Other"):
                formatter.write_dl(uncategorized)


@click.command(cls=ThothCLI)
@click.version_option(
    version=version("thothctl"),
    prog_name="thothctl",
    message=get_banner() + "\n   Version: %(version)s\n",
    help="Show the version and exit.",
)
@global_options
@click.pass_context
def cli(ctx, debug, verbose, code_directory):
    """ThothForge CLI - AI-Powered Infrastructure Lifecycle CLI"""
    """Thoth CLI tool"""
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug
    ctx.obj["VERBOSE"] = verbose
    ctx.obj["CODE_DIRECTORY"] = code_directory

    # Initialize telemetry for non-interactive use
    if not sys.stdin.isatty():
        from .core.telemetry import telemetry

        telemetry.initialize()

    # Configure logging based on flags
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        # Also set environment variable for child processes
        os.environ["THOTHCTL_DEBUG"] = "true"
    elif verbose:
        logging.getLogger().setLevel(logging.INFO)
        os.environ["THOTHCTL_VERBOSE"] = "true"
    else:
        # Keep it clean - only show warnings and errors
        logging.getLogger().setLevel(logging.WARNING)


if __name__ == "__main__":
    cli()
