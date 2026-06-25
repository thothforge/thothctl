"""Show space configuration summary."""
from pathlib import Path

import click
import toml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from ....common.common import list_spaces, get_projects_in_space
from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI


ACTIVE_SPACE_FILE = Path.home() / ".thothcf" / "active_space"


class ShowSpaceCommand(ClickCommand):
    """Command to display a space's full configuration summary."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()
        self.console = Console()

    def validate(self, space_name: str, **kwargs) -> bool:
        spaces = list_spaces()
        if space_name not in spaces:
            self.ui.print_error(f"Space '{space_name}' does not exist")
            self.ui.print_info(f"Available spaces: {', '.join(spaces) if spaces else 'none'}")
            raise ValueError(f"Space '{space_name}' does not exist")
        return True

    def _execute(self, space_name: str, **kwargs) -> None:
        config_path = Path.home() / ".thothcf" / "spaces.toml"
        config = toml.load(config_path)
        space = config["spaces"][space_name]

        # Check if this is the active space
        active_space = ""
        if ACTIVE_SPACE_FILE.exists():
            active_space = ACTIVE_SPACE_FILE.read_text(encoding="utf-8").strip()
        is_active = space_name == active_space

        # Header
        status = "🟢 ACTIVE" if is_active else "⚪ INACTIVE"
        self.console.print(Panel(
            f"[bold]{space.get('name', space_name)}[/bold] — {space.get('description', 'No description')}\n"
            f"Status: {status}  |  Created: {space.get('created_at', 'unknown')[:10]}",
            title="🌐 Space Configuration",
            border_style="cyan",
        ))

        # Configuration table
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
        table.add_column("Section", style="bold")
        table.add_column("Setting")
        table.add_column("Value")

        # VCS
        vcs = space.get("version_control", {})
        table.add_row("Version Control", "Provider", vcs.get("provider", "—"))

        # Terraform
        tf = space.get("terraform", {})
        table.add_row("Terraform", "Registry", tf.get("registry", "—"))
        table.add_row("", "Auth Method", tf.get("auth_method", "—"))

        # Orchestration
        orch = space.get("orchestration", {})
        table.add_row("Orchestration", "Tool", orch.get("tool", "—"))

        # Governance
        gov = space.get("governance", {})
        if gov:
            table.add_row("Governance", "Policy Repo", gov.get("policy_repo", "—"))

        self.console.print(table)

        # Projects in this space
        projects = get_projects_in_space(space_name)
        if projects:
            self.console.print(f"\n[bold]📦 Projects ({len(projects)}):[/bold]")
            for p in projects:
                self.console.print(f"  • {p}")
        else:
            self.console.print("\n[dim]No projects in this space.[/dim]")

        # Credentials status
        creds_path = Path.home() / ".thothcf" / "spaces" / space_name / "credentials"
        if creds_path.exists():
            cred_files = list(creds_path.iterdir())
            self.console.print(f"\n[bold]🔒 Credentials:[/bold] {len(cred_files)} stored (encrypted)")
        else:
            self.console.print("\n[dim]🔒 No credentials configured.[/dim]")


cli = ShowSpaceCommand.as_click_command(help="Show space configuration summary")(
    click.argument("space_name"),
)
