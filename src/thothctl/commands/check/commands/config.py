"""Check effective configuration from all sources."""

import os
from pathlib import Path
from typing import Dict

import toml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ....core.cli_ui import CliUI
from ....core.commands import ClickCommand


class CheckConfigCommand(ClickCommand):
    """Command to show effective merged configuration with source annotations."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()
        self.console = Console()

    def _execute(self, **kwargs) -> None:
        """Display effective configuration from all sources."""
        self.console.print()
        self.console.print(
            Panel(
                "Shows merged configuration from all sources.\n"
                "Precedence: Environment vars > Project > Space > Global defaults",
                title="🔧 Effective Configuration",
                border_style="cyan",
            )
        )

        # 1. Active Space
        self._show_active_space()

        # 2. Space configuration
        self._show_space_config()

        # 3. Project configuration
        self._show_project_config()

        # 4. Environment variables
        self._show_env_vars()

        # 5. Config file locations
        self._show_config_paths()

    def _show_active_space(self) -> None:
        """Show the currently active space."""
        active_file = Path.home() / ".thothcf" / "active_space"
        if active_file.exists():
            space_name = active_file.read_text(encoding="utf-8").strip()
            self.console.print(
                f"\n[bold]🌐 Active Space:[/bold] [green]{space_name}[/green]"
            )
        else:
            self.console.print(
                "\n[bold]🌐 Active Space:[/bold] [dim]None (not set)[/dim]"
            )

    def _show_space_config(self) -> None:
        """Show space-level configuration."""
        spaces_path = Path.home() / ".thothcf" / "spaces.toml"
        active_file = Path.home() / ".thothcf" / "active_space"

        if not spaces_path.exists() or not active_file.exists():
            return

        space_name = active_file.read_text(encoding="utf-8").strip()
        try:
            config = toml.load(spaces_path)
            space_data = config.get("spaces", {}).get(space_name, {})
        except Exception:
            return

        if not space_data:
            return

        table = Table(
            title=f"Space Config: {space_name}",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Section", style="cyan")
        table.add_column("Key", style="white")
        table.add_column("Value", style="green")
        table.add_column("Source", style="dim")

        for section_name, section_data in space_data.items():
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    table.add_row(section_name, key, str(value), "spaces.toml")
            elif section_name not in ("projects",):
                table.add_row("", section_name, str(section_data), "spaces.toml")

        self.console.print()
        self.console.print(table)

    def _show_project_config(self) -> None:
        """Show project-level configuration from CWD."""
        project_files = [".thothcf.toml", ".thothcf_module.toml"]
        found = False

        for filename in project_files:
            filepath = Path.cwd() / filename
            if filepath.exists():
                found = True
                try:
                    config = toml.load(filepath)
                except Exception:
                    continue

                table = Table(
                    title=f"Project Config: {filename}",
                    box=box.ROUNDED,
                    show_header=True,
                    header_style="bold yellow",
                )
                table.add_column("Key", style="yellow")
                table.add_column("Value", style="white")
                table.add_column("Source", style="dim")

                self._flatten_to_table(config, table, filename)
                self.console.print()
                self.console.print(table)

        if not found:
            self.console.print(
                "\n[dim]No project config found in current directory (.thothcf.toml)[/dim]"
            )

    def _show_env_vars(self) -> None:
        """Show THOTH_* environment variables."""
        env_vars = {
            k: v for k, v in sorted(os.environ.items()) if k.startswith("THOTH")
        }

        if env_vars:
            table = Table(
                title="Environment Variables (THOTH_*)",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold red",
            )
            table.add_column("Variable", style="red")
            table.add_column("Value", style="white")

            for key, value in env_vars.items():
                # Mask tokens/secrets
                if any(
                    s in key.lower() for s in ("token", "secret", "password", "key")
                ):
                    display_value = value[:4] + "****" if len(value) > 4 else "****"
                else:
                    display_value = value
                table.add_row(key, display_value)

            self.console.print()
            self.console.print(table)
        else:
            self.console.print("\n[dim]No THOTH_* environment variables set[/dim]")

    def _show_config_paths(self) -> None:
        """Show all config file locations and their existence status."""
        paths = [
            ("Global spaces", Path.home() / ".thothcf" / "spaces.toml"),
            ("Global projects", Path.home() / ".thothcf" / ".thothcf.toml"),
            ("Active space", Path.home() / ".thothcf" / "active_space"),
            ("Project config", Path.cwd() / ".thothcf.toml"),
            ("Module config", Path.cwd() / ".thothcf_module.toml"),
            ("Template params", Path.cwd() / ".thothcf_template_parameters.toml"),
        ]

        self.console.print("\n[bold]📁 Config File Locations:[/bold]")
        for label, path in paths:
            exists = "✅" if path.exists() else "❌"
            style = "green" if path.exists() else "dim"
            self.console.print(f"  {exists} [{style}]{label}:[/{style}] {path}")

        self.console.print()
        self.console.print(
            "[dim]Precedence: ENV vars (THOTH_*) > Project (.thothcf.toml) "
            "> Space (spaces.toml) > Global defaults[/dim]"
        )

    def _flatten_to_table(
        self, data: Dict, table: Table, source: str, prefix: str = ""
    ) -> None:
        """Flatten nested dict into table rows."""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                self._flatten_to_table(value, table, source, full_key)
            elif isinstance(value, list):
                table.add_row(full_key, ", ".join(str(v) for v in value), source)
            else:
                table.add_row(full_key, str(value), source)


cli = CheckConfigCommand.as_click_command(
    help="Show effective merged configuration from all sources"
)()
