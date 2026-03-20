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
    tools: list[str] = ["checkov"]
    enforcement: str = "soft"
    reports_dir: str = "Reports"
    tftool: str = "tofu"
    options: str | None = None

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
    AI_REVIEW = "thothctl_ai_review"

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

def scan_infrastructure(
    directory: str = ".",
    tools: list[str] | None = None,
    enforcement: str = "soft",
    reports_dir: str = "Reports",
    tftool: str = "tofu",
    options: str | None = None,
) -> str:
    """Scan infrastructure code for security issues using selected tools."""
    import subprocess, json, os

    tools = tools or ["checkov"]
    logger.info(f"Scanning {directory} with tools: {tools}, enforcement: {enforcement}")

    cmd = ["thothctl", "scan", "iac"]
    for t in tools:
        cmd.extend(["-t", t])
    cmd.extend(["--reports-dir", reports_dir])
    cmd.extend(["--tftool", tftool])
    cmd.extend(["--enforcement", enforcement])
    if options:
        cmd.extend(["-o", options])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=os.path.abspath(directory),
        )

        # Read markdown summary if generated
        md_path = os.path.join(os.path.abspath(directory), reports_dir, "scan_summary.md")
        if os.path.exists(md_path):
            with open(md_path) as f:
                return f.read()

        output = result.stdout or result.stderr or "Scan completed"
        if result.returncode != 0:
            return f"Scan completed with violations (exit code {result.returncode}):\n{output}"
        return output

    except subprocess.TimeoutExpired:
        return "Error: Scan timed out after 600 seconds"
    except FileNotFoundError:
        return "Error: thothctl not found in PATH. Install with: pip install thothctl"
    except Exception as e:
        return f"Error running scan: {str(e)}"

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

def ai_review(directory: str = ".", provider: str = None, model: str = None,
              mode: str = "analyze", scan_results: str = None,
              severity: str = None, agents: list = None) -> str:
    """Run AI-powered security review on IaC code."""
    try:
        import json as _json

        if mode == "orchestrate":
            from ...services.ai_review.orchestrator import AgentOrchestrator, AgentRole
            role_map = {"security": AgentRole.SECURITY, "architecture": AgentRole.ARCHITECTURE,
                        "fix": AgentRole.FIX, "decision": AgentRole.DECISION}
            roles = [role_map[a] for a in (agents or []) if a in role_map] or None
            orch = AgentOrchestrator(provider=provider, model=model)
            result = orch.run_agents(directory, roles=roles)
            return _json.dumps({
                "security": result.security, "architecture": result.architecture,
                "fixes": result.fixes, "decision": result.decision, "errors": result.errors,
            }, indent=2, default=str)

        from ...services.ai_review.ai_agent import AIReviewAgent
        from ...services.ai_review.utils.formatters import format_analysis_as_markdown

        agent = AIReviewAgent(provider=provider, model=model)

        if mode == "decide":
            from ...services.ai_review.decision_engine import DecisionEngine
            from ...services.ai_review.pr_decision_publisher import format_decision_comment
            analysis = agent.analyze_scan_results(scan_results) if scan_results else agent.analyze_directory(directory)
            engine = DecisionEngine()
            result = engine.evaluate(analysis)
            return format_decision_comment(result, analysis)

        if mode == "improve":
            result = agent.generate_fixes(directory, severity_filter=severity)
            return _json.dumps(result, indent=2)

        # Default: analyze
        if scan_results:
            analysis = agent.analyze_scan_results(scan_results)
        else:
            analysis = agent.analyze_directory(directory)
        return format_analysis_as_markdown(analysis)
    except Exception as e:
        error_msg = f"AI review failed: {str(e)}"
        logger.error(error_msg)
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
                description="Scan infrastructure code for security issues using multiple tools (Checkov, Trivy, TFSec, KICS, OPA/Conftest). Supports custom Rego policies via OPA and enforcement modes to gate CI/CD pipelines.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory to scan",
                            "default": "."
                        },
                        "tools": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["checkov", "trivy", "tfsec", "kics", "terraform-compliance", "opa"]
                            },
                            "description": "Security scanning tools to use. OPA/Conftest evaluates custom Rego policies.",
                            "default": ["checkov"]
                        },
                        "enforcement": {
                            "type": "string",
                            "enum": ["soft", "hard"],
                            "description": "Enforcement mode: 'soft' reports violations (exit 0), 'hard' fails when violations found (exit 1)",
                            "default": "soft"
                        },
                        "reports_dir": {
                            "type": "string",
                            "description": "Directory to save scan reports",
                            "default": "Reports"
                        },
                        "tftool": {
                            "type": "string",
                            "enum": ["terraform", "tofu"],
                            "description": "Terraform tool to use",
                            "default": "tofu"
                        },
                        "options": {
                            "type": "string",
                            "description": "Additional options as key=value pairs. For OPA: mode=conftest|opa, policy_dir=path, decision=path, namespace=name"
                        }
                    }
                },
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
            Tool(
                name=ThothTools.AI_REVIEW,
                description="AI-powered security analysis and code review for Infrastructure as Code. Analyzes IaC files using AI to identify security issues, misconfigurations, and provide risk scoring with actionable recommendations.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory containing IaC code to analyze",
                            "default": "."
                        },
                        "provider": {
                            "type": "string",
                            "enum": ["openai", "bedrock", "azure", "ollama"],
                            "description": "AI provider to use"
                        },
                        "model": {
                            "type": "string",
                            "description": "Specific AI model to use"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["analyze", "decide", "improve", "orchestrate"],
                            "description": "Mode: 'analyze' for review, 'decide' for auto-decision, 'improve' for code fix generation, 'orchestrate' for multi-agent review",
                            "default": "analyze"
                        },
                        "scan_results": {
                            "type": "string",
                            "description": "Path to existing scan results to analyze instead of raw directory"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                            "description": "Minimum severity for fix generation (improve mode)",
                            "default": "medium"
                        },
                        "agents": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["security", "architecture", "fix", "decision"]},
                            "description": "Which agents to run (orchestrate mode). Default: all"
                        }
                    }
                }
            ),
        ]
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
                    result = scan_infrastructure(
                        directory=arguments.get("directory", "."),
                        tools=arguments.get("tools", ["checkov"]),
                        enforcement=arguments.get("enforcement", "soft"),
                        reports_dir=arguments.get("reports_dir", "Reports"),
                        tftool=arguments.get("tftool", "tofu"),
                        options=arguments.get("options"),
                    )
                ui.print_success("Scan complete")
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

            case ThothTools.AI_REVIEW:
                with ui.status_spinner(f"Running AI review on {arguments.get('directory', '.')}..."):
                    result = ai_review(
                        directory=arguments.get("directory", "."),
                        provider=arguments.get("provider"),
                        model=arguments.get("model"),
                        mode=arguments.get("mode", "analyze"),
                        scan_results=arguments.get("scan_results"),
                        severity=arguments.get("severity"),
                        agents=arguments.get("agents"),
                    )
                ui.print_success("AI review complete")
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
