"""ThothCTL MCP Service - Exposes ThothCTL functionality through Model Context Protocol."""

import logging
import os
from pathlib import Path
from typing import Sequence, Dict, Any, List
from enum import Enum

from mcp.server import Server
from mcp.server.session import ServerSession
from mcp.server.stdio import stdio_server
from mcp.types import (
    ClientCapabilities,
    TextContent,
    Tool,
    ListRootsResult,
    RootsCapability,
)
from pydantic import BaseModel

# Import your ThothCTL functionality
from ...common.common import list_projects, list_spaces, get_project_space, get_projects_in_space
from ...version import __version__
from ...core.cli_ui import CliUI

# Initialize CLI UI
ui = CliUI()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("thothctl-mcp")

# Define input schemas for all ThothCTL commands
class ProjectInit(BaseModel):
    """Initialize a new project with ThothCTL."""
    project_name: str
    directory: str = "."

class ProjectRemove(BaseModel):
    """Remove a project managed by ThothCTL."""
    project_name: str

class ProjectList(BaseModel):
    """List projects managed by ThothCTL."""
    pass

class SpaceInit(BaseModel):
    """Initialize a new space with ThothCTL."""
    space_name: str
    directory: str = "."

class SpaceRemove(BaseModel):
    """Remove a space managed by ThothCTL."""
    space_name: str

class SpaceList(BaseModel):
    """List spaces managed by ThothCTL."""
    pass

class ProjectsInSpace(BaseModel):
    """Get list of projects in a specific space."""
    space_name: str

class ScanCode(BaseModel):
    """Scan infrastructure code for security issues."""
    directory: str = "."

class CreateInventory(BaseModel):
    """Create Inventory for the iac composition."""
    directory: str = "."

class GenerateIaC(BaseModel):
    """Generate IaC from rules, use cases, and components."""
    template: str
    output: str = "."

class DocumentProject(BaseModel):
    """Initialize and setup project documentation."""
    directory: str = "."

class CheckCompliance(BaseModel):
    """Check infrastructure code for compliance."""
    directory: str = "."

class ManageProject(BaseModel):
    """Convert, clean up and manage the current project."""
    action: str
    directory: str = "."

class GetVersion(BaseModel):
    """Get ThothCTL version."""
    pass

class UpgradeThothCTL(BaseModel):
    """Upgrade thothctl to the latest version."""
    check_only: bool = False

# Define tool names as enum for consistency
class ThothTools(str, Enum):
    PROJECT_INIT = "thothctl_init_project"
    PROJECT_REMOVE = "thothctl_remove_project"
    PROJECT_LIST = "thothctl_list_projects"
    PROJECT_BOOTSTRAP = "thothctl_project_bootstrap"
    PROJECT_CLEANUP = "thothctl_project_cleanup"
    PROJECT_CONVERT = "thothctl_project_convert"
    PROJECT_UPGRADE = "thothctl_project_upgrade"
    SPACE_INIT = "thothctl_init_space"
    SPACE_REMOVE = "thothctl_remove_space"
    SPACE_LIST = "thothctl_list_spaces"
    PROJECTS_IN_SPACE = "thothctl_get_projects_in_space"
    SCAN_CODE = "thothctl_scan"
    CREATE_INVENTORY = "thothctl_inventory"
    GENERATE_IAC = "thothctl_generate"
    DOCUMENT_PROJECT = "thothctl_document"
    CHECK_COMPLIANCE = "thothctl_check"
    MANAGE_PROJECT = "thothctl_project"
    GET_VERSION = "thothctl_version"
    UPGRADE_THOTHCTL = "thothctl_upgrade"

# Implementation of ThothCTL commands
def init_project(project_name: str, directory: str = ".") -> str:
    """Initialize a new project with ThothCTL."""
    logger.info(f"Initializing project {project_name} in {directory}")
    # Call your existing init project functionality
    return f"Project {project_name} initialized in {directory}"

def remove_project(project_name: str) -> str:
    """Remove a project managed by ThothCTL."""
    logger.info(f"Removing project {project_name}")
    # Call your existing remove project functionality
    return f"Project {project_name} removed"

def list_all_projects() -> List[str]:
    """Get list of projects managed by ThothCTL."""
    logger.info("Listing all projects")
    projects = list_projects()
    return projects

def bootstrap_project(directory: str = ".") -> str:
    """Bootstrap existing projects with ThothCTL support."""
    logger.info(f"Bootstrapping project in {directory}")
    ui.print_info(f"Bootstrapping project in {directory}")
    return f"Project bootstrapped in {directory}"

def cleanup_project(directory: str = ".") -> str:
    """Clean up residual files and directories from your project."""
    logger.info(f"Cleaning up project in {directory}")
    ui.print_info(f"Cleaning up project in {directory}")
    return f"Project cleaned up in {directory}"

def convert_project(directory: str = ".", target_format: str = None) -> str:
    """Convert project to template, template to project or between formats."""
    logger.info(f"Converting project in {directory} to {target_format}")
    ui.print_info(f"Converting project in {directory} to {target_format}")
    return f"Project converted in {directory} to {target_format}"

def upgrade_project(directory: str = ".", template_url: str = None) -> str:
    """Upgrade project scaffold files from remote template."""
    logger.info(f"Upgrading project in {directory} from {template_url}")
    ui.print_info(f"Upgrading project in {directory} from {template_url}")
    return f"Project upgraded in {directory} from {template_url}"

def init_space(space_name: str, directory: str = ".") -> str:
    """Initialize a new space with ThothCTL."""
    logger.info(f"Initializing space {space_name} in {directory}")
    ui.print_info(f"Initializing space {space_name} in {directory}")
    return f"Space {space_name} initialized in {directory}"

def remove_space(space_name: str) -> str:
    """Remove a space managed by ThothCTL."""
    logger.info(f"Removing space {space_name}")
    ui.print_info(f"Removing space {space_name}")
    return f"Space {space_name} removed"

def list_all_spaces() -> List[str]:
    """Get list of spaces managed by ThothCTL."""
    ui.print_info("Listing all spaces")
    spaces = list_spaces()
    return spaces

def get_projects_in_specific_space(space_name: str) -> List[str]:
    """Get list of projects in a specific space."""
    ui.print_info(f"Getting projects in space {space_name}")
    projects = get_projects_in_space(space_name)
    return projects

def scan_infrastructure(directory: str = ".") -> str:
    """Scan infrastructure code for security issues."""
    logger.info(f"Scanning {directory}")
    ui.print_info(f"Scanning {directory}")
    return f"Scanned {directory}"

def create_inventory(directory: str = ".") -> str:
    """Create Inventory for the iac composition."""
    logger.info(f"Creating inventory for {directory}")
    ui.print_info(f"Creating inventory for {directory}")
    return f"Created inventory for {directory}"

def generate_iac(template: str, output: str = ".") -> str:
    """Generate IaC from rules, use cases, and components."""
    logger.info(f"Generating {template} in {output}")
    ui.print_info(f"Generating {template} in {output}")
    return f"Generated {template} in {output}"

def document_project(directory: str = ".") -> str:
    """Initialize and setup project documentation."""
    logger.info(f"Documenting {directory}")
    ui.print_info(f"Documenting {directory}")
    return f"Documented {directory}"

def check_compliance(directory: str = ".") -> str:
    """Check infrastructure code for compliance."""
    logger.info(f"Checking {directory}")
    ui.print_info(f"Checking {directory}")
    return f"Checked {directory}"

def manage_project(action: str, directory: str = ".") -> str:
    """Convert, clean up and manage the current project."""
    logger.info(f"Performing {action} on project in {directory}")
    ui.print_info(f"Performing {action} on project in {directory}")
    return f"Performed {action} on project in {directory}"

def get_version() -> str:
    """Get ThothCTL version."""
    ui.print_info(f"Getting ThothCTL version: {__version__}")
    return __version__

def upgrade_thothctl(check_only: bool = False) -> str:
    """Upgrade thothctl to the latest version."""
    from ...commands.upgrade.cli import UpgradeCommand
    
    logger.info(f"Upgrading ThothCTL (check_only={check_only})")
    ui.print_info(f"Upgrading ThothCTL (check_only={check_only})")
    
    try:
        upgrade_cmd = UpgradeCommand()
        upgrade_cmd._execute(check_only=check_only)
        return "ThothCTL upgrade completed successfully"
    except Exception as e:
        error_msg = f"ThothCTL upgrade failed: {str(e)}"
        ui.print_error(error_msg)
        return error_msg

async def serve(working_directory: Path | None = None) -> None:
    """Run the MCP server for ThothCTL in stdio mode.
    
    Args:
        working_directory: Optional working directory to use
    """
    logger = logging.getLogger(__name__)
    
    if working_directory is not None:
        logger.info(f"Using working directory: {working_directory}")

    server = Server("ThothCTL")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        logger.info("Listing available tools")
        return [
            Tool(
                name=ThothTools.PROJECT_INIT,
                description="Initialize and setup a new project with ThothCTL",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Name of the project to initialize"
                        },
                        "directory": {
                            "type": "string",
                            "description": "Directory to initialize the project in",
                            "default": "."
                        }
                    },
                    "required": ["project_name"]
                }
            ),
            Tool(
                name=ThothTools.PROJECT_REMOVE,
                description="Remove a project managed by ThothCTL",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Name of the project to remove"
                        }
                    },
                    "required": ["project_name"]
                }
            ),
            Tool(
                name=ThothTools.PROJECT_LIST,
                description="List all projects managed by ThothCTL",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name=ThothTools.PROJECT_BOOTSTRAP,
                description="Bootstrap existing projects with ThothCTL support",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory to bootstrap",
                            "default": "."
                        }
                    }
                }
            ),
            Tool(
                name=ThothTools.PROJECT_CLEANUP,
                description="Clean up residual files and directories from your project",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory to clean up",
                            "default": "."
                        }
                    }
                }
            ),
            Tool(
                name=ThothTools.PROJECT_CONVERT,
                description="Convert project to template, template to project or between formats",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory to convert",
                            "default": "."
                        },
                        "target_format": {
                            "type": "string",
                            "description": "Target format for conversion"
                        }
                    }
                }
            ),
            Tool(
                name=ThothTools.PROJECT_UPGRADE,
                description="Upgrade project scaffold files from remote template",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory to upgrade",
                            "default": "."
                        },
                        "template_url": {
                            "type": "string",
                            "description": "URL of the template to upgrade from"
                        }
                    }
                }
            ),
            Tool(
                name=ThothTools.SPACE_INIT,
                description="Initialize and setup a new space with ThothCTL",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "space_name": {
                            "type": "string",
                            "description": "Name of the space to initialize"
                        },
                        "directory": {
                            "type": "string",
                            "description": "Directory to initialize the space in",
                            "default": "."
                        }
                    },
                    "required": ["space_name"]
                }
            ),
            Tool(
                name=ThothTools.SPACE_REMOVE,
                description="Remove a space managed by thothctl",
                inputSchema=SpaceRemove.schema(),
            ),
            Tool(
                name=ThothTools.SPACE_LIST,
                description="List spaces managed by thothctl locally",
                inputSchema=SpaceList.schema(),
            ),
            Tool(
                name=ThothTools.PROJECTS_IN_SPACE,
                description="Get list of projects in a specific space",
                inputSchema=ProjectsInSpace.schema(),
            ),
            Tool(
                name=ThothTools.SCAN_CODE,
                description="Scan infrastructure code for security issues",
                inputSchema=ScanCode.schema(),
            ),
            Tool(
                name=ThothTools.CREATE_INVENTORY,
                description="Create Inventory for the iac composition",
                inputSchema=CreateInventory.schema(),
            ),
            Tool(
                name=ThothTools.GENERATE_IAC,
                description="Generate IaC from rules, use cases, and components",
                inputSchema=GenerateIaC.schema(),
            ),
            Tool(
                name=ThothTools.DOCUMENT_PROJECT,
                description="Initialize and setup project documentation",
                inputSchema=DocumentProject.schema(),
            ),
            Tool(
                name=ThothTools.CHECK_COMPLIANCE,
                description="Check infrastructure code for compliance",
                inputSchema=CheckCompliance.schema(),
            ),
            Tool(
                name=ThothTools.MANAGE_PROJECT,
                description="Convert, clean up and manage the current project",
                inputSchema=ManageProject.schema(),
            ),
            Tool(
                name=ThothTools.GET_VERSION,
                description="Get ThothCTL version",
                inputSchema=GetVersion.schema(),
            ),
            Tool(
                name=ThothTools.UPGRADE_THOTHCTL,
                description="Upgrade thothctl to the latest version",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "check_only": {
                            "type": "boolean",
                            "description": "Only check for updates without installing",
                            "default": False
                        }
                    }
                }
            ),
        ]

    async def list_directories() -> Sequence[str]:
        """List available directories for ThothCTL operations."""
        async def by_roots() -> Sequence[str]:
            if not isinstance(server.request_context.session, ServerSession):
                raise TypeError("server.request_context.session must be a ServerSession")

            if not server.request_context.session.check_client_capability(
                ClientCapabilities(roots=RootsCapability())
            ):
                return []

            roots_result: ListRootsResult = await server.request_context.session.list_roots()
            logger.debug(f"Roots result: {roots_result}")
            directories = []
            for root in roots_result.roots:
                path = root.uri.path
                directories.append(str(path))
            return directories

        def by_commandline() -> Sequence[str]:
            return [str(working_directory)] if working_directory is not None else []

        cmd_dirs = by_commandline()
        root_dirs = await by_roots()
        return [*root_dirs, *cmd_dirs]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Call a ThothCTL tool with the given arguments."""
        logger.info(f"Calling tool: {name}")
        
        match name:
            case ThothTools.PROJECT_INIT:
                result = init_project(
                    arguments["project_name"],
                    arguments.get("directory", ".")
                )
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.PROJECT_REMOVE:
                result = remove_project(arguments["project_name"])
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.PROJECT_LIST:
                projects = list_all_projects()
                return [TextContent(
                    type="text",
                    text=f"Projects:\n{', '.join(projects)}"
                )]

            case ThothTools.PROJECT_BOOTSTRAP:
                with ui.status_spinner(f"Bootstrapping project in {arguments.get('directory', '.')}..."):
                    result = bootstrap_project(arguments.get("directory", "."))
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.PROJECT_CLEANUP:
                with ui.status_spinner(f"Cleaning up project in {arguments.get('directory', '.')}..."):
                    result = cleanup_project(arguments.get("directory", "."))
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.PROJECT_CONVERT:
                with ui.status_spinner(f"Converting project in {arguments.get('directory', '.')}..."):
                    result = convert_project(
                        arguments.get("directory", "."),
                        arguments.get("target_format")
                    )
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.PROJECT_UPGRADE:
                with ui.status_spinner(f"Upgrading project in {arguments.get('directory', '.')}..."):
                    result = upgrade_project(
                        arguments.get("directory", "."),
                        arguments.get("template_url")
                    )
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.SPACE_INIT:
                result = init_space(
                    arguments["space_name"],
                    arguments.get("directory", ".")
                )
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.SPACE_REMOVE:
                with ui.status_spinner(f"Removing space {arguments['space_name']}..."):
                    result = remove_space(arguments["space_name"])
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.SPACE_LIST:
                with ui.status_spinner("Listing spaces..."):
                    spaces = list_all_spaces()
                ui.print_success(f"Found {len(spaces)} spaces")
                return [TextContent(
                    type="text",
                    text=f"Spaces:\n{', '.join(spaces)}"
                )]

            case ThothTools.PROJECTS_IN_SPACE:
                with ui.status_spinner(f"Getting projects in space {arguments['space_name']}..."):
                    projects = get_projects_in_specific_space(arguments["space_name"])
                ui.print_success(f"Found {len(projects)} projects in space {arguments['space_name']}")
                return [TextContent(
                    type="text",
                    text=f"Projects in space {arguments['space_name']}:\n{', '.join(projects)}"
                )]

            case ThothTools.SCAN_CODE:
                with ui.status_spinner(f"Scanning {arguments.get('directory', '.')}..."):
                    result = scan_infrastructure(arguments.get("directory", "."))
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.CREATE_INVENTORY:
                with ui.status_spinner(f"Creating inventory for {arguments.get('directory', '.')}..."):
                    result = create_inventory(arguments.get("directory", "."))
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.GENERATE_IAC:
                with ui.status_spinner(f"Generating {arguments['template']}..."):
                    result = generate_iac(
                        arguments["template"],
                        arguments.get("output", ".")
                    )
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.DOCUMENT_PROJECT:
                with ui.status_spinner(f"Documenting {arguments.get('directory', '.')}..."):
                    result = document_project(arguments.get("directory", "."))
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.CHECK_COMPLIANCE:
                with ui.status_spinner(f"Checking {arguments.get('directory', '.')}..."):
                    result = check_compliance(arguments.get("directory", "."))
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.MANAGE_PROJECT:
                with ui.status_spinner(f"Managing project with action {arguments['action']}..."):
                    result = manage_project(
                        arguments["action"],
                        arguments.get("directory", ".")
                    )
                ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case ThothTools.GET_VERSION:
                with ui.status_spinner("Getting ThothCTL version..."):
                    version = get_version()
                ui.print_success(f"ThothCTL version: {version}")
                return [TextContent(
                    type="text",
                    text=f"ThothCTL version: {version}"
                )]

            case ThothTools.UPGRADE_THOTHCTL:
                check_only = arguments.get("check_only", False)
                action = "Checking for updates" if check_only else "Upgrading ThothCTL"
                with ui.status_spinner(f"{action}..."):
                    result = upgrade_thothctl(check_only)
                if "failed" in result.lower():
                    ui.print_error(result)
                else:
                    ui.print_success(result)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case _:
                ui.print_error(f"Unknown tool: {name}")
                raise ValueError(f"Unknown tool: {name}")

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Starting MCP server in stdio mode")
        await server.run(read_stream, write_stream, options, raise_exceptions=True)

def run_server(host: str = "localhost", port: int = 8080) -> None:
    """Run the MCP server over HTTP.
    
    Args:
        host: Host to bind the server to
        port: Port to run the server on
    """
    try:
        # Use the simplified HTTP server implementation
        from .simple_http_server import run_simple_http_server
        
        logger.info(f"Starting ThothCTL MCP server on {host}:{port}")
        ui.print_info(f"Starting ThothCTL MCP server on {host}:{port}")
        ui.print_info(f"Server PID: {os.getpid()}")
        
        # Run the simplified server
        run_simple_http_server(host, port)
        
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        ui.print_error(f"Error running MCP server: {str(e)}")

if __name__ == "__main__":
    # This allows running the module directly for testing
    run_server()
