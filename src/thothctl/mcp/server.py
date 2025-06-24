"""ThothCTL MCP Server - Exposes ThothCTL functionality through Model Context Protocol."""

import json
import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List, Optional
import subprocess

from ..common.common import list_projects, list_spaces, get_project_space, get_projects_in_space, get_space_details
from ..version import __version__
from ..core.cli_ui import CliUI

# Initialize CLI UI
ui = CliUI()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("thothctl-mcp")

# Default port for the MCP server
DEFAULT_PORT = 8080


class ThothCTLMCPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for ThothCTL MCP server."""
    
    def _set_headers(self, status_code: int = 200) -> None:
        """Set response headers.
        
        Args:
            status_code: HTTP status code
        """
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
    
    def do_POST(self) -> None:
        """Handle POST requests."""
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        request = json.loads(post_data.decode("utf-8"))
        
        logger.info(f"Received request: {request}")
        
        if self.path == "/tools":
            # Return the list of available tools
            self._handle_tools_request()
        elif self.path == "/execute":
            # Execute a tool
            self._handle_execute_request(request)
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
    
    def _handle_tools_request(self) -> None:
        """Handle request for available tools."""
        tools = self._get_available_tools()
        
        self._set_headers()
        self.wfile.write(json.dumps({"tools": tools}).encode())
    
    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools.
        
        Returns:
            List of tool definitions
        """
        tools = [
            {
                "name": "thothctl_init_project",
                "description": "Initialize and setup project configurations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Name of the project to initialize"
                        },
                        "space": {
                            "type": "string",
                            "description": "Space name for the project (used for loading credentials and configurations)"
                        },
                        "code_directory": {
                            "type": "string",
                            "description": "Configuration file path"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    },
                    "required": ["project_name"]
                }
            },
            {
                "name": "thothctl_init_space",
                "description": "Initialize and setup space configurations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "space_name": {
                            "type": "string",
                            "description": "Name of the space to initialize"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the space"
                        },
                        "vcs_provider": {
                            "type": "string",
                            "description": "Version control system provider (github, gitlab, azure)"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    },
                    "required": ["space_name"]
                }
            },
            {
                "name": "thothctl_list_projects",
                "description": "List projects managed by thothctl locally",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    }
                }
            },
            {
                "name": "thothctl_list_spaces",
                "description": "List spaces managed by thothctl locally",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    }
                }
            },
            {
                "name": "thothctl_scan",
                "description": "Scan infrastructure code for security issues",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code_directory": {
                            "type": "string",
                            "description": "Directory containing infrastructure code"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    }
                }
            },
            {
                "name": "thothctl_inventory",
                "description": "Create Inventory for the iac composition",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code_directory": {
                            "type": "string",
                            "description": "Directory containing infrastructure code"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    }
                }
            },
            {
                "name": "thothctl_generate",
                "description": "Generate IaC from rules, use cases, and components",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code_directory": {
                            "type": "string",
                            "description": "Directory containing infrastructure code"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    }
                }
            },
            {
                "name": "thothctl_document",
                "description": "Initialize and setup project documentation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code_directory": {
                            "type": "string",
                            "description": "Directory containing infrastructure code"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    }
                }
            },
            {
                "name": "thothctl_check",
                "description": "Check infrastructure code for compliance",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code_directory": {
                            "type": "string",
                            "description": "Directory containing infrastructure code"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    }
                }
            },
            {
                "name": "thothctl_project",
                "description": "Convert, clean up and manage the current project",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code_directory": {
                            "type": "string",
                            "description": "Directory containing infrastructure code"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    }
                }
            },
            {
                "name": "thothctl_remove_project",
                "description": "Remove a project managed by thothctl",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Name of the project to remove"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    },
                    "required": ["project_name"]
                }
            },
            {
                "name": "thothctl_remove_space",
                "description": "Remove a space managed by thothctl",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "space_name": {
                            "type": "string",
                            "description": "Name of the space to remove"
                        },
                        "remove_projects": {
                            "type": "boolean",
                            "description": "Whether to remove all projects in the space"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    },
                    "required": ["space_name"]
                }
            },
            {
                "name": "thothctl_get_projects",
                "description": "Get list of projects managed by thothctl",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "thothctl_get_spaces",
                "description": "Get list of spaces managed by thothctl",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "thothctl_get_projects_in_space",
                "description": "Get list of projects in a specific space",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "space_name": {
                            "type": "string",
                            "description": "Name of the space"
                        }
                    },
                    "required": ["space_name"]
                }
            },
            {
                "name": "thothctl_version",
                "description": "Get ThothCTL version",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
        
        # Fix the tool names to match what's expected by the command mapping
        fixed_tools = []
        for tool in tools:
            if tool["name"] == "thothctl_init_project":
                tool_copy = tool.copy()
                tool_copy["name"] = "thothctl_init"
                fixed_tools.append(tool_copy)
            elif tool["name"] == "thothctl_list_projects":
                tool_copy = tool.copy()
                tool_copy["name"] = "thothctl_list"
                fixed_tools.append(tool_copy)
            elif tool["name"] == "thothctl_remove_project":
                tool_copy = tool.copy()
                tool_copy["name"] = "thothctl_remove"
                fixed_tools.append(tool_copy)
            else:
                fixed_tools.append(tool)
        
        return fixed_tools
    
    def _handle_execute_request(self, request: Dict[str, Any]) -> None:
        """Handle request to execute a tool.
        
        Args:
            request: The request data
        """
        tool_name = request.get("name")
        parameters = request.get("parameters", {})
        
        if not tool_name:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "Tool name is required"}).encode())
            return
        
        # Special handlers for custom tools
        if tool_name == "thothctl_get_projects":
            self._handle_get_projects()
            return
        
        if tool_name == "thothctl_get_spaces":
            self._handle_get_spaces()
            return
            
        if tool_name == "thothctl_get_projects_in_space":
            self._handle_get_projects_in_space(parameters)
            return
        
        if tool_name == "thothctl_version":
            self._handle_get_version()
            return
        
        # Map tool name to thothctl command
        command_map = {
            "thothctl_init": ["init", "project"],
            "thothctl_init_project": ["init", "project"],
            "thothctl_init_space": ["init", "space"],
            "thothctl_list": ["list", "projects"],
            "thothctl_list_projects": ["list", "projects"],
            "thothctl_list_spaces": ["list", "spaces"],
            "thothctl_scan": ["scan"],
            "thothctl_inventory": ["inventory"],
            "thothctl_generate": ["generate"],
            "thothctl_document": ["document"],
            "thothctl_check": ["check"],
            "thothctl_project": ["project"],
            "thothctl_remove": ["remove", "project"],
            "thothctl_remove_project": ["remove", "project"],
            "thothctl_remove_space": ["remove", "space"]
        }
        
        if tool_name not in command_map:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": f"Unknown tool: {tool_name}"}).encode())
            return
        
        # Build the command
        cmd = ["thothctl"] + command_map[tool_name]
        
        # Add parameters
        if "code_directory" in parameters:
            cmd.extend(["-d", parameters["code_directory"]])
        
        if parameters.get("debug", False):
            cmd.append("--debug")
            
        # Handle specific command parameters
        if tool_name in ["thothctl_init", "thothctl_init_project"]:
            if "project_name" in parameters:
                cmd.extend(["-pj", parameters["project_name"]])
            if "space" in parameters:
                cmd.extend(["-s", parameters["space"]])
                
        elif tool_name == "thothctl_init_space":
            if "space_name" in parameters:
                cmd.extend(["--space-name", parameters["space_name"]])
            if "description" in parameters:
                cmd.extend(["--description", parameters["description"]])
            if "vcs_provider" in parameters:
                cmd.extend(["--vcs-provider", parameters["vcs_provider"]])
                
        elif tool_name in ["thothctl_remove", "thothctl_remove_project"]:
            if "project_name" in parameters:
                cmd.extend(["-pj", parameters["project_name"]])
                
        elif tool_name == "thothctl_remove_space":
            if "space_name" in parameters:
                cmd.extend(["--space-name", parameters["space_name"]])
            if parameters.get("remove_projects", False):
                cmd.append("--remove-projects")
        
        # Execute the command
        try:
            logger.info(f"Executing command: {' '.join(cmd)}")
            ui.print_info(f"Executing command: {' '.join(cmd)}")
            
            with ui.status_spinner("Executing command..."):
                result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                ui.print_success("Command executed successfully")
            else:
                ui.print_error(f"Command failed with exit code {result.returncode}")
                ui.print_error(result.stderr)
            
            response = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            ui.print_error(f"Error executing command: {str(e)}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _handle_get_projects(self) -> None:
        """Handle request to get list of projects."""
        try:
            with ui.status_spinner("Getting projects..."):
                projects = list_projects()
                
                # Add space information to each project
                project_data = []
                if projects:
                    for project_name in projects:
                        space = get_project_space(project_name)
                        project_info = {
                            "name": project_name,
                            "space": space
                        }
                        project_data.append(project_info)
            
            ui.print_success(f"Found {len(project_data)} projects")
            
            response = {
                "projects": project_data if projects else []
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"Error getting projects: {e}")
            ui.print_error(f"Error getting projects: {str(e)}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _handle_get_spaces(self) -> None:
        """Handle request to get list of spaces."""
        try:
            with ui.status_spinner("Getting spaces..."):
                spaces = list_spaces()
                space_details = get_space_details()
                
                # Prepare space data with additional information
                space_data = []
                for space_name in spaces:
                    space_info = {
                        "name": space_name,
                        "projects": get_projects_in_space(space_name),
                        "details": space_details.get(space_name, {})
                    }
                    space_data.append(space_info)
            
            ui.print_success(f"Found {len(space_data)} spaces")
            
            response = {
                "spaces": space_data if spaces else []
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"Error getting spaces: {e}")
            ui.print_error(f"Error getting spaces: {str(e)}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _handle_get_projects_in_space(self, parameters: Dict[str, Any]) -> None:
        """Handle request to get list of projects in a space.
        
        Args:
            parameters: Request parameters
        """
        space_name = parameters.get("space_name")
        if not space_name:
            ui.print_error("Space name is required")
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "Space name is required"}).encode())
            return
            
        try:
            with ui.status_spinner(f"Getting projects in space {space_name}..."):
                projects = get_projects_in_space(space_name)
            
            ui.print_success(f"Found {len(projects)} projects in space {space_name}")
            
            response = {
                "space": space_name,
                "projects": projects if projects else []
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"Error getting projects in space: {e}")
            ui.print_error(f"Error getting projects in space: {str(e)}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _handle_get_version(self) -> None:
        """Handle request to get ThothCTL version."""
        try:
            ui.print_info(f"ThothCTL version: {__version__}")
            
            response = {
                "version": __version__
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"Error getting version: {e}")
            ui.print_error(f"Error getting version: {str(e)}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())


def run_server(port: int = DEFAULT_PORT) -> None:
    """Run the MCP server.
    
    Args:
        port: Port to listen on
    """
    server_address = ("", port)
    httpd = HTTPServer(server_address, ThothCTLMCPHandler)
    ui.print_info(f"Starting ThothCTL MCP server on port {port}")
    ui.print_info(f"ThothCTL version: {__version__}")
    try:
        ui.print_success(f"Server is ready at http://localhost:{port}")
        httpd.serve_forever()
    except KeyboardInterrupt:
        ui.print_info("Stopping server...")
        httpd.server_close()
