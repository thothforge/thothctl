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
    
    def _execute(self, port, name, force, stdio, scope):
        """Execute the register command."""
        scope_label = "workspace" if scope == "workspace" else "global"
        with self.ui.status_spinner(f"Registering MCP server with Kiro CLI ({scope_label}) as '{name}'..."):
            try:
                # Determine config path based on scope
                if scope == "workspace":
                    config_dir = os.path.join(os.getcwd(), ".kiro", "settings")
                else:  # global
                    config_dir = os.path.expanduser("~/.kiro/settings")
                
                os.makedirs(config_dir, exist_ok=True)
                config_path = os.path.join(config_dir, "mcp.json")
                
                # Load existing configuration if it exists
                existing_config = {}
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r") as f:
                            existing_config = json.load(f)
                        self.ui.print_info(f"Found existing configuration with {len(existing_config.get('mcpServers', {}))} server(s)")
                    except (json.JSONDecodeError, Exception) as e:
                        self.ui.print_warning(f"Could not read existing config: {e}")
                        if not force:
                            if not self.ui.confirm("Continue with new configuration?"):
                                self.ui.print_warning("Registration cancelled")
                                return
                        existing_config = {}
                
                # Ensure mcpServers section exists
                if "mcpServers" not in existing_config:
                    existing_config["mcpServers"] = {}
                
                # Check if server name already exists
                if name in existing_config["mcpServers"]:
                    if not force:
                        self.ui.print_warning(f"Server '{name}' already exists in configuration")
                        if not self.ui.confirm(f"Overwrite existing '{name}' server configuration?"):
                            self.ui.print_warning("Registration cancelled")
                            return
                    self.ui.print_info(f"Overwriting existing '{name}' server configuration")
                
                # Create the new server configuration
                if stdio:
                    # Stdio mode configuration (recommended for Kiro CLI)
                    server_config = {
                        "command": "thothctl",
                        "args": ["mcp", "server", "--stdio"],
                        "env": {}
                    }
                else:
                    # HTTP mode configuration
                    server_config = {
                        "url": f"http://localhost:{port}/mcp/v1",
                        "headers": {},
                        "env": {}
                    }
                
                # Add the new server to existing configuration
                existing_config["mcpServers"][name] = server_config
                
                # Write the updated configuration
                with open(config_path, "w") as f:
                    json.dump(existing_config, f, indent=2)
                
                # Success message
                total_servers = len(existing_config["mcpServers"])
                mode = "stdio" if stdio else f"HTTP (port {port})"
                
                self.ui.print_success(f"Successfully registered '{name}' MCP server with Kiro CLI")
                self.ui.print_info(f"Scope: {scope_label}")
                self.ui.print_info(f"Mode: {mode}")
                self.ui.print_info(f"Configuration: {config_path}")
                self.ui.print_info(f"Total servers in config: {total_servers}")
                
                # Show all registered servers
                if total_servers > 1:
                    self.ui.print_info("All registered MCP servers:")
                    for server_name in existing_config["mcpServers"].keys():
                        marker = "← NEW" if server_name == name else ""
                        self.ui.print_info(f"  • {server_name} {marker}")
                
            except Exception as e:
                self.ui.print_error(f"Failed to register MCP server with Kiro CLI")
                self.ui.print_error(f"Error: {str(e)}")
                raise


# Create the Click command
cli = MCPRegisterCommand.as_click_command(name="register")(
    click.option(
        "-p",
        "--port",
        type=int,
        default=8080,
        help="Port the MCP server will run on (HTTP mode only)",
    ),
    click.option(
        "-n",
        "--name",
        type=str,
        default="thothctl",
        help="Name to register the MCP server as",
    ),
    click.option(
        "--force",
        is_flag=True,
        help="Force overwrite if the server is already registered",
    ),
    click.option(
        "--stdio",
        is_flag=True,
        default=True,
        help="Register for stdio mode (recommended for Kiro CLI)",
    ),
    click.option(
        "--scope",
        type=click.Choice(["workspace", "global"]),
        default="global",
        help="Configuration scope: workspace (.kiro/settings/mcp.json) or global (~/.kiro/settings/mcp.json)",
    )
)
