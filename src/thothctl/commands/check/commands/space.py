"""Check space command."""

import click
from pathlib import Path
from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


class CheckSpaceCommand(ClickCommand):
    """Command to check space configuration and setup."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def _execute(self, space_name: str, **kwargs) -> None:
        """Execute space configuration check"""
        if not space_name:
            self.ui.print_error("Space name is required")
            return

        self.ui.print_info(f"🔍 Checking space configuration: {space_name}")
        
        # Check if space exists
        space_path = Path.home() / ".thothcf" / "spaces" / space_name
        if not space_path.exists():
            self.ui.print_error(f"Space '{space_name}' does not exist")
            return

        # Display space overview
        self._display_space_overview(space_name, space_path)
        
        # Check VCS configuration
        self._check_vcs_configuration(space_name, space_path)
        
        # Check credentials
        self._check_credentials(space_name, space_path)
        
        # Check projects using this space
        self._check_space_projects(space_name)

    def _display_space_overview(self, space_name: str, space_path: Path) -> None:
        """Display space overview information"""
        config_file = space_path / "space.toml"
        
        if config_file.exists():
            import toml
            try:
                config = toml.load(config_file)
                
                # Create overview table
                table = Table(title=f"🌌 Space Overview: {space_name}")
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="green")
                
                space_info = config.get("space", {})
                table.add_row("Name", space_info.get("name", space_name))
                table.add_row("Version", space_info.get("version", "N/A"))
                table.add_row("Path", str(space_path))
                
                # Add configuration paths
                configs = config.get("configurations", {})
                table.add_row("Config Path", configs.get("path", "configs"))
                
                credentials = config.get("credentials", {})
                table.add_row("Credentials Path", credentials.get("path", "credentials"))
                
                self.ui.console.print(table)
                
            except Exception as e:
                self.ui.print_error(f"Failed to read space config: {e}")
        else:
            self.ui.print_warning(f"No config file found for space '{space_name}'")

    def _check_vcs_configuration(self, space_name: str, space_path: Path) -> None:
        """Check VCS configuration"""
        vcs_config_file = space_path / "space.toml"
        
        if vcs_config_file.exists():
            import toml
            try:
                vcs_config = toml.load(vcs_config_file)
                
                # Create VCS configuration table
                table = Table(title="🔄 VCS Configuration")
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="green")
                table.add_column("Status", style="yellow")
                
                # Get VCS configuration from space.toml structure
                version_control = vcs_config.get("version_control", {})
                provider = version_control.get("default_provider", "N/A")
                providers = version_control.get("providers", [])
                
                table.add_row("Default Provider", provider, "✅ Configured")
                table.add_row("Available Providers", ", ".join(providers), "✅ Set")
                table.add_row("VCS Path", version_control.get("path", "vcs"), "✅ Set")
                
                self.ui.console.print(table)
                
            except Exception as e:
                self.ui.print_error(f"Failed to read VCS config: {e}")
        else:
            self.ui.print_warning("No VCS configuration found")

    def _check_credentials(self, space_name: str, space_path: Path) -> None:
        """Check credentials availability"""
        credentials_path = space_path / "credentials"
        
        # Create credentials table
        table = Table(title="🔒 Credentials Status")
        table.add_column("Type", style="cyan")
        table.add_column("File", style="white")
        table.add_column("Status", style="yellow")
        table.add_column("Details", style="dim")
        
        credential_types = ["vcs", "terraform", "cloud"]
        
        for cred_type in credential_types:
            cred_file = credentials_path / f"{cred_type}.enc"
            if cred_file.exists():
                table.add_row(
                    cred_type.upper(),
                    f"{cred_type}.enc",
                    "✅ Available",
                    f"Size: {cred_file.stat().st_size} bytes"
                )
            else:
                table.add_row(
                    cred_type.upper(),
                    f"{cred_type}.enc",
                    "❌ Missing",
                    "Not configured"
                )
        
        self.ui.console.print(table)

    def _check_space_projects(self, space_name: str) -> None:
        """Check projects using this space"""
        try:
            from ....common.common import list_projects, check_info_project
            
            project_names = list_projects()
            space_projects = []
            
            for project_name in project_names:
                try:
                    # Get project info to check space
                    project_info = check_info_project(project_name)
                    if project_info and isinstance(project_info, dict):
                        thothcf_info = project_info.get("thothcf", {})
                        if thothcf_info.get("space") == space_name:
                            space_projects.append(project_name)
                except Exception:
                    # Skip projects that can't be read
                    continue
            
            # Create projects table
            if space_projects:
                table = Table(title=f"📁 Projects using space '{space_name}'")
                table.add_column("Project Name", style="green")
                table.add_column("Status", style="yellow")
                
                for project_name in space_projects:
                    table.add_row(project_name, "✅ Active")
                
                self.ui.console.print(table)
            else:
                self.ui.console.print(Panel(
                    Text(f"No projects are currently using space '{space_name}'", style="dim"),
                    title="📁 Projects",
                    border_style="yellow"
                ))
                
        except Exception as e:
            self.ui.print_error(f"Failed to check space projects: {e}")


# Create the Click command
cli = CheckSpaceCommand.as_click_command(
    help="Check space configuration and setup"
)(
    click.option(
        "-s",
        "--space-name",
        required=True,
        help="Name of the space to check",
    ),
)
