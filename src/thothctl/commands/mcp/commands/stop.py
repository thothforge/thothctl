"""MCP server stop command."""

import click
import os
import signal
import glob
from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI


class MCPStopCommand(ClickCommand):
    """Command to stop the MCP server for ThothCTL."""
    
    def __init__(self):
        super().__init__()
        self.ui = CliUI()
    
    def _execute(self, port, all_servers):
        """Execute the MCP server stop command."""
        if all_servers:
            self._stop_all_servers()
        else:
            self._stop_server_by_port(port)
    
    def _stop_server_by_port(self, port: int):
        """Stop MCP server running on specific port."""
        pid_dir = os.path.expanduser("~/.thothctl/mcp")
        pid_file = os.path.join(pid_dir, f"server_{port}.pid")
        
        if not os.path.exists(pid_file):
            self.ui.print_warning(f"No MCP server found running on port {port}")
            return
        
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Try to terminate the process
            os.kill(pid, signal.SIGTERM)
            
            # Remove PID file
            os.remove(pid_file)
            
            self.ui.print_success(f"MCP server on port {port} stopped successfully")
            
        except (ValueError, ProcessLookupError):
            self.ui.print_warning(f"MCP server process not found (PID file may be stale)")
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception as e:
            self.ui.print_error(f"Error stopping MCP server: {str(e)}")
    
    def _stop_all_servers(self):
        """Stop all running MCP servers."""
        pid_dir = os.path.expanduser("~/.thothctl/mcp")
        
        if not os.path.exists(pid_dir):
            self.ui.print_info("No MCP servers found")
            return
        
        pid_files = glob.glob(os.path.join(pid_dir, "server_*.pid"))
        
        if not pid_files:
            self.ui.print_info("No MCP servers found")
            return
        
        stopped_count = 0
        for pid_file in pid_files:
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # Extract port from filename
                port = os.path.basename(pid_file).replace("server_", "").replace(".pid", "")
                
                # Try to terminate the process
                os.kill(pid, signal.SIGTERM)
                
                # Remove PID file
                os.remove(pid_file)
                
                self.ui.print_success(f"MCP server on port {port} stopped")
                stopped_count += 1
                
            except (ValueError, ProcessLookupError):
                self.ui.print_warning(f"Stale PID file removed: {pid_file}")
                if os.path.exists(pid_file):
                    os.remove(pid_file)
            except Exception as e:
                self.ui.print_error(f"Error stopping server {pid_file}: {str(e)}")
        
        if stopped_count > 0:
            self.ui.print_success(f"Stopped {stopped_count} MCP server(s)")
        else:
            self.ui.print_info("No running MCP servers found")


# Create the Click command
cli = MCPStopCommand.as_click_command(name="stop")(
    click.option(
        "-p",
        "--port",
        type=int,
        default=8080,
        help="Port of the MCP server to stop",
    ),
    click.option(
        "--all",
        "all_servers",
        is_flag=True,
        help="Stop all running MCP servers",
    )
)
