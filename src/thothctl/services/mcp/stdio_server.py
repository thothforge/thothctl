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
            Tool(
                name="thothctl_generate_iac",
                description="Generate governed Infrastructure as Code from natural language intent. "
                            "Uses organizational rules from .thothcf.toml and validates output with Checkov/OPA. "
                            "Supports self-correction: if validation fails, the AI fixes violations automatically.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "description": "Natural language description of the infrastructure to generate"
                        },
                        "project_type": {
                            "type": "string",
                            "description": "Target IaC project type",
                            "default": "auto",
                            "enum": ["auto", "terraform", "terraform-terragrunt", "terragrunt", "cloudformation", "cdkv2"]
                        },
                        "self_correct": {
                            "type": "boolean",
                            "default": True,
                            "description": "Re-prompt AI to fix validation violations (max 3 iterations)"
                        },
                        "apply": {
                            "type": "boolean",
                            "default": False,
                            "description": "Write files to disk (False = dry-run, returns file contents only)"
                        },
                        "skip_validation": {
                            "type": "boolean",
                            "default": False,
                            "description": "Skip Checkov/OPA validation"
                        }
                    },
                    "required": ["intent"],
                    "additionalProperties": False
                }
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
                        "space": {"type": "string", "description": "Space name (optional)"},
                        "language": {"type": "string", "description": "CDK language (only for cdkv2)", "enum": ["typescript", "python", "java", "csharp", "go"]}
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
                        "tools": {"type": "array", "items": {"type": "string"}, "description": "Security tools to use", "default": ["checkov"]},
                        "enforcement": {"type": "string", "enum": ["soft", "hard"], "description": "soft=report only, hard=exit 1 on violations", "default": "soft"}
                    },
                    "additionalProperties": False
                }
            ),

            # Cost analysis
            Tool(
                name="thothctl_cost_analysis",
                description="Estimate AWS infrastructure costs from Terraform plans or CloudFormation templates. Provides monthly/annual projections, service-by-service breakdown, and optimization recommendations.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "recursive": {"type": "boolean", "description": "Search recursively for plan files", "default": False}
                    },
                    "additionalProperties": False
                }
            ),

            # Drift detection
            Tool(
                name="thothctl_drift_detection",
                description="Detect infrastructure drift between IaC state and live cloud resources. Supports tag filtering, policy enforcement, coverage trending, and AI-powered analysis.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "recursive": {"type": "boolean", "description": "Search recursively", "default": False},
                        "tftool": {"type": "string", "enum": ["terraform", "tofu"], "default": "tofu"},
                        "filter_tags": {"type": "string", "description": "Tag filter (e.g. 'env=prod,team=platform')"},
                        "ai_provider": {"type": "string", "enum": ["openai", "bedrock", "azure", "ollama"]},
                        "ai_model": {"type": "string"}
                    },
                    "additionalProperties": False
                }
            ),

            # AI review
            Tool(
                name="thothctl_ai_review",
                description="AI-powered security analysis and code review for Infrastructure as Code. Supports analyze, decide, improve, and orchestrate modes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string", "enum": ["openai", "bedrock", "azure", "ollama"]},
                        "mode": {"type": "string", "enum": ["analyze", "decide", "improve", "orchestrate"], "default": "analyze"},
                        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                        "agents": {"type": "array", "items": {"type": "string", "enum": ["security", "architecture", "fix", "decision"]}}
                    },
                    "additionalProperties": False
                }
            ),

            # Upgrade
            Tool(
                name="thothctl_upgrade",
                description="Upgrade thothctl to the latest version",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "check_only": {"type": "boolean", "description": "Only check for updates without installing", "default": False}
                    },
                    "additionalProperties": False
                }
            ),

            # Workflow
            Tool(
                name="thothctl_workflow_devsecops",
                description="Execute DevSecOps SDLC workflow phases. Orchestrates multiple commands into cohesive phases: plan (cost + blast-radius), develop (environment + structure + docs), build (inventory + versions), test (tfplan validation), secure (checkov + trivy + opa), deploy (enforcement gate), monitor (drift detection). Use 'pre-deploy' for test+secure combined, or 'all' for full pipeline.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "phase": {
                            "type": "string",
                            "enum": ["plan", "develop", "build", "test", "secure", "deploy", "monitor", "pre-deploy", "all"],
                            "default": "all",
                            "description": "SDLC phase to execute"
                        },
                        "enforcement": {
                            "type": "string",
                            "enum": ["soft", "hard"],
                            "default": "soft",
                            "description": "soft=report only, hard=exit 1 on violations"
                        },
                        "policy_dir": {
                            "type": "string",
                            "description": "OPA policy directory or Git URL for secure phase"
                        },
                        "tools": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Override scan tools for secure phase (e.g. ['checkov', 'trivy', 'opa'])"
                        }
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
            elif name == "thothctl_generate_iac":
                cmd = ["thothctl", "generate", "iac", "--intent", arguments["intent"]]
                if arguments.get("project_type", "auto") != "auto":
                    cmd.extend(["--project-type", arguments["project_type"]])
                if arguments.get("apply"):
                    cmd.append("--apply")
                else:
                    cmd.append("--dry-run")
                if arguments.get("skip_validation"):
                    cmd.append("--skip-validation")
                if not arguments.get("self_correct", True):
                    cmd.append("--no-self-correct")
            
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
                if arguments.get("enforcement"):
                    cmd.extend(["--enforcement", arguments["enforcement"]])

            # Cost analysis
            elif name == "thothctl_cost_analysis":
                cmd = ["thothctl", "check", "iac", "-type", "cost-analysis"]
                if arguments.get("recursive", False):
                    cmd.append("--recursive")

            # Drift detection
            elif name == "thothctl_drift_detection":
                cmd = ["thothctl", "check", "iac", "-type", "drift"]
                if arguments.get("recursive", False):
                    cmd.append("--recursive")
                if arguments.get("tftool"):
                    cmd.extend(["--tftool", arguments["tftool"]])
                if arguments.get("filter_tags"):
                    cmd.extend(["--filter-tags", arguments["filter_tags"]])
                if arguments.get("ai_provider"):
                    cmd.extend(["--ai-provider", arguments["ai_provider"]])
                if arguments.get("ai_model"):
                    cmd.extend(["--ai-model", arguments["ai_model"]])

            # AI review
            elif name == "thothctl_ai_review":
                mode = arguments.get("mode", "analyze")
                cmd = ["thothctl", "ai-review", mode]
                if arguments.get("provider"):
                    cmd.extend(["-p", arguments["provider"]])
                if mode == "improve" and arguments.get("severity"):
                    cmd.extend(["--severity", arguments["severity"]])
                if mode == "orchestrate" and arguments.get("agents"):
                    for agent in arguments["agents"]:
                        cmd.extend(["-a", agent])

            # Upgrade
            elif name == "thothctl_upgrade":
                cmd = ["thothctl", "upgrade"]
                if arguments.get("check_only", False):
                    cmd.append("--check-only")

            # Workflow
            elif name == "thothctl_workflow_devsecops":
                cmd = ["thothctl", "workflow", "devsecops"]
                phase = arguments.get("phase", "all")
                cmd.extend(["--phase", phase])
                if arguments.get("enforcement"):
                    cmd.extend(["--enforcement", arguments["enforcement"]])
                if arguments.get("policy_dir"):
                    cmd.extend(["--policy-dir", arguments["policy_dir"]])
                if arguments.get("tools"):
                    for tool in arguments["tools"]:
                        cmd.extend(["-t", tool])
            
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
