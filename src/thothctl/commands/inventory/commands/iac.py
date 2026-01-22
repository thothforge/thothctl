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

    def _execute(
        self,
        check_versions: bool,
        report_type: str,
        inventory_path: Optional[str],
        inventory_action: str = "create",
        auto_approve: bool = False,
        framework_type: str = "auto",
        complete: bool = False,
        check_providers: bool = False,
        check_schema_compatibility: bool = False,
        provider_tool: str = "tofu",
        project_name: Optional[str] = None,
        terragrunt_args: str = "",        **kwargs,
    ) -> None:
        """
        Execute project initialization

        Args:
            check_versions: Flag to check latest versions for modules and providers
            report_type: Type of report to generate
            inventory_path: Path to inventory
            inventory_action: Action to perform (create/update/list/restore)
            auto_approve: Flag for automatic approval
            framework_type: Framework type to analyze
            complete: Flag to exclude .terraform and .terragrunt-cache folders
            check_providers: Flag to check provider information
            check_schema_compatibility: Flag to check provider schema compatibility
            provider_tool: Tool to use for checking providers
            project_name: Custom project name for the inventory report
            terragrunt_args: Additional arguments to pass to terragrunt commands
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
                        framework_type=framework_type,
                        complete=complete,
                        check_providers=check_providers,
                        check_provider_versions=check_versions,  # Use unified flag for provider versions too
                        check_schema_compatibility=check_schema_compatibility,
                        provider_tool=provider_tool,
                        project_name=project_name,
                        terragrunt_args=terragrunt_args,
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
        framework_type: str = "auto",
        complete: bool = False,
        terragrunt_args: str = "",        check_providers: bool = False,
        check_provider_versions: bool = False,
        check_schema_compatibility: bool = False,
        provider_tool: str = "tofu",
        project_name: Optional[str] = None,
    ) -> None:
        """
        Create infrastructure inventory from source directory.

        Args:
            source_dir: Source directory containing Terraform files
            check_versions: Whether to check for latest versions (modules and providers)
            report_type: Type of report to generate (html, json, or all)
            reports_dir: Directory to store generated reports
            framework_type: Framework type to analyze
            complete: Flag to include .terraform and .terragrunt-cache folders
            check_providers: Flag to check provider information
            check_provider_versions: Flag to check provider versions against registries
            check_schema_compatibility: Flag to check provider schema compatibility
            provider_tool: Tool to use for checking providers
            project_name: Custom project name to use in the report
            terragrunt_args: Additional arguments to pass to terragrunt commands
        """
        try:
            # Debug logging for CLI parameters
            logger.info(f"CLI Debug: check_schema_compatibility={check_schema_compatibility}")
            logger.info(f"CLI Debug: check_versions={check_versions}")
            logger.info(f"CLI Debug: check_providers={check_providers}")
            logger.info(f"CLI Debug: check_provider_versions={check_provider_versions}")
            
            # Validate schema compatibility dependencies
            if check_schema_compatibility and not check_versions:
                self.ui.print_error("❌ Error: --check-schema-compatibility requires --check-versions to be enabled")
                self.ui.print_info("💡 Use: thothctl inventory iac --check-versions --check-schema-compatibility")
                raise click.ClickException("Schema compatibility analysis requires version checking to be enabled")
            
            if check_schema_compatibility:
                self.ui.print_info("🔍 Schema compatibility analysis enabled - this may take additional time")
            
            with self.ui.status_spinner("Creating infrastructure inventory..."):
                # When check_versions is enabled, automatically enable provider checking
                effective_check_providers = check_providers or check_versions
                
                inventory = await self.inventory_service.create_inventory(
                    source_directory=source_dir,
                    check_versions=check_versions,
                    report_type=report_type,
                    reports_directory=reports_dir,
                    framework_type=framework_type,
                    complete=complete,
                    check_providers=effective_check_providers,
                    check_provider_versions=check_versions,
                    check_schema_compatibility=check_schema_compatibility,
                    provider_tool=provider_tool,
                    project_name=project_name,
                    terragrunt_args=terragrunt_args,                    print_console=True,  # Enable console printing
                )

            self.ui.print_success("Infrastructure inventory created successfully!")

            if inventory and inventory.get("components"):
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

        # Count local modules based on source, not status
        local_modules = 0
        
        # Use unique providers count if available, otherwise count all providers
        total_providers = inventory.get("unique_providers_count", 0)
        if total_providers == 0:
            # Fall back to counting all providers if unique count not available
            for comp_group in inventory["components"]:
                total_providers += len(comp_group.get("providers", []))
            
        # Count local modules
        for comp_group in inventory["components"]:
            for component in comp_group.get("components", []):
                source = component.get("source", [""])[0] if component.get("source") else ""
                if self._is_local_source(source):
                    local_modules += 1

        self.ui.print_info("\nInventory Summary:")
        self.ui.print_info(f"Total Components: {total_components}")
        self.ui.print_info(f"Project Type: {inventory.get('projectType', 'Terraform')}")
        
        # Display framework-specific information
        project_type = inventory.get('projectType', 'terraform')
        
        
        # Show module-specific information
        if project_type == 'module':
            resources = inventory.get('resources', [])
            if resources:
                self.ui.print_info(f"Resources: {len(resources)}")
                # Show resource types summary
                resource_types = {}
                for resource in resources:
                    res_type = resource.get('resource_type', 'unknown')
                    resource_types[res_type] = resource_types.get(res_type, 0) + 1
                
                for res_type, count in resource_types.items():
                    self.ui.print_info(f"  - {res_type}: {count}")        # Show terragrunt stacks count for terraform-terragrunt projects
        if project_type == 'terraform-terragrunt':
            terragrunt_stacks_count = inventory.get('terragrunt_stacks_count', 0)
            self.ui.print_info(f"Terragrunt Stacks: {terragrunt_stacks_count}")
        
        if 'terragrunt' in project_type:
            terragrunt_modules = sum(
                1 for comp in inventory["components"] 
                for c in comp.get("components", []) 
                if c.get("type") == "terragrunt_module"
            )
            self.ui.print_info(f"Terragrunt Modules: {terragrunt_modules}")
            
        if 'terraform' in project_type:
            terraform_modules = sum(
                1 for comp in inventory["components"] 
                for c in comp.get("components", []) 
                if c.get("type") == "module"
            )
            self.ui.print_info(f"Terraform Modules: {terraform_modules}")

        # Show local modules count
        if local_modules > 0:
            self.ui.print_info(f"Local Modules: {local_modules}")
            
        # Show providers count
        if total_providers > 0:
            self.ui.print_info(f"Providers: {total_providers}")

        if "version_checks" in inventory:
            self.ui.print_info(f"Outdated Components: {outdated_components}")

    def _is_local_source(self, source: str) -> bool:
        """Check if a source is a local path."""
        if not source or source == "Null":
            return False
            
        return (source.startswith("./") or 
                source.startswith("../") or 
                source.startswith("/") or
                source.startswith("../../") or
                source.startswith("../../../") or
                source.startswith("../../../../") or
                (not source.startswith("http") and not source.startswith("git") and "/" in source and not source.count("/") == 2))


# Create the Click command
cli = IaCInvCommand.as_click_command(
    help="Create a inventory about IaC modules composition for terraform/tofu/terragrunt projects"
)(
    click.option(
        "-iph",
        "--inventory-path",
        help="Path for saving inventory reports",
        type=click.Path(),
        default="./Reports/inventory-sbom",
    ),
    click.option(
        "-cv",
        "--check-versions",
        is_flag=True,
        default=False,
        help="Check latest versions for modules and providers (includes provider version checking)",
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
        type=click.Choice(["html", "json", "cyclonedx", "all"], case_sensitive=False),
        default="html",
        help="Type of report to generate (cyclonedx generates OWASP CycloneDX SBOM format)",
    ),
    click.option(
        "--framework-type",
        "-ft",
        type=click.Choice(["auto", "terraform", "terragrunt", "terraform-terragrunt", "module"], case_sensitive=False),
        default="auto",
        help="Framework type to analyze (auto for automatic detection)",
    ),
    click.option(
        "--complete",
        is_flag=True,
        default=False,
        help="Include .terraform and .terragrunt-cache folders in analysis (complete analysis)",
    ),
    click.option(
        "--check-providers",
        is_flag=True,
        default=False,
        help="Check and report provider information for each stack (automatically enabled with --check-versions)",
    ),
    click.option(
        "--check-schema-compatibility",
        is_flag=True,
        default=False,
        help="Check provider schema compatibility between current and latest versions. Requires --check-versions to be enabled. Generates detailed compatibility analysis including breaking changes, warnings, and recommendations.",
    ),
    click.option(
        "--provider-tool",
        type=click.Choice(["tofu", "terraform"], case_sensitive=False),
        default="tofu",
        help="Tool to use for checking providers (default: tofu)",
    ),
    click.option(
        "--project-name",
        "-pj",
        help="Specify a custom project name for the inventory report",
        default=None,
    ),
    click.option(
        "--terragrunt-args",
        "-tg-args",
        help="Additional arguments to pass to terragrunt commands (e.g., '--feature=ci=false'). Only used for terragrunt and terraform-terragrunt projects.",
        default="",
    ),)
