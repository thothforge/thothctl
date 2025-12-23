"""Module for managing version updates in terraform modules."""
import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Tuple

import inquirer
from colorama import Fore, init
from rich.console import Console
from rich.table import Table


# Initialize colorama for cross-platform color support
init(autoreset=True)


@dataclass
class VersionUpdate:
    """Data class to hold version update information."""

    name: str
    current_version: str
    new_version: str
    source: str
    file_path: str


class UpdateAction(Enum):
    """Enum for update actions."""

    UPDATE = "update"
    RESTORE = "restore"


class VersionManager:
    """Manages version updates for terraform modules."""

    def __init__(self, inventory_file: Path):
        """Initialize version manager."""
        self.inventory_file = inventory_file
        self.console = Console()
        self.project_type = "terraform"  # Default to terraform

    def load_inventory(self) -> dict:
        """Load and parse inventory file."""
        try:
            inventory = json.loads(self.inventory_file.read_text())
            self.project_type = inventory.get("projectType", "terraform")
            return inventory
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.error(f"Failed to load inventory file: {e}")
            raise

    def display_updates(self, updates: List[dict]) -> None:
        """Display version updates in a formatted table."""
        table = Table(
            title=f"Modules version to Update ({self.project_type})",
            title_style="bold magenta",
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
        )

        columns = ["Name", "ActualVersion", "NewVersion", "Source", "File"]
        for column in columns:
            table.add_column(column, style="dim")

        for update in updates:
            table.add_row(
                update["name"],
                f'[red]{update["version"][0]}[/red]',
                f'[green]{update["latest_version"]}[/green]',
                update["source"][0],
                update["file"],
            )

        self.console.print(table)

    def process_updates(
        self,
        updates: List[dict],
        auto_approve: bool = False,
        action: str = UpdateAction.UPDATE.value,
    ) -> None:
        """Process version updates with user confirmation."""
        if not updates:
            print(f"{Fore.YELLOW}No updates available.{Fore.RESET}")
            return

        if (
            not auto_approve and not self._confirm_update()
        ):  # Removed the "main" parameter
            print(f"{Fore.RED}❌ No changes to apply.{Fore.RESET}")
            return

        auto_apply_all = self._confirm_apply_all()  # Separated into a new method

        if auto_apply_all:
            # Process all updates
            for update in updates:
                self._process_single_update(update, True, action)
        else:
            # Let user select specific modules
            selected_modules = self._select_modules(updates)
            for update in updates:
                if update["name"] in selected_modules:
                    self._process_single_update(update, False, action)

    def _select_modules(self, updates: List[dict]) -> List[str]:
        """Allow user to select specific modules to update."""
        choices = [
            {
                "name": f"{update['name']} ({update['version'][0]} → {update['latest_version']})",
                "value": update["name"],
            }
            for update in sorted(updates, key=lambda x: x["name"])
        ]

        # Remove duplicates while preserving order
        seen = set()
        unique_choices = []
        for choice in choices:
            if choice["name"] not in seen:
                seen.add(choice["name"])
                unique_choices.append(choice)

        questions = [
            inquirer.Checkbox(
                "selected_modules",
                message="Select modules to update (use space to select, enter to confirm)",
                choices=[
                    (choice["name"], choice["value"]) for choice in unique_choices
                ],
            ),
        ]

        answers = inquirer.prompt(questions)

        if not answers or not answers["selected_modules"]:
            print(f"{Fore.YELLOW}No modules selected.{Fore.RESET}")
            return []

        return answers["selected_modules"]

    def _apply_version_update(self, file_path: Path, search: str, replace: str) -> None:
        """Apply version update to file."""
        try:
            content = file_path.read_text()
            
            # Handle terragrunt.hcl files differently
            if self.project_type == "terragrunt" and file_path.name == "terragrunt.hcl":
                # For terragrunt, we need to update the version in the source attribute
                if "tfr:///" in content:
                    # Handle tfr:/// format
                    updated_content = re.sub(
                        rf'source = "tfr:///[^"]+"',
                        lambda m: m.group(0).replace(search, replace),
                        content
                    )
                else:
                    # Handle other formats
                    updated_content = content.replace(search, replace)
            else:
                # Standard terraform file update
                updated_content = content.replace(search, replace)
                
            file_path.write_text(updated_content)

            logging.debug(f"Version {search} changed to {replace} in {file_path}")
            
            # Format the file if it's a terraform file
            if file_path.suffix == ".tf":
                self._format_terraform_file(file_path)
                
            print(
                f"{Fore.GREEN}✔️ Version changed successfully. "
                f"Run plan and apply for checking changes.{Fore.RESET}\n"
            )
        except IOError as e:
            logging.error(f"Failed to update file {file_path}: {e}")
            raise

    def _confirm_update(self) -> bool:
        """Confirm update action with user."""
        questions = [
            inquirer.Confirm(
                "confirm",
                message="Do you want to proceed with the updates?",
                default=True,
            )
        ]

        answers = inquirer.prompt(questions)
        return answers and answers["confirm"]

    def _confirm_single_update(
        self, search: str, replace: str, file_path: Path
    ) -> bool:
        """Confirm single update with user."""
        questions = [
            inquirer.Confirm(
                "confirm",
                message=f"Update version from {search} to {replace} in {file_path}?",
                default=True,
            )
        ]

        answers = inquirer.prompt(questions)
        return answers and answers["confirm"]

    def _confirm_apply_all(self) -> bool:
        """Confirm if updates should be applied to all modules."""
        questions = [
            inquirer.Confirm(
                "confirm",
                message="Do you want to apply updates to all modules?",
                default=False,
            )
        ]

        answers = inquirer.prompt(questions)
        return answers and answers["confirm"]

    def _process_single_update(
        self, update: dict, auto_apply: bool, action: str
    ) -> None:
        """Process a single version update."""
        file_path = Path(update["file"])
        search, replace = self._get_version_strings(update, action)

        if not auto_apply:
            module_name = update["name"]
            current_version = update["version"][0]
            new_version = update["latest_version"]
            print(
                f"\n{Fore.CYAN}Processing module: {module_name} ({current_version} → {new_version}){Fore.RESET}"
            )
            if not self._confirm_single_update(search, replace, file_path):
                return

        print(f"{Fore.GREEN}Applying update for {update['name']}...{Fore.RESET}")
        self._apply_version_update(file_path, search, replace)

    @staticmethod
    def _format_terraform_file(file_path: Path) -> None:
        """
        Format terraform file using available tools.
        
        Tries to use tofu or terraform fmt, whichever is available.
        If neither is available, logs a warning but doesn't fail.
        """
        import subprocess
        import shutil
        
        # List of tools to try, in order of preference
        format_tools = ["tofu", "terraform"]
        
        for tool in format_tools:
            # Check if the tool is available
            if shutil.which(tool):
                try:
                    logging.debug(f"Formatting {file_path} using {tool} fmt")
                    result = subprocess.run(
                        [tool, "fmt", str(file_path)], 
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=30  # Add timeout to prevent hanging
                    )
                    logging.debug(f"Successfully formatted {file_path} with {tool}")
                    return
                except subprocess.CalledProcessError as e:
                    logging.warning(f"Failed to format {file_path} with {tool}: {e}")
                    # Try the next tool
                    continue
                except subprocess.TimeoutExpired:
                    logging.warning(f"Timeout formatting {file_path} with {tool}")
                    # Try the next tool
                    continue
                except Exception as e:
                    logging.warning(f"Unexpected error formatting {file_path} with {tool}: {e}")
                    # Try the next tool
                    continue
        
        # If we get here, no tool worked
        logging.warning(
            f"Could not format {file_path}: neither 'tofu' nor 'terraform' is available or working. "
            f"File was updated but not formatted."
        )

    def _get_version_strings(self, file_details: dict, action: str) -> Tuple[str, str]:
        """Get version strings for update or restore."""
        current_version = file_details["version"][0]
        new_version = file_details["latest_version"]
        
        # For terragrunt files, we need to handle the version differently
        if self.project_type == "terragrunt" and "tfr:///" in file_details["source"][0]:
            current_pattern = f"?version={current_version}"
            new_pattern = f"?version={new_version}"
            
            return (
                (new_pattern, current_pattern)
                if action == UpdateAction.RESTORE.value
                else (current_pattern, new_pattern)
            )
        else:
            # Standard terraform version handling
            return (
                (new_version, current_version)
                if action == UpdateAction.RESTORE.value
                else (current_version, new_version)
            )


def summary_inventory(
    inv,
):
    """
    Create summary inventory.

    :param inv:
    :return:
    """
    inv_summary = {}  # "ProjectName": project_name
    outdated = 0
    updated = 0
    local = 0
    list_outdated = []
    st = None
    for components in inv.get("components", []):
        for c in components.get("components", []):
            logging.debug(c)
            local_version = c.get("version")
            st = c.get("status", None)

            if isinstance(local_version, list):
                # When version is a list, check status
                if st == "Updated":
                    updated += 1
                elif st == "Outdated":
                    outdated += 1
                    list_outdated.append(c)
                else:
                    # If status is not set but version is a list, count as local
                    local += 1
            elif local_version == "Null" or local_version is None:
                # Local modules with no version
                local += 1
            else:
                # Single version string - could be outdated or updated based on status
                if st == "Updated":
                    updated += 1
                elif st == "Outdated":
                    outdated += 1
                    list_outdated.append(c)
                else:
                    # Default to local if no status
                    local += 1
    total = local + updated + outdated
    inv_summary["TotalModules"] = total
    inv_summary["LocalModules"] = local
    inv_summary["RemoteModules"] = updated + outdated
    inv_summary["Updated"] = updated
    inv_summary["Outdated"] = outdated
    print(inv_summary)

    inv_summary["UpdateStatus"] = f"{str((updated / total) * 100) if total > 0 else '0'} %"

    return inv_summary, list_outdated


def main_update_versions(
    inventory_file: str,
    auto_approve: bool = False,
    action: str = UpdateAction.UPDATE.value,
) -> None:
    """Main function to handle version updates."""
    manager = VersionManager(Path(inventory_file))
    inventory = manager.load_inventory()
    _, updates = summary_inventory(inventory)

    manager.display_updates(updates)
    manager.process_updates(updates, auto_approve, action)
