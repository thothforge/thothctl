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

    # Check for newer version (non-blocking, cached)
    _check_version_freshness()

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


def _check_version_freshness():
    """Check if a newer version is available (cached, non-blocking).

    Uses a cache file (~/.thothcf/.version_check) to avoid hitting PyPI
    on every invocation. Checks at most once every 24 hours.
    """
    import json
    import time

    cache_file = Path.home() / ".thothcf" / ".version_check"
    cache_ttl = 86400  # 24 hours

    try:
        current = version("thothctl")

        # Check cache first
        if cache_file.exists():
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            if time.time() - cache.get("timestamp", 0) < cache_ttl:
                latest = cache.get("latest")
                if latest and latest != current:
                    _show_upgrade_hint(current, latest)
                return

        # Fetch latest from PyPI (with short timeout)
        import requests

        resp = requests.get(
            "https://pypi.org/pypi/thothctl/json",
            timeout=3,
        )
        if resp.status_code == 200:
            latest = resp.json().get("info", {}).get("version", current)

            # Cache the result
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps({"latest": latest, "timestamp": time.time()}),
                encoding="utf-8",
            )

            if latest != current and _is_newer(latest, current):
                _show_upgrade_hint(current, latest)

    except Exception:
        # Never let version check break the CLI
        pass


def _show_upgrade_hint(current: str, latest: str):
    """Show a one-line upgrade hint in stderr."""
    import sys

    sys.stderr.write(
        f"\033[33m⚠ ThothCTL {latest} available (you have {current}). "
        f"Run: thothctl upgrade\033[0m\n"
    )


def _is_newer(latest: str, current: str) -> bool:
    """Compare semantic versions."""
    try:
        latest_parts = tuple(int(x) for x in latest.split(".")[:3])
        current_parts = tuple(int(x) for x in current.split(".")[:3])
        return latest_parts > current_parts
    except (ValueError, AttributeError):
        return False
