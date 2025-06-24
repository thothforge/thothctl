"""MCP server command."""

import click
from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....services.mcp import run_server


class MCPServerCommand(ClickCommand):
    """Command to start the MCP server for ThothCTL."""
    
    def __init__(self):
        super().__init__()
        self.ui = CliUI()
    
    def execute(self, port, host, stdio):
        """Execute the MCP server command."""
        if stdio:
            import asyncio
            from pathlib import Path
            from ....services.mcp import serve
            
            # Run in stdio mode - this is the mode Amazon Q uses
            self.ui.print_info(f"Starting ThothCTL MCP server in stdio mode")
            asyncio.run(serve(Path.cwd()))
        else:
            # Run in HTTP mode
            with self.ui.status_spinner(f"Starting MCP server on {host}:{port}..."):
                self.ui.print_info(f"Starting ThothCTL MCP server on {host}:{port}")
                self.ui.print_info(f"Health check will be available at: http://{host}:{port}/health")
                self.ui.print_info(f"MCP endpoint will be available at: http://{host}:{port}/mcp/v1")
                self.ui.print_info(f"To stop the server, use: thothctl mcp stop --port {port}")
                run_server(host=host, port=port)


# Create the Click command
cli = MCPServerCommand.as_click_command(name="server")(
    click.option(
        "-p",
        "--port",
        type=int,
        default=8080,
        help="Port to run the MCP server on",
    ),
    click.option(
        "-h",
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the MCP server to",
    ),
    click.option(
        "--stdio",
        is_flag=True,
        help="Run in stdio mode instead of HTTP mode",
    )
)
