"""ThothCTL MCP Server — MCP SDK v2.0+ compatible (MCPServer API)."""

import asyncio
import subprocess
from typing import Optional

from mcp.server import MCPServer


def _run_cmd(cmd: list, timeout: int = 180) -> str:
    """Execute a thothctl command and return output."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode == 0:
        return result.stdout.strip()
    return f"Error (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"


server = MCPServer("thothctl")


# --- Version ---


@server.tool(name="thothctl_version", description="Get ThothCTL version information")
async def thothctl_version() -> str:
    return _run_cmd(["thothctl", "--version"])


# --- Check commands ---


@server.tool(
    name="thothctl_check_environment",
    description="Check if development environment tools are installed",
)
async def thothctl_check_environment() -> str:
    return _run_cmd(["thothctl", "check", "environment"])


@server.tool(
    name="thothctl_check_iac",
    description="Check Infrastructure as Code artifacts like tfplan",
)
async def thothctl_check_iac() -> str:
    return _run_cmd(["thothctl", "check", "iac"])


@server.tool(
    name="thothctl_check_project",
    description="Check project structure and configuration",
)
async def thothctl_check_project() -> str:
    return _run_cmd(["thothctl", "check", "project"])


# --- Document commands ---


@server.tool(
    name="thothctl_document_iac",
    description="Generate documentation for Infrastructure as Code",
)
async def thothctl_document_iac() -> str:
    return _run_cmd(["thothctl", "document", "iac"])


# --- Generate commands ---


@server.tool(
    name="thothctl_generate_stacks",
    description="Generate infrastructure stacks from YAML configuration",
)
async def thothctl_generate_stacks() -> str:
    return _run_cmd(["thothctl", "generate", "stacks"])


@server.tool(
    name="thothctl_generate_iac",
    description="Generate governed IaC from natural language intent. Uses org rules and self-correction.",
)
async def thothctl_generate_iac(
    intent: str,
    project_type: str = "auto",
    apply: bool = False,
    skip_validation: bool = False,
    self_correct: bool = True,
) -> str:
    cmd = ["thothctl", "generate", "iac", "--intent", intent]
    if project_type != "auto":
        cmd.extend(["--project-type", project_type])
    if apply:
        cmd.append("--apply")
    else:
        cmd.append("--dry-run")
    if skip_validation:
        cmd.append("--skip-validation")
    if not self_correct:
        cmd.append("--no-self-correct")
    return _run_cmd(cmd, timeout=300)


# --- Init commands ---


@server.tool(
    name="thothctl_init_env",
    description="Initialize development environment with required tools",
)
async def thothctl_init_env() -> str:
    return _run_cmd(["thothctl", "init", "env"])


@server.tool(
    name="thothctl_init_project",
    description="Initialize a new IaC project with scaffold and structure",
)
async def thothctl_init_project(
    project_name: str,
    project_type: str = "terraform-terragrunt",
    space: Optional[str] = None,
) -> str:
    cmd = [
        "thothctl",
        "init",
        "project",
        "--project-name",
        project_name,
        "--project-type",
        project_type,
    ]
    if space:
        cmd.extend(["--space", space])
    return _run_cmd(cmd)


@server.tool(
    name="thothctl_init_space",
    description="Initialize a new infrastructure space for multi-tenancy",
)
async def thothctl_init_space(space_name: str) -> str:
    return _run_cmd(["thothctl", "init", "space", "--space-name", space_name])


# --- Inventory commands ---


@server.tool(
    name="thothctl_inventory_iac",
    description="Create infrastructure inventory (SBOM) with dependency tracking",
)
async def thothctl_inventory_iac(
    check_versions: bool = False,
    project_name: Optional[str] = None,
) -> str:
    cmd = ["thothctl", "inventory", "iac"]
    if check_versions:
        cmd.append("--check-versions")
    if project_name:
        cmd.extend(["--project-name", project_name])
    return _run_cmd(cmd, timeout=300)


# --- List commands ---


@server.tool(
    name="thothctl_list_projects", description="List all IaC projects in current space"
)
async def thothctl_list_projects() -> str:
    return _run_cmd(["thothctl", "list", "projects"])


@server.tool(name="thothctl_list_spaces", description="List all infrastructure spaces")
async def thothctl_list_spaces() -> str:
    return _run_cmd(["thothctl", "list", "spaces"])


@server.tool(
    name="thothctl_list_templates",
    description="List available project templates from VCS",
)
async def thothctl_list_templates() -> str:
    return _run_cmd(["thothctl", "list", "templates"])


# --- Project commands ---


@server.tool(
    name="thothctl_project_cleanup",
    description="Clean up project cache and temporary files",
)
async def thothctl_project_cleanup() -> str:
    return _run_cmd(["thothctl", "project", "cleanup"])


@server.tool(
    name="thothctl_project_convert",
    description="Convert project to/from template format",
)
async def thothctl_project_convert(target_type: Optional[str] = None) -> str:
    cmd = ["thothctl", "project", "convert"]
    if target_type:
        cmd.extend(["--target-type", target_type])
    return _run_cmd(cmd)


# --- Remove commands ---


@server.tool(
    name="thothctl_remove_project",
    description="Remove a project from the current space",
)
async def thothctl_remove_project(project_name: str) -> str:
    return _run_cmd(["thothctl", "remove", "project", "--project-name", project_name])


@server.tool(name="thothctl_remove_space", description="Remove an infrastructure space")
async def thothctl_remove_space(space_name: str) -> str:
    return _run_cmd(["thothctl", "remove", "space", "--space-name", space_name])


# --- Scan commands ---


@server.tool(
    name="thothctl_scan_iac",
    description="Run multi-tool security scanning on IaC (Checkov, Trivy, KICS, OPA)",
)
async def thothctl_scan_iac(
    tools: Optional[list] = None,
    enforcement: Optional[str] = None,
) -> str:
    cmd = ["thothctl", "scan", "iac"]
    for tool in tools or ["checkov"]:
        cmd.extend(["--tools", tool])
    if enforcement:
        cmd.extend(["--enforcement", enforcement])
    return _run_cmd(cmd, timeout=300)


# --- Cost analysis ---


@server.tool(
    name="thothctl_cost_analysis",
    description="Analyze AWS infrastructure costs with monthly/annual projections",
)
async def thothctl_cost_analysis(recursive: bool = False) -> str:
    cmd = ["thothctl", "check", "iac", "-type", "cost-analysis"]
    if recursive:
        cmd.append("--recursive")
    return _run_cmd(cmd, timeout=120)


# --- Drift detection ---


@server.tool(
    name="thothctl_drift_detection",
    description="Detect infrastructure drift between code and deployed state",
)
async def thothctl_drift_detection(
    recursive: bool = False,
    tftool: Optional[str] = None,
    filter_tags: Optional[str] = None,
    ai_provider: Optional[str] = None,
    ai_model: Optional[str] = None,
) -> str:
    cmd = ["thothctl", "check", "iac", "-type", "drift"]
    if recursive:
        cmd.append("--recursive")
    if tftool:
        cmd.extend(["--tftool", tftool])
    if filter_tags:
        cmd.extend(["--filter-tags", filter_tags])
    if ai_provider:
        cmd.extend(["--ai-provider", ai_provider])
    if ai_model:
        cmd.extend(["--ai-model", ai_model])
    return _run_cmd(cmd, timeout=300)


# --- AI Review ---


@server.tool(
    name="thothctl_ai_review",
    description="AI-powered security review, code analysis, and automated PR decisions",
)
async def thothctl_ai_review(
    mode: str = "analyze",
    provider: Optional[str] = None,
    severity: Optional[str] = None,
    agents: Optional[list] = None,
) -> str:
    cmd = ["thothctl", "ai-review", mode]
    if provider:
        cmd.extend(["-p", provider])
    if mode == "improve" and severity:
        cmd.extend(["--severity", severity])
    if mode == "orchestrate" and agents:
        for agent in agents:
            cmd.extend(["-a", agent])
    return _run_cmd(cmd, timeout=300)


# --- Upgrade ---


@server.tool(
    name="thothctl_upgrade", description="Upgrade ThothCTL to the latest version"
)
async def thothctl_upgrade(check_only: bool = False) -> str:
    cmd = ["thothctl", "upgrade"]
    if check_only:
        cmd.append("--check-only")
    return _run_cmd(cmd)


# --- Workflow ---


@server.tool(
    name="thothctl_workflow_devsecops",
    description="Execute DevSecOps SDLC workflow phases (plan, develop, build, test, secure, deploy, monitor)",
)
async def thothctl_workflow_devsecops(
    phase: str = "all",
    enforcement: Optional[str] = None,
    policy_dir: Optional[str] = None,
    tools: Optional[list] = None,
) -> str:
    cmd = ["thothctl", "workflow", "devsecops", "--phase", phase]
    if enforcement:
        cmd.extend(["--enforcement", enforcement])
    if policy_dir:
        cmd.extend(["--policy-dir", policy_dir])
    if tools:
        for tool in tools:
            cmd.extend(["-t", tool])
    return _run_cmd(cmd, timeout=300)


@server.tool(
    name="thothctl_workflow_run",
    description="Execute a custom composable workflow from YAML definition",
)
async def thothctl_workflow_run(
    file: str,
    dry_run: bool = False,
) -> str:
    cmd = ["thothctl", "workflow", "run", "-f", file]
    if dry_run:
        cmd.append("--dry-run")
    return _run_cmd(cmd, timeout=300)


@server.tool(
    name="thothctl_quickstart",
    description="Interactive guided onboarding for new projects",
)
async def thothctl_quickstart() -> str:
    return _run_cmd(["thothctl", "quickstart"])


# --- Entry point ---


async def serve_amazon_q():
    """Run the MCP server in stdio mode."""
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(serve_amazon_q())
