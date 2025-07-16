"""Simplified ThothCTL MCP Server compatible with Amazon Q."""

import asyncio
import json
import logging
import sys
import subprocess
import os
from pathlib import Path
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Import ThothCTL functionality
from ...version import __version__

# Configure minimal logging for Amazon Q compatibility
logging.basicConfig(
    level=logging.ERROR,  # Only show errors to avoid interfering with stdio
    format="%(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("thothctl-mcp")


async def serve_amazon_q():
    """Main entry point for Amazon Q compatible MCP server."""
    server = Server("thothctl")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        """List available ThothCTL tools."""
        return [
            Tool(
                name="thothctl_init_project",
                description="Initialize a new project with ThothCTL",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Name of the project to initialize"
                        },
                        "space": {
                            "type": "string",
                            "description": "Space name for the project (optional)"
                        }
                    },
                    "required": ["project_name"]
                }
            ),
            Tool(
                name="thothctl_list_projects",
                description="List all projects managed by ThothCTL",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="thothctl_list_spaces",
                description="List all spaces managed by ThothCTL",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="thothctl_inventory",
                description="Create infrastructure inventory for IaC composition",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory to analyze (default: current directory)",
                            "default": "."
                        },
                        "check_versions": {
                            "type": "boolean",
                            "description": "Check for latest versions of modules and providers",
                            "default": False
                        },
                        "report_type": {
                            "type": "string",
                            "description": "Type of report to generate",
                            "enum": ["html", "json", "all"],
                            "default": "html"
                        }
                    }
                }
            ),
            Tool(
                name="thothctl_scan",
                description="Scan infrastructure code for security issues",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory to scan (default: current directory)",
                            "default": "."
                        },
                        "tools": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["checkov", "trivy", "tfsec"]
                            },
                            "description": "Security scanning tools to use",
                            "default": ["checkov"]
                        }
                    }
                }
            ),
            Tool(
                name="thothctl_document",
                description="Generate documentation for infrastructure projects",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory to document (default: current directory)",
                            "default": "."
                        }
                    }
                }
            ),
            Tool(
                name="thothctl_version",
                description="Get ThothCTL version information",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute a ThothCTL tool."""
        try:
            result = await execute_thothctl_command(name, arguments)
            return [TextContent(type="text", text=result)]
        except Exception as e:
            error_msg = f"Error executing {name}: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]

    # Run the server
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=False)


async def execute_thothctl_command(name: str, arguments: Dict[str, Any]) -> str:
    """Execute a specific ThothCTL command."""
    try:
        # Build the command
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
        
        elif name == "thothctl_document":
            cmd.extend(["document"])
        
        elif name == "thothctl_version":
            cmd.append("--version")
        
        else:
            return f"Unknown tool: {name}"
        
        # Change to the specified directory if provided
        original_cwd = None
        directory = arguments.get("directory", ".")
        if directory and directory != ".":
            if os.path.exists(directory):
                original_cwd = os.getcwd()
                os.chdir(directory)
            else:
                return f"Directory not found: {directory}"
        
        # Execute the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=directory if directory != "." else None
        )
        
        # Restore original directory
        if original_cwd:
            os.chdir(original_cwd)
        
        # Return result
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


if __name__ == "__main__":
    asyncio.run(serve_amazon_q())
