"""MCP register command."""

import click
import json
import os
import sys
from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI


class MCPRegisterCommand(ClickCommand):
    """Command to register the MCP server with Amazon Q."""
    
    def __init__(self):
        super().__init__()
        self.ui = CliUI()
    
    def execute(self, port, name, force):
        """Execute the register command."""
        with self.ui.status_spinner(f"Registering MCP server with Amazon Q as '{name}'..."):
            try:
                # Create the .amazonq directory if it doesn't exist
                os.makedirs(os.path.expanduser("~/.amazonq"), exist_ok=True)
                
                # Create the MCP configuration
                mcp_config = {
                    "mcpServers": {
                        name: {
                            "command": "thothctl",
                            "args": ["mcp", "server", "--port", str(port)],
                            "env": {},
                            "timeout": 120000,
                            "healthCheckUrl": f"http://localhost:{port}/health",
                            "url": f"http://localhost:{port}/mcp/v1"
                        }
                    }
                }
                
                # Write the configuration to a file
                config_path = os.path.expanduser("~/.amazonq/mcp.json")
                
                # Check if file exists and force flag is not set
                if os.path.exists(config_path) and not force:
                    if not self.ui.confirm("Configuration file already exists. Overwrite?"):
                        self.ui.print_warning("Registration cancelled")
                        return
                
                with open(config_path, "w") as f:
                    json.dump(mcp_config, f, indent=2)
                
                self.ui.print_success(f"Successfully registered MCP server with Amazon Q")
                self.ui.print_info(f"Configuration written to {config_path}")
                
            except Exception as e:
                self.ui.print_error(f"Failed to register MCP server with Amazon Q")
                self.ui.print_error(f"Error: {str(e)}")
                raise


# Create the Click command
cli = MCPRegisterCommand.as_click_command(name="register")(
    click.option(
        "-p",
        "--port",
        type=int,
        default=8080,
        help="Port the MCP server will run on",
    ),
    click.option(
        "-n",
        "--name",
        type=str,
        default="thothforge",
        help="Name to register the MCP server as",
    ),
    click.option(
        "--force",
        is_flag=True,
        help="Force overwrite if the server is already registered",
    )
)
