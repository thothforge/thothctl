"""ThothCTL MCP Server - Complete Amazon Q 1.16.0 Compatible Implementation."""

import asyncio
import subprocess
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


async def serve_amazon_q():
    """Amazon Q compatible MCP server with all thothctl functionality."""
    server = Server("thothctl")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            # Version and basic info
            Tool(
                name="thothctl_version",
                description="Get ThothCTL version information",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            
            # Check commands
            Tool(
                name="thothctl_check_environment",
                description="Check if development environment tools are installed",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            Tool(
                name="thothctl_check_iac",
                description="Check Infrastructure as Code artifacts like tfplan",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            Tool(
                name="thothctl_check_project",
                description="Check project structure and configuration",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            
            # Document commands
            Tool(
                name="thothctl_document_iac",
                description="Generate documentation for Infrastructure as Code",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            
            # Generate commands
            Tool(
                name="thothctl_generate_stacks",
                description="Generate infrastructure stacks based on configuration",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            
            # Init commands
            Tool(
                name="thothctl_init_env",
                description="Initialize a development environment with required tools",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            Tool(
                name="thothctl_init_project",
                description="Initialize a new project",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string", "description": "Name of the project"},
                        "project_type": {"type": "string", "description": "Type of project", "default": "terraform-terragrunt", "enum": ["terraform", "terraform-terragrunt", "tofu", "cdkv2", "terraform_module", "terragrunt", "custom"]},
                        "space": {"type": "string", "description": "Space name (optional)"}
                    },
                    "required": ["project_name"],
                    "additionalProperties": False
                }
            ),
            Tool(
                name="thothctl_init_space",
                description="Initialize a new space",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "space_name": {"type": "string", "description": "Name of the space"}
                    },
                    "required": ["space_name"],
                    "additionalProperties": False
                }
            ),
            
            # Inventory commands
            Tool(
                name="thothctl_inventory_iac",
                description="Create inventory about IaC modules composition",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "check_versions": {"type": "boolean", "description": "Check for latest versions", "default": False},
                        "project_name": {"type": "string", "description": "Project name for report"}
                    },
                    "additionalProperties": False
                }
            ),
            
            # List commands
            Tool(
                name="thothctl_list_projects",
                description="List all projects managed by thothctl",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            Tool(
                name="thothctl_list_spaces",
                description="List all spaces managed by thothctl",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            Tool(
                name="thothctl_list_templates",
                description="List available templates from VCS providers",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            
            # Project commands
            Tool(
                name="thothctl_project_cleanup",
                description="Clean up residual files and directories from project",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            Tool(
                name="thothctl_project_convert",
                description="Convert project to template or between formats",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target_type": {"type": "string", "description": "Target conversion type"}
                    },
                    "additionalProperties": False
                }
            ),
            
            # Remove commands
            Tool(
                name="thothctl_remove_project",
                description="Remove project from local thothcf tracking",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string", "description": "Name of project to remove"}
                    },
                    "required": ["project_name"],
                    "additionalProperties": False
                }
            ),
            Tool(
                name="thothctl_remove_space",
                description="Remove a space and optionally its associated projects",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "space_name": {"type": "string", "description": "Name of space to remove"}
                    },
                    "required": ["space_name"],
                    "additionalProperties": False
                }
            ),
            
            # Scan commands
            Tool(
                name="thothctl_scan_iac",
                description="Scan IaC using security tools with AI analysis",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tools": {"type": "array", "items": {"type": "string"}, "description": "Security tools to use", "default": ["checkov"]}
                    },
                    "additionalProperties": False
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            # Build command based on tool name
            if name == "thothctl_version":
                cmd = ["thothctl", "--version"]
            
            # Check commands
            elif name == "thothctl_check_environment":
                cmd = ["thothctl", "check", "environment"]
            elif name == "thothctl_check_iac":
                cmd = ["thothctl", "check", "iac"]
            elif name == "thothctl_check_project":
                cmd = ["thothctl", "check", "project"]
            
            # Document commands
            elif name == "thothctl_document_iac":
                cmd = ["thothctl", "document", "iac"]
            
            # Generate commands
            elif name == "thothctl_generate_stacks":
                cmd = ["thothctl", "generate", "stacks"]
            
            # Init commands
            elif name == "thothctl_init_env":
                cmd = ["thothctl", "init", "env"]
            elif name == "thothctl_init_project":
                cmd = ["thothctl", "init", "project", "--project-name", arguments["project_name"]]
                project_type = arguments.get("project_type", "terraform-terragrunt")
                cmd.extend(["--project-type", project_type])
                if arguments.get("space"):
                    cmd.extend(["--space", arguments["space"]])
            elif name == "thothctl_init_space":
                cmd = ["thothctl", "init", "space", "--space-name", arguments["space_name"]]
            
            # Inventory commands
            elif name == "thothctl_inventory_iac":
                cmd = ["thothctl", "inventory", "iac"]
                if arguments.get("check_versions", False):
                    cmd.append("--check-versions")
                if arguments.get("project_name"):
                    cmd.extend(["--project-name", arguments["project_name"]])
            
            # List commands
            elif name == "thothctl_list_projects":
                cmd = ["thothctl", "list", "projects"]
            elif name == "thothctl_list_spaces":
                cmd = ["thothctl", "list", "spaces"]
            elif name == "thothctl_list_templates":
                cmd = ["thothctl", "list", "templates"]
            
            # Project commands
            elif name == "thothctl_project_cleanup":
                cmd = ["thothctl", "project", "cleanup"]
            elif name == "thothctl_project_convert":
                cmd = ["thothctl", "project", "convert"]
                if arguments.get("target_type"):
                    cmd.extend(["--target-type", arguments["target_type"]])
            
            # Remove commands
            elif name == "thothctl_remove_project":
                cmd = ["thothctl", "remove", "project", "--project-name", arguments["project_name"]]
            elif name == "thothctl_remove_space":
                cmd = ["thothctl", "remove", "space", "--space-name", arguments["space_name"]]
            
            # Scan commands
            elif name == "thothctl_scan_iac":
                cmd = ["thothctl", "scan", "iac"]
                tools = arguments.get("tools", ["checkov"])
                for tool in tools:
                    cmd.extend(["--tools", tool])
            
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            output = result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr.strip()}"
            
            return [TextContent(type="text", text=output)]
        
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    # Run server
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


if __name__ == "__main__":
    asyncio.run(serve_amazon_q())
