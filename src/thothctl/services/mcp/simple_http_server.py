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
                        "directory": {"type": "string", "description": "Directory to initialize in", "default": "."},
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
                "description": "Scan infrastructure code for security issues using multiple tools (Checkov, Trivy, TFSec, KICS, OPA/Conftest). Supports custom Rego policies and enforcement modes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."},
                        "tools": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["checkov", "trivy", "tfsec", "kics", "terraform-compliance", "opa"]},
                            "default": ["checkov"]
                        },
                        "enforcement": {
                            "type": "string",
                            "enum": ["soft", "hard"],
                            "description": "soft=report only, hard=exit 1 on violations",
                            "default": "soft"
                        },
                        "reports_dir": {"type": "string", "default": "Reports"},
                        "tftool": {"type": "string", "enum": ["terraform", "tofu"], "default": "tofu"},
                        "options": {
                            "type": "string",
                            "description": "Additional key=value options. For OPA: mode=conftest|opa, policy_dir=path, decision=path"
                        }
                    }
                }
            },
            {
                "name": "thothctl_version",
                "description": "Get ThothCTL version",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "thothctl_cost_analysis",
                "description": "Estimate AWS infrastructure costs from Terraform plans or CloudFormation templates. Provides monthly/annual projections, service-by-service breakdown, and optimization recommendations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."},
                        "recursive": {"type": "boolean", "default": False}
                    }
                }
            },
            {
                "name": "thothctl_drift_detection",
                "description": "Detect infrastructure drift by comparing IaC state against live cloud resources. Supports tag filtering, policy enforcement, coverage trending, and AI-powered analysis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."},
                        "recursive": {"type": "boolean", "default": False},
                        "tftool": {"type": "string", "enum": ["terraform", "tofu"], "default": "tofu"},
                        "filter_tags": {"type": "string", "description": "Tag filter (e.g. 'env=prod,team=platform')"},
                        "ai_provider": {"type": "string", "enum": ["openai", "bedrock", "azure", "ollama"]},
                        "ai_model": {"type": "string"},
                        "project_name": {"type": "string"}
                    }
                }
            },
            {
                "name": "thothctl_ai_review",
                "description": "AI-powered security analysis and code review for Infrastructure as Code. Supports analyze, decide, improve, and orchestrate modes with multiple AI providers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."},
                        "provider": {"type": "string", "enum": ["openai", "bedrock", "azure", "ollama"]},
                        "model": {"type": "string"},
                        "mode": {"type": "string", "enum": ["analyze", "decide", "improve", "orchestrate"], "default": "analyze"},
                        "scan_results": {"type": "string", "description": "Path to existing scan results to analyze"},
                        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                        "agents": {"type": "array", "items": {"type": "string", "enum": ["security", "architecture", "fix", "decision"]}}
                    }
                }
            },
            {
                "name": "thothctl_remove_project",
                "description": "Remove a project managed by ThothCTL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string", "description": "Name of the project to remove"}
                    },
                    "required": ["project_name"]
                }
            },
            {
                "name": "thothctl_init_space",
                "description": "Initialize a new space with ThothCTL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "space_name": {"type": "string", "description": "Name of the space"},
                        "directory": {"type": "string", "default": "."}
                    },
                    "required": ["space_name"]
                }
            },
            {
                "name": "thothctl_remove_space",
                "description": "Remove a space managed by ThothCTL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "space_name": {"type": "string", "description": "Name of the space to remove"}
                    },
                    "required": ["space_name"]
                }
            },
            {
                "name": "thothctl_get_projects_in_space",
                "description": "Get list of projects in a specific space",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "space_name": {"type": "string", "description": "Space name"}
                    },
                    "required": ["space_name"]
                }
            },
            {
                "name": "thothctl_project_bootstrap",
                "description": "Bootstrap existing projects with ThothCTL support",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."}
                    }
                }
            },
            {
                "name": "thothctl_project_cleanup",
                "description": "Clean up residual files and directories from your project",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."}
                    }
                }
            },
            {
                "name": "thothctl_project_convert",
                "description": "Convert project to template or template to project",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."},
                        "target_format": {"type": "string", "description": "Target format for conversion"}
                    }
                }
            },
            {
                "name": "thothctl_project_upgrade",
                "description": "Upgrade project scaffold files from remote template",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."},
                        "template_url": {"type": "string", "description": "URL of the template to upgrade from"}
                    }
                }
            },
            {
                "name": "thothctl_generate",
                "description": "Generate IaC components or stacks from rules and templates",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template": {"type": "string", "description": "Template to generate from"},
                        "output": {"type": "string", "default": "."}
                    },
                    "required": ["template"]
                }
            },
            {
                "name": "thothctl_document",
                "description": "Generate documentation for IaC projects",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."}
                    }
                }
            },
            {
                "name": "thothctl_check",
                "description": "Check infrastructure code: environment validation, project structure, or compliance",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."},
                        "check_type": {"type": "string", "enum": ["environment", "project", "space"], "default": "project"}
                    }
                }
            },
            {
                "name": "thothctl_project",
                "description": "Manage project: convert, clean up, bootstrap, or upgrade",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["bootstrap", "cleanup", "convert", "upgrade"]},
                        "directory": {"type": "string", "default": "."}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "thothctl_upgrade",
                "description": "Upgrade thothctl to the latest version",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "check_only": {"type": "boolean", "default": False}
                    }
                }
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
            cmd.extend(["--enforcement", arguments.get("enforcement", "soft")])
            cmd.extend(["--reports-dir", arguments.get("reports_dir", "Reports")])
            cmd.extend(["--tftool", arguments.get("tftool", "tofu")])
            if arguments.get("options"):
                cmd.extend(["-o", arguments["options"]])
        elif name == "thothctl_version":
            cmd.append("--version")
        elif name == "thothctl_cost_analysis":
            cmd.extend(["check", "iac", "-type", "cost-analysis"])
            if arguments.get("recursive", False):
                cmd.append("--recursive")
        elif name == "thothctl_drift_detection":
            cmd.extend(["check", "iac", "-type", "drift"])
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
            if arguments.get("project_name"):
                cmd.extend(["--project-name", arguments["project_name"]])
        elif name == "thothctl_ai_review":
            mode = arguments.get("mode", "analyze")
            cmd.extend(["ai-review", mode])
            if arguments.get("provider"):
                cmd.extend(["-p", arguments["provider"]])
            if arguments.get("model"):
                cmd.extend(["--model", arguments["model"]])
            if mode == "improve" and arguments.get("severity"):
                cmd.extend(["--severity", arguments["severity"]])
            if mode == "orchestrate" and arguments.get("agents"):
                for agent in arguments["agents"]:
                    cmd.extend(["-a", agent])
        elif name == "thothctl_remove_project":
            cmd.extend(["remove", "-pj", arguments["project_name"]])
        elif name == "thothctl_init_space":
            cmd.extend(["init", "space", "--name", arguments["space_name"]])
        elif name == "thothctl_remove_space":
            cmd.extend(["remove", "-sp", arguments["space_name"]])
        elif name == "thothctl_get_projects_in_space":
            cmd.extend(["list", "projects", "--space", arguments["space_name"]])
        elif name == "thothctl_project_bootstrap":
            cmd.extend(["project", "bootstrap"])
        elif name == "thothctl_project_cleanup":
            cmd.extend(["project", "cleanup"])
        elif name == "thothctl_project_convert":
            cmd.extend(["project", "convert"])
            if arguments.get("target_format"):
                cmd.extend(["--template-project-type", arguments["target_format"]])
        elif name == "thothctl_project_upgrade":
            cmd.extend(["project", "upgrade"])
            if arguments.get("template_url"):
                cmd.extend(["--template-url", arguments["template_url"]])
        elif name == "thothctl_generate":
            cmd.extend(["generate", "component", "--template", arguments["template"]])
        elif name == "thothctl_document":
            cmd.extend(["document", "iac"])
        elif name == "thothctl_check":
            check_type = arguments.get("check_type", "project")
            if check_type == "environment":
                cmd.extend(["check", "environment"])
            elif check_type == "space":
                cmd.extend(["check", "space"])
            else:
                cmd.extend(["check", "project", "iac"])
        elif name == "thothctl_project":
            action = arguments["action"]
            cmd.extend(["project", action])
        elif name == "thothctl_upgrade":
            cmd.extend(["upgrade"])
            if arguments.get("check_only", False):
                cmd.append("--check-only")
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
