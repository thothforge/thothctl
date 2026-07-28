"""Initialize development environment command."""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import click

from ....core.commands import ClickCommand
from ....services.init.environment.install_tools import bootstrap_env
from ....services.init.environment.prerequisite_checker import (
    check_prerequisites,
    display_prerequisite_results,
)
from ....services.init.environment.tool_packs import (
    resolve_pack,
)


class EnvInitCommand(ClickCommand):
    """Command to initialize development environment with required tools."""

    def validate(self, **kwargs) -> bool:
        """Validate environment initialization parameters."""
        return True

    def _execute(
        self,
        operation_system: str,
        project_type: Optional[str] = None,
        with_aidlc: bool = False,
        **kwargs,
    ) -> None:
        """Execute environment initialization."""
        if project_type:
            self._init_env_with_pack(operation_system, project_type, with_aidlc)
        else:
            # Legacy behavior: show all tools for manual selection
            bootstrap_env(so=operation_system)

    def _init_env_with_pack(
        self, operation_system: str, project_type: str, with_aidlc: bool = False
    ) -> None:
        """Initialize environment using project-type tool pack."""
        from colorama import Fore
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console()

        # Resolve the full tool pack (with inheritance)
        pack = resolve_pack(project_type)

        # Display pack info
        console.print(
            Panel(
                f"[bold]{pack.name}[/bold] — {pack.description}\n"
                f"Tools: {', '.join(pack.tools)}",
                title="🧰 Tool Pack",
                border_style="cyan",
            )
        )

        # Check prerequisites first (never install runtimes)
        if pack.prerequisites:
            console.print("\n[bold]Checking prerequisites...[/bold]\n")
            results = check_prerequisites(pack.prerequisites)
            all_met = display_prerequisite_results(results)

            if not all_met:
                console.print(
                    "[yellow]⚠️  Fix prerequisites above before installing tools.[/yellow]"
                )
                console.print(
                    "[dim]Tools that depend on missing prerequisites will be skipped.[/dim]\n"
                )

                # Ask if user wants to continue anyway
                import inquirer

                questions = [
                    inquirer.Confirm(
                        "continue",
                        message="Continue installing available tools?",
                        default=True,
                    )
                ]
                answers = inquirer.prompt(questions)
                if not answers or not answers["continue"]:
                    console.print(f"{Fore.RED}Installation cancelled.{Fore.RESET}")
                    return

        # Show tools to be installed
        console.print("\n[bold]Tools to install/upgrade:[/bold]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Tool", style="cyan")
        table.add_column("Category")

        # Determine which tools are from base vs specific pack
        base_pack = resolve_pack("base")
        base_tools = set(base_pack.tools)

        for tool in pack.tools:
            category = (
                "🔒 Security/Compliance" if tool in base_tools else "🔧 IaC Tooling"
            )
            # Override for specific tools
            if tool in ("pre-commit", "commitizen", "thothctl", "kiro-cli"):
                category = "⚙️ Developer Workflow"
            table.add_row(tool, category)

        console.print(table)
        console.print()

        # Confirm and install
        import inquirer

        questions = [
            inquirer.Confirm(
                "install",
                message=f"Install {len(pack.tools)} tools for '{pack.name}' pack?",
                default=True,
            )
        ]
        answers = inquirer.prompt(questions)
        if not answers or not answers["install"]:
            console.print(f"{Fore.YELLOW}Installation skipped.{Fore.RESET}")
            return

        # Install using existing infrastructure
        from ....services.check.environment.check_environment import (
            get_tool_version,
            load_tools,
        )
        from ....services.init.environment.install_tools import install_tool

        tools_config = load_tools()
        versions = get_tool_version(tools_config)

        if operation_system == "Linux/Debian":
            os.chdir("/tmp")
            for tool_name in pack.tools:
                # Skip tools that need missing prerequisites
                if tool_name == "aws-cdk" and not _is_node_available():
                    console.print(
                        "[yellow]⏭️  Skipping aws-cdk (Node.js not available)[/yellow]"
                    )
                    continue

                try:
                    install_tool(tool_name=tool_name, versions=versions)
                except Exception as e:
                    console.print(f"[red]❌ Failed to install {tool_name}: {e}[/red]")
        else:
            console.print(
                f"[red]❌ OS '{operation_system}' not supported. "
                f"Use manual installation.[/red]"
            )

        # AI-DLC workflow rules (optional)
        self._handle_aidlc_installation(console, project_type, with_aidlc)

    def _handle_aidlc_installation(
        self, console, project_type: str, with_aidlc: bool
    ) -> None:
        """Handle AI-DLC workflow rules installation (flag or interactive prompt)."""
        from ....services.init.environment.install_tools import install_aidlc_rules

        if with_aidlc:
            # Explicit flag: install without prompting
            install_aidlc_rules(target_dir=str(Path.cwd()))
            return

        # Interactive: prompt the user
        # Default Yes for CDK projects (more complex), No for others
        default_install = project_type == "cdkv2"

        console.print()
        console.print("[bold]🤖 AI-Assisted Development (optional)[/bold]")
        console.print(
            "   AI-DLC workflow rules provide structured requirement → design →\n"
            "   implementation workflows for Kiro CLI. Recommended for complex projects."
        )
        console.print()

        import inquirer

        questions = [
            inquirer.Confirm(
                "install_aidlc",
                message="Install AI-DLC rules to .kiro/steering/?",
                default=default_install,
            )
        ]
        answers = inquirer.prompt(questions)
        if answers and answers["install_aidlc"]:
            install_aidlc_rules(target_dir=str(Path.cwd()))

    @contextmanager
    def _change_directory(self, path: Path):
        """Safely change directory and return to original."""
        original_dir = Path.cwd()
        try:
            os.chdir(path)
            yield
        finally:
            os.chdir(original_dir)


def _is_node_available() -> bool:
    """Quick check if node is available."""
    import shutil

    return shutil.which("node") is not None


def _detect_project_type() -> Optional[str]:
    """Auto-detect project type from .thothcf.toml in current directory."""
    toml_path = Path.cwd() / ".thothcf.toml"
    if toml_path.exists():
        try:
            import toml

            config = toml.load(toml_path)
            return config.get("thothcf", {}).get("project_type")
        except Exception:
            pass
    return None


# Create the Click command
cli = EnvInitCommand.as_click_command(
    help="Initialize development environment with required tools. "
    "Use --project-type for smart pack-based installation."
)(
    click.option(
        "-os",
        "--operation-system",
        help="Target operating system",
        required=False,
        default="Linux/Debian",
        type=click.Choice(["Linux/Debian"], case_sensitive=False),
    ),
    click.option(
        "-pt",
        "--project-type",
        help="Install tools for a specific project type (auto-detect from .thothcf.toml if omitted)",
        required=False,
        default=None,
        type=click.Choice(
            [
                "terraform",
                "terraform-terragrunt",
                "tofu",
                "cdkv2",
                "terraform_module",
                "custom",
            ],
            case_sensitive=False,
        ),
    ),
    click.option(
        "--with-aidlc",
        is_flag=True,
        default=False,
        help="Install AI-DLC workflow rules for Kiro (.kiro/steering/). "
        "Non-interactive; in interactive mode, you'll be prompted.",
    ),
)
