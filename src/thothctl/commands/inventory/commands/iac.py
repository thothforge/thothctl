import click
from pathlib import Path
import getpass
from typing import Optional
from rich.console import Console
import asyncio
import logging
from colorama import Fore

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI
from ....services.inventory.inventory_service import InventoryService


logger = logging.getLogger(__name__)
console = Console()

class IaCInvCommand(ClickCommand):
    """Command to initialize a new project"""

    def __init__(self):
        super().__init__()
        self.inventory_service = InventoryService()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        """Validate project initialization parameters"""
        return True

    def execute(
            self,
            check_versions: bool,
            report_type: str,
            inventory_path: Optional[str],
            **kwargs
    ) -> None:
        """Execute project initialization"""
        ctx = click.get_current_context()
        debug = ctx.obj.get('DEBUG')
        code_directory = ctx.obj.get('CODE_DIRECTORY')

        try:
            print(f"👷 {Fore.GREEN}Create and handling code inventory {Fore.RESET}")
            asyncio.run(
                self.create_inventory(
                    source_dir=code_directory,
                    check_versions=check_versions,
                    report_type=report_type,
                    reports_dir=inventory_path
                )
            )

        except click.Abort:
            click.echo("Inventory creation aborted.")
        raise SystemExit(1)


    async def create_inventory(
            self,
            source_dir: str,
            check_versions: bool = False,
            report_type: str = "html",
            reports_dir: Optional[str] = None
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
            print(check_versions)
            with self.ui.status_spinner("Creating infrastructure inventory..."):
                inventory = await self.inventory_service.create_inventory(
                    source_directory=source_dir,
                    check_versions=check_versions,
                    report_type=report_type,
                    reports_directory=reports_dir
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

    def _display_summary(self, inventory: dict) -> None:
        """Display inventory summary."""
        total_components = len(inventory["components"])
        outdated_components = sum(
            1 for comp in inventory["components"]
            if comp.get("status") == "Outdated"
        )

        self.ui.print_info(f"\nInventory Summary:")
        self.ui.print_info(f"Total Components: {total_components}")

        if "version_checks" in inventory:
            self.ui.print_info(
                f"Outdated Components: {outdated_components}"
            )
# Create the Click command
cli = IaCInvCommand.as_click_command(
    help="Create a inventory about IaC modules composition for terraform/tofu projects"
)(
    click.option('-iph', '--inventory-path',
                 help='Path for saving inventory reports',
                 type = click.Path(),
                 default =  "./Reports/Inventory"

                 ),
    click.option('-ch', '--check-versions',
                 is_flag=True,
                 default=False,
                 help='Check remote versions'),
    click.option("-updep",
                 "--update-dependencies",
                 help='Pass the inventory json file path for updating dependencies.',
                 is_flag=True,
                 default=False
                 ),
    click.option("-auto",
                 "--auto-approve",
                 help='Use with --update_dependencies option for auto approve updating dependencies.',
                 is_flag=True,
                 default=False
                 ),

    click.option("-upact",
                 "--update-action",
                 default="update",
                 type=click.Choice(['update', 'restore'], case_sensitive=True),
                 help="Use with --update_action option to update or restore versions based on the inventory json file path for dependencies"),
click.option(
    "--report-type",
    "-r",
    type=click.Choice(["html", "json", "all"], case_sensitive=False),
    default="html",
    help="Type of report to generate"
)

)
