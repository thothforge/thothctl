import asyncio
import logging
from enum import Enum
from typing import Optional

import click

import os
from colorama import Fore
from rich.console import Console

from ....core.cli_ui import CliUI
from ....core.commands import ClickCommand
from ....services.inventory.inventory_service import InventoryService


logger = logging.getLogger(__name__)
console = Console()


class InventoryAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    LIST = "list"
    RESTORE = "restore"


class IaCInvCommand(ClickCommand):
    """Command to initialize a new project"""

    def __init__(self):
        super().__init__()
        self.inventory_service = InventoryService()
        self.ui = CliUI()
        # self.console = Console()

    def clear_screen(self):
        """Clear the console screen in a cross-platform way."""
        os.system("cls" if os.name == "nt" else "clear")

    def validate(self, **kwargs) -> bool:
        """Validate project initialization parameters"""
        return True

    def execute(
        self,
        check_versions: bool,
        report_type: str,
        inventory_path: Optional[str],
        inventory_action: str = "create",
        auto_approve: bool = False,
        **kwargs,
    ) -> None:
        """
        Execute project initialization

        Args:
            check_versions: Flag to check versions
            report_type: Type of report to generate
            inventory_path: Path to inventory
            inventory_action: Action to perform (create/update/list/restore)
            auto_approve: Flag for automatic approval
        """
        try:
            ctx = click.get_current_context()
            config = {
                "debug": ctx.obj.get("DEBUG"),
                "code_directory": ctx.obj.get("CODE_DIRECTORY"),
            }

            action = InventoryAction(inventory_action.lower())
            print(f"👷 {Fore.GREEN}{self._get_action_message(action)}{Fore.RESET}")

            if action == InventoryAction.CREATE:
                print("📦 Creating inventory...")
                asyncio.run(
                    self.create_inventory(
                        source_dir=config["code_directory"],
                        check_versions=check_versions,
                        report_type=report_type,
                        reports_dir=inventory_path,
                    )
                )
            elif action in (InventoryAction.UPDATE, InventoryAction.RESTORE):
                self.update_inventory(
                    inventory_path=inventory_path,
                    action=inventory_action,
                    auto_approve=auto_approve,
                )
            # LIST action doesn't require additional processing

        except click.Abort:
            click.echo("Inventory creation aborted.")
            raise SystemExit(1)
        except ValueError:
            click.echo(f"Invalid inventory action: {inventory_action}")
            raise SystemExit(1)

    def _get_action_message(self, action: InventoryAction) -> str:
        """Get the appropriate message for each action"""
        messages = {
            InventoryAction.CREATE: "📦 Creating inventory",
            InventoryAction.UPDATE: "Update IaC according to inventory",
            InventoryAction.LIST: "List IaC inventory",
            InventoryAction.RESTORE: "Restore IaC code according to inventory",
        }
        return messages.get(action, "Unknown action")

    async def create_inventory(
        self,
        source_dir: str,
        check_versions: bool = False,
        report_type: str = "html",
        reports_dir: Optional[str] = None,
    ) -> None:
        """
        Create infrastructure inventory from source directory.

        Args:
            source_dir: Source directory containing Terraform files
            check_versions: Whether to check for latest versions
            report_type: Type of report to generate (html, json, or all)
            reports_dir: Directory to store generated reports
        """
        try:
            with self.ui.status_spinner("Creating infrastructure inventory..."):
                inventory = await self.inventory_service.create_inventory(
                    source_directory=source_dir,
                    check_versions=check_versions,
                    report_type=report_type,
                    reports_directory=reports_dir,
                )

            self.ui.print_success("Infrastructure inventory created successfully!")

            if inventory["components"]:
                self._display_summary(inventory)
            else:
                self.ui.print_warning("No components found in the specified directory.")

        except Exception as e:
            self.ui.print_error(f"Failed to create inventory: {str(e)}")
            logger.exception("Inventory creation failed")
            raise click.Abort()

    def update_inventory(
        self, inventory_path: str, auto_approve: bool = False, action: str = "update"
    ) -> None:
        """
        Update inventory from a given path.

        Args:
            inventory_path: Path to the inventory file
            auto_approve: Whether to automatically approve changes
            action: The type of update action to perform
        """
        try:
            self.clear_screen()

            # Show initial status
            self.ui.print_info(
                "[bold blue]Starting inventory update process...[/bold blue]",
            )

            # Process the update
            self.inventory_service.update_inventory(
                inventory_path, auto_approve=auto_approve, action=action
            )

            # Show success message
            # self.console.print(
            self.ui.print_success(
                "[bold green]✓ Inventory updated successfully![/bold green]\n\n",  # "[blue]Summary of changes:[/blue]",
            )

        except Exception as e:
            self.clear_screen()

            # Show error message in a panel
            error_message = (
                "[bold red]❌ Inventory Update Failed[/bold red]\n\n"
                f"[red]Error: {str(e)}[/red]"
            )
            self.ui.print_error(error_message)

            # Log the full error for debugging
            logging.exception("Inventory update failed")
            raise click.Abort()

        finally:
            # Ensure the cursor is visible
            self.ui.console.show_cursor(True)

    def _display_summary_update(self, inventory_path: str) -> None:
        """
        Display a summary of the inventory updates.

        Args:
            inventory_path: Path to the inventory file
        """
        try:
            # Add your summary logic here
            self.ui.print_info("\n[blue]Detailed changes:[/blue]")
            # Example summary table
            from rich.table import Table

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Module")
            table.add_column("Previous Version")
            table.add_column("New Version")
            table.add_column("Status")

            # Add your rows here based on the actual changes
            # table.add_row("module1", "1.0.0", "1.1.0", "✓")

            self.ui.console.print(table)

        except Exception as e:
            self.ui.console.print(
                "[yellow]Unable to display summary. " f"Error: {str(e)}[/yellow]"
            )

    def _display_summary(self, inventory: dict) -> None:
        """Display inventory summary."""
        total_components = len(inventory["components"])
        outdated_components = sum(
            1 for comp in inventory["components"] if comp.get("status") == "Outdated"
        )

        self.ui.print_info("\nInventory Summary:")
        self.ui.print_info(f"Total Components: {total_components}")

        if "version_checks" in inventory:
            self.ui.print_info(f"Outdated Components: {outdated_components}")


# Create the Click command
cli = IaCInvCommand.as_click_command(
    help="Create a inventory about IaC modules composition for terraform/tofu projects"
)(
    click.option(
        "-iph",
        "--inventory-path",
        help="Path for saving inventory reports",
        type=click.Path(),
        default="./Reports/Inventory",
    ),
    click.option(
        "-ch",
        "--check-versions",
        is_flag=True,
        default=False,
        help="Check remote versions",
    ),
    click.option(
        "-updep",
        "--update-dependencies-path",
        help="Pass the inventory json file path for updating dependencies.",
        is_flag=True,
        default=False,
    ),
    click.option(
        "-auto",
        "--auto-approve",
        help="Use with --update_dependencies option for auto approve updating dependencies.",
        is_flag=True,
        default=False,
    ),
    click.option(
        "-iact",
        "--inventory-action",
        default="create",
        type=click.Choice(["create", "update", "restore"], case_sensitive=True),
        help="Action for inventory tasks",
    ),
    click.option(
        "--report-type",
        "-r",
        type=click.Choice(["html", "json", "all"], case_sensitive=False),
        default="html",
        help="Type of report to generate",
    ),
)
