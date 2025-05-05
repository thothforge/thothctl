"""ThothCTL MCP Server - Exposes ThothCTL functionality through Model Context Protocol."""

import json
import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List, Optional
import subprocess

from ..common.common import list_projects
from ..version import __version__

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
                "name": "thothctl_init",
                "description": "Initialize and setup project configurations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code_directory": {
                            "type": "string",
                            "description": "Configuration file path"
                        },
                        "debug": {
                            "type": "boolean",
                            "description": "Enable debug mode"
                        }
                    }
                }
            },
            {
                "name": "thothctl_list",
                "description": "List Projects managed by thothctl locally",
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
                "name": "thothctl_remove",
                "description": "Remove Projects managed by thothctl",
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
                "name": "thothctl_get_projects",
                "description": "Get list of projects managed by thothctl",
                "parameters": {
                    "type": "object",
                    "properties": {}
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
        
        return tools
    
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
        
        if tool_name == "thothctl_version":
            self._handle_get_version()
            return
        
        # Map tool name to thothctl command
        command_map = {
            "thothctl_init": "init",
            "thothctl_list": "list",
            "thothctl_scan": "scan",
            "thothctl_inventory": "inventory",
            "thothctl_generate": "generate",
            "thothctl_document": "document",
            "thothctl_check": "check",
            "thothctl_project": "project",
            "thothctl_remove": "remove"
        }
        
        if tool_name not in command_map:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": f"Unknown tool: {tool_name}"}).encode())
            return
        
        # Build the command
        cmd = ["thothctl", command_map[tool_name]]
        
        # Add parameters
        if "code_directory" in parameters:
            cmd.extend(["-d", parameters["code_directory"]])
        
        if parameters.get("debug", False):
            cmd.append("--debug")
            
        if "project_name" in parameters and tool_name == "thothctl_remove":
            cmd.extend(["-pj", parameters["project_name"]])
        
        # Execute the command
        try:
            logger.info(f"Executing command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            response = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _handle_get_projects(self) -> None:
        """Handle request to get list of projects."""
        try:
            projects = list_projects()
            
            response = {
                "projects": projects if projects else []
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"Error getting projects: {e}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _handle_get_version(self) -> None:
        """Handle request to get ThothCTL version."""
        try:
            response = {
                "version": __version__
            }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"Error getting version: {e}")
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())


def run_server(port: int = DEFAULT_PORT) -> None:
    """Run the MCP server.
    
    Args:
        port: Port to listen on
    """
    server_address = ("", port)
    httpd = HTTPServer(server_address, ThothCTLMCPHandler)
    logger.info(f"Starting ThothCTL MCP server on port {port}")
    logger.info(f"ThothCTL version: {__version__}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping server...")
        httpd.server_close()
