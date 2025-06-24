"""MCP command group."""

import click

from .commands.server import cli as server_cli
from .commands.register import cli as register_cli
from .commands.status import cli as status_cli
from .commands.stop import cli as stop_cli


@click.group(name="mcp")
def cli():
    """Model Context Protocol (MCP) server for ThothCTL."""
    pass


cli.add_command(server_cli)
cli.add_command(register_cli)
cli.add_command(status_cli)
cli.add_command(stop_cli)
