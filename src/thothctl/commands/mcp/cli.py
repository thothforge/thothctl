"""MCP server command for ThothCTL."""

import importlib.util
import logging
from pathlib import Path
from typing import Optional

import click
from ...mcp.server import run_server


logger = logging.getLogger(__name__)


class MCPCLI(click.MultiCommand):
    def list_commands(self, ctx: click.Context) -> list[str]:
        commands = []
        commands_path = Path(__file__).parent / "commands"
        
        # Create commands directory if it doesn't exist
        commands_path.mkdir(exist_ok=True)
        
        try:
            for item in commands_path.iterdir():
                if item.name.endswith(".py") and not item.name.startswith("_"):
                    commands.append(item.stem)
        except Exception as e:
            logger.error(f"Error listing MCP subcommands: {e}")
            return []

        # Add the default 'server' command even if no file exists yet
        if "server" not in commands:
            commands.append("server")
            
        commands.sort()
        return commands

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        try:
            # Special case for the 'server' command if file doesn't exist yet
            if cmd_name == "server" and not (Path(__file__).parent / "commands" / "server.py").exists():
                @click.command(name="server")
                @click.option(
                    "-p",
                    "--port",
                    type=int,
                    default=8080,
                    help="Port to run the MCP server on",
                )
                def server_command(port):
                    """Start the MCP server for ThothCTL."""
                    run_server(port=port)
                
                return server_command
                
            module_path = Path(__file__).parent / "commands" / f"{cmd_name}.py"

            if not module_path.exists():
                return None

            # Import the module
            module_name = f"thothctl.commands.mcp.commands.{cmd_name}"
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
            logger.error(f"Error loading MCP subcommand {cmd_name}: {str(e)}")
            return None


@click.group(cls=MCPCLI)
@click.pass_context
def cli(ctx):
    """Model Context Protocol (MCP) server for ThothCTL"""
    pass
