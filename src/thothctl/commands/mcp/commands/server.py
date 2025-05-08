"""MCP server command."""

import click
from ....mcp.server import run_server


@click.command(name="server")
@click.option(
    "-p",
    "--port",
    type=int,
    default=8080,
    help="Port to run the MCP server on",
)
def cli(port):
    """Start the MCP server for ThothCTL."""
    run_server(port=port)
