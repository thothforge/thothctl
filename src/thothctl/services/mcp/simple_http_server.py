"""Simplified HTTP MCP server for ThothCTL."""

import asyncio
import json
import logging
import os
import atexit
from pathlib import Path
from typing import Dict, Any

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from ...version import __version__
from ...core.cli_ui import CliUI

# Initialize CLI UI
ui = CliUI()

# Configure logging
logger = logging.getLogger("thothctl-mcp-http")

class SimpleHTTPMCPServer:
    """Simplified HTTP MCP server for ThothCTL."""
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.tools = self._get_available_tools()
    
    def _get_available_tools(self) -> list:
        """Get list of available tools."""
        return [
            {
                "name": "thothctl_init_project",
                "description": "Initialize a new project with ThothCTL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string", "description": "Name of the project"},
                        "space": {"type": "string", "description": "Space name (optional)"}
                    },
                    "required": ["project_name"]
                }
            },
            {
                "name": "thothctl_list_projects",
                "description": "List all projects managed by ThothCTL",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "thothctl_list_spaces",
                "description": "List all spaces managed by ThothCTL",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "thothctl_inventory",
                "description": "Create infrastructure inventory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."},
                        "check_versions": {"type": "boolean", "default": False},
                        "report_type": {"type": "string", "enum": ["html", "json", "all"], "default": "html"}
                    }
                }
            },
            {
                "name": "thothctl_scan",
                "description": "Scan infrastructure code for security issues",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."},
                        "tools": {"type": "array", "items": {"type": "string"}, "default": ["checkov"]}
                    }
                }
            },
            {
                "name": "thothctl_version",
                "description": "Get ThothCTL version",
                "parameters": {"type": "object", "properties": {}}
            }
        ]
    
    async def health_check(self, request):
        """Health check endpoint."""
        return JSONResponse({
            "status": "ok",
            "version": __version__,
            "server": "ThothCTL MCP Server"
        })
    
    async def list_tools(self, request):
        """List available tools endpoint."""
        return JSONResponse({
            "tools": self.tools
        })
    
    async def execute_tool(self, request):
        """Execute a tool endpoint."""
        try:
            body = await request.json()
            tool_name = body.get("tool")
            arguments = body.get("arguments", {})
            
            if not tool_name:
                return JSONResponse(
                    {"error": "Missing 'tool' parameter"},
                    status_code=400
                )
            
            # Execute the tool using subprocess (same as Amazon Q server)
            result = await self._execute_thothctl_command(tool_name, arguments)
            
            return JSONResponse({
                "result": result,
                "status": "success"
            })
            
        except Exception as e:
            logger.error(f"Error executing tool: {e}")
            return JSONResponse(
                {"error": str(e), "status": "error"},
                status_code=500
            )
    
    async def _execute_thothctl_command(self, name: str, arguments: Dict[str, Any]) -> str:
        """Execute a ThothCTL command."""
        import subprocess
        
        # Build the command (same logic as Amazon Q server)
        cmd = ["thothctl"]
        
        if name == "thothctl_init_project":
            cmd.extend(["init", "project", "--project-name", arguments["project_name"]])
            if arguments.get("space"):
                cmd.extend(["--space", arguments["space"]])
        elif name == "thothctl_list_projects":
            cmd.extend(["list", "projects"])
        elif name == "thothctl_list_spaces":
            cmd.extend(["list", "spaces"])
        elif name == "thothctl_inventory":
            cmd.extend(["inventory", "iac"])
            if arguments.get("check_versions", False):
                cmd.append("--check-versions")
            report_type = arguments.get("report_type", "html")
            cmd.extend(["--report-type", report_type])
        elif name == "thothctl_scan":
            cmd.extend(["scan", "iac"])
            tools = arguments.get("tools", ["checkov"])
            for tool in tools:
                cmd.extend(["--tools", tool])
        elif name == "thothctl_version":
            cmd.append("--version")
        else:
            return f"Unknown tool: {name}"
        
        # Execute the command
        try:
            directory = arguments.get("directory", ".")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=directory if directory != "." else None
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if not output and result.stderr.strip():
                    output = result.stderr.strip()
                return output or f"Command executed successfully: {' '.join(cmd)}"
            else:
                error_output = result.stderr.strip() or result.stdout.strip()
                return f"Command failed (exit code {result.returncode}): {error_output}"
        
        except subprocess.TimeoutExpired:
            return f"Command timed out after 5 minutes: {' '.join(cmd)}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    def create_app(self):
        """Create the Starlette application."""
        routes = [
            Route("/health", self.health_check, methods=["GET"]),
            Route("/tools", self.list_tools, methods=["GET"]),
            Route("/execute", self.execute_tool, methods=["POST"]),
            Route("/mcp/v1/tools", self.list_tools, methods=["GET"]),
            Route("/mcp/v1/execute", self.execute_tool, methods=["POST"]),
        ]
        
        middleware = [
            Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
        ]
        
        return Starlette(routes=routes, middleware=middleware)
    
    def run(self):
        """Run the HTTP server."""
        try:
            # Create PID file
            pid_dir = os.path.expanduser("~/.thothctl/mcp")
            os.makedirs(pid_dir, exist_ok=True)
            pid_file = os.path.join(pid_dir, f"server_{self.port}.pid")
            
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Register cleanup
            def cleanup():
                try:
                    if os.path.exists(pid_file):
                        os.remove(pid_file)
                except:
                    pass
            
            atexit.register(cleanup)
            
            # Create and run the app
            app = self.create_app()
            
            ui.print_success(f"MCP server ready at http://{self.host}:{self.port}")
            ui.print_info(f"Health check endpoint: http://{self.host}:{self.port}/health")
            ui.print_info(f"Tools endpoint: http://{self.host}:{self.port}/tools")
            ui.print_info(f"Execute endpoint: http://{self.host}:{self.port}/execute")
            
            uvicorn.run(app, host=self.host, port=self.port, log_level="info")
            
        except Exception as e:
            logger.error(f"Error running HTTP server: {e}")
            ui.print_error(f"Error running HTTP server: {str(e)}")
            raise


def run_simple_http_server(host: str = "localhost", port: int = 8080):
    """Run the simplified HTTP MCP server."""
    server = SimpleHTTPMCPServer(host, port)
    server.run()
