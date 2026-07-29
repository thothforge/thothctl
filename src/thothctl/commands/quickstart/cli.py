"""Quickstart — guided onboarding for ThothCTL."""

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...core.cli_ui import CliUI

logger = logging.getLogger(__name__)
console = Console()


# Detection markers for project types
DETECTION_MARKERS = {
    "terraform": ["*.tf"],
    "terraform-terragrunt": ["terragrunt.hcl"],
    "cdkv2": ["cdk.json"],
    "tofu": [".terraform.lock.hcl"],  # combined with no .tf = tofu
}


def detect_project_type(directory: Path) -> Optional[str]:
    """Detect project type from marker files in directory."""
    # Check for .thothcf.toml first (already managed)
    thothcf = directory / ".thothcf.toml"
    if thothcf.exists():
        try:
            import toml

            config = toml.load(thothcf)
            pt = config.get("thothcf", {}).get("project_type")
            if pt:
                return pt
        except Exception:
            pass

    # Check marker files
    if (directory / "cdk.json").exists():
        return "cdkv2"
    if (directory / "terragrunt.hcl").exists():
        return "terraform-terragrunt"
    if list(directory.glob("*.tf")):
        return "terraform"

    return None


@click.command()
@click.option(
    "-pt",
    "--project-type",
    type=click.Choice(
        ["terraform", "terraform-terragrunt", "tofu", "cdkv2", "terraform_module"],
        case_sensitive=False,
    ),
    default=None,
    help="Project type (auto-detected if omitted)",
)
@click.option(
    "-p",
    "--project-name",
    default=None,
    help="Project name for new project initialization",
)
@click.pass_context
def cli(ctx, project_type, project_name):
    """Guided onboarding — get started with ThothCTL in under 2 minutes."""
    ui = CliUI()
    cwd = Path.cwd()

    console.print()
    console.print(
        Panel(
            "[bold]Welcome to ThothCTL![/bold]\n"
            "This wizard will set up your project for DevSecOps in under 2 minutes.",
            title="🚀 Quickstart",
            border_style="cyan",
        )
    )

    # Step 1: Detect or ask for project type
    detected = detect_project_type(cwd)

    if detected:
        console.print(
            f"\n[bold]✅ Detected project:[/bold] [green]{detected}[/green] (in {cwd.name}/)"
        )
        project_type = detected
    elif project_type:
        console.print(
            f"\n[bold]📝 Project type:[/bold] [green]{project_type}[/green] (from flag)"
        )
    else:
        # Interactive selection
        import inquirer

        questions = [
            inquirer.List(
                "project_type",
                message="What type of IaC project is this?",
                choices=[
                    "terraform-terragrunt",
                    "terraform",
                    "cdkv2",
                    "tofu",
                    "terraform_module",
                ],
            )
        ]
        answers = inquirer.prompt(questions)
        if not answers:
            ui.print_error("Cancelled.")
            return
        project_type = answers["project_type"]

    # Step 2: Check if already a ThothCTL project or needs init
    is_managed = (cwd / ".thothcf.toml").exists()

    if not is_managed and not detected:
        # Need to create a new project
        if not project_name:
            project_name = cwd.name
            console.print(
                f"\n[bold]📝 Project name:[/bold] [green]{project_name}[/green] (from directory)"
            )
        console.print("\n[yellow]Project not yet managed by ThothCTL. Run:[/yellow]")
        console.print(
            f"  [cyan]thothctl init project -p {project_name} --project-type {project_type}[/cyan]"
        )
        console.print()
    elif is_managed:
        console.print("\n[bold]✅ Project is managed by ThothCTL[/bold]")

    # Step 3: Check environment
    console.print("\n[bold]🔍 Checking development environment...[/bold]\n")
    try:
        from ...services.check.environment.check_environment import EnvironmentChecker

        checker = EnvironmentChecker()
        results = checker.check_environment()
        missing = results.get("missing", [])
    except Exception as e:
        logger.debug(f"Environment check failed: {e}")
        missing = []

    # Step 4: Quick scan suggestion
    console.print("\n[bold]🔒 Security Scan[/bold]")
    has_code = detected is not None or is_managed
    if has_code:
        console.print("  Run your first security scan with:")
        console.print("  [cyan]thothctl scan iac -t checkov[/cyan]")
    else:
        console.print("  [dim]No IaC code detected to scan yet.[/dim]")

    # Step 5: Summary with next steps
    console.print()
    next_steps = Table(title="📋 Next Steps", show_header=True, header_style="bold")
    next_steps.add_column("#", style="bold cyan", width=3)
    next_steps.add_column("Action")
    next_steps.add_column("Command", style="cyan")

    step_num = 1
    if missing:
        next_steps.add_row(
            str(step_num),
            "Install missing tools",
            "thothctl init env --project-type " + project_type,
        )
        step_num += 1
    if not is_managed and not detected:
        next_steps.add_row(
            str(step_num),
            "Initialize project",
            f"thothctl init project -p {project_name or cwd.name} --project-type {project_type}",
        )
        step_num += 1
    if has_code:
        next_steps.add_row(
            str(step_num), "Run security scan", "thothctl scan iac -t checkov -t trivy"
        )
        step_num += 1
        next_steps.add_row(
            str(step_num),
            "Generate inventory",
            "thothctl inventory iac --check-versions",
        )
        step_num += 1
    next_steps.add_row(str(step_num), "View dashboard", "thothctl dashboard launch")
    step_num += 1
    next_steps.add_row(
        str(step_num),
        "Full DevSecOps pipeline",
        "thothctl workflow devsecops --phase all",
    )

    console.print(next_steps)
    console.print()
    console.print("[dim]Documentation: https://thothforge.github.io/thothctl/[/dim]")
