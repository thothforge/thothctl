"""MCP status command."""

import click
import subprocess
import sys
import requests
import os
import psutil
from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI


class MCPStatusCommand(ClickCommand):
    """Command to check the status of the MCP server."""
    
    def __init__(self):
        super().__init__()
        self.ui = CliUI()
    
    def _execute(self, port):
        """Execute the status command."""
        self.ui.print_info(f"Checking MCP server status on port {port}...")
        
        # Check if there's a PID file
        pid_file = os.path.expanduser(f"~/.thothctl/mcp/server_{port}.pid")
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                self.ui.print_info(f"Found PID file with process ID: {pid}")
                
                # Check if the process is running
                try:
                    process = psutil.Process(pid)
                    if process.is_running():
                        cmdline = " ".join(process.cmdline())
                        if "thothctl" in cmdline and "mcp" in cmdline and "server" in cmdline:
                            self.ui.print_success(f"MCP server process (PID {pid}) is running")
                        else:
                            self.ui.print_warning(f"Process with PID {pid} is running but doesn't appear to be an MCP server")
                    else:
                        self.ui.print_warning(f"Process with PID {pid} is not running")
                except psutil.NoSuchProcess:
                    self.ui.print_warning(f"Process with PID {pid} does not exist")
                    self.ui.print_warning(f"PID file may be stale: {pid_file}")
            except Exception as e:
                self.ui.print_warning(f"Error reading PID file: {str(e)}")
        
        # Check if the server is running
        try:
            with self.ui.status_spinner("Connecting to MCP server..."):
                response = requests.get(f"http://localhost:{port}/health", timeout=2)
                
            if response.status_code == 200:
                data = response.json()
                self.ui.print_success("MCP server is running")
                self.ui.print_info(f"Version: {data.get('version', 'unknown')}")
                self.ui.print_info(f"Status: {data.get('status', 'unknown')}")
            else:
                self.ui.print_error(f"MCP server returned status code {response.status_code}")
        except requests.exceptions.ConnectionError:
            self.ui.print_error("MCP server is not running or not accessible")
        except Exception as e:
            self.ui.print_error(f"Error checking MCP server status: {str(e)}")
        
        # Check if the server is registered with Amazon Q
        try:
            with self.ui.status_spinner("Checking Amazon Q MCP registration..."):
                result = subprocess.run("q mcp list", shell=True, check=True, capture_output=True, text=True)
            
            self.ui.print_info("\nAmazon Q MCP Registration:")
            self.ui.console.print(result.stdout)
        except subprocess.CalledProcessError as e:
            self.ui.print_error("\nFailed to check MCP registration with Amazon Q")
            self.ui.print_error(f"Error: {e.stderr}")
            raise


# Create the Click command
cli = MCPStatusCommand.as_click_command(name="status")(
    click.option(
        "-p",
        "--port",
        type=int,
        default=8080,
        help="Port the MCP server is running on",
    )
)
