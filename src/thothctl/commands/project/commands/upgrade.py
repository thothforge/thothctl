"""Project upgrade command implementation."""
import logging
from pathlib import Path
from typing import Optional

import click

from ....core.cli_ui import CliUI
from ....core.commands import ClickCommand
from ....services.project.upgrade.upgrade_service import ProjectUpgradeService


logger = logging.getLogger(__name__)


class ProjectUpgradeCommand(ClickCommand):
    """Command to upgrade project scaffold files from remote template."""

    def __init__(self):
        super().__init__()
        self.upgrade_service = ProjectUpgradeService()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        """Validate upgrade parameters."""
        return True

    def _execute(
        self,
        project_path: str = ".",
        dry_run: bool = False,
        force: bool = False,
        interactive: bool = False,
        **kwargs,
    ) -> None:
        """
        Execute project upgrade.

        Args:
            project_path: Path to the project directory
            dry_run: Show what would be updated without making changes
            force: Force update even if files have local modifications
            interactive: Allow selective file import
        """
        try:
            project_path = Path(project_path).resolve()
            
            if dry_run:
                self.ui.print_info("🔍 Running upgrade check (dry run)...")
            elif interactive:
                self.ui.print_info("🎯 Starting interactive project upgrade...")
            else:
                self.ui.print_info("🚀 Starting project upgrade...")

            result = self.upgrade_service.upgrade_project(
                project_path=project_path,
                dry_run=dry_run,
                force=force,
                interactive=interactive
            )

            if result["success"]:
                if dry_run:
                    self._display_dry_run_results(result)
                elif interactive:
                    self._display_interactive_results(result)
                else:
                    self._display_upgrade_results(result)
            else:
                self.ui.print_error(f"❌ Upgrade failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.ui.print_error(f"Failed to upgrade project: {str(e)}")
            logger.exception("Project upgrade failed")
            raise click.Abort()

    def _display_dry_run_results(self, result: dict) -> None:
        """Display dry run results."""
        changes = result.get("changes", {})
        commit_info = changes.get("commit_info", {})
        
        # Show commit comparison
        if commit_info:
            local_hash = commit_info.get("local_hash", "unknown")[:8]
            remote_hash = commit_info.get("remote_hash", "unknown")[:8]
            needs_update = commit_info.get("needs_update", False)
            
            self.ui.print_info(f"📋 Commit comparison:")
            self.ui.print_info(f"  Local:  {local_hash}")
            self.ui.print_info(f"  Remote: {remote_hash}")
            
            if not needs_update:
                self.ui.print_success("✅ Project is up to date (same commit hash)!")
                return
            else:
                self.ui.print_warning("⚠️  Remote template has newer commits")
        
        # Show detailed file changes
        new_files = changes.get("new_files", [])
        updated_files = changes.get("updated_files", [])
        conflicts = changes.get("conflicts", [])
        
        if not any([new_files, updated_files, conflicts]):
            self.ui.print_success("✅ No file changes needed!")
            return

        self.ui.print_info("📋 Available changes from template:")
        
        if new_files:
            self.ui.print_info(f"  📄 New files available ({len(new_files)}):")
            for file_path in sorted(new_files):
                self.ui.print_info(f"    + {file_path}")
        
        if updated_files:
            self.ui.print_info(f"  🔄 Files with updates ({len(updated_files)}):")
            for file_path in sorted(updated_files):
                self.ui.print_info(f"    ~ {file_path}")
        
        if conflicts:
            self.ui.print_warning(f"  ⚠️  Files with local modifications ({len(conflicts)}):")
            for file_path in sorted(conflicts):
                self.ui.print_warning(f"    ! {file_path}")
        
        self.ui.print_info("")
        self.ui.print_info("💡 Run without --dry-run to apply changes")
        self.ui.print_info("💡 Use --force to override local modifications")

    def _display_interactive_results(self, result: dict) -> None:
        """Display interactive upgrade results."""
        changes = result.get("changes", {})
        
        if changes.get("selected_files"):
            self.ui.print_success("✅ Interactive upgrade completed!")
            self.ui.print_info(f"  📄 Imported {len(changes['selected_files'])} files")
            for file_path in sorted(changes["selected_files"]):
                self.ui.print_info(f"    + {file_path}")
        else:
            self.ui.print_info("ℹ️  No files were selected for import")

    def _display_upgrade_results(self, result: dict) -> None:
        """Display upgrade results."""
        changes = result.get("changes", {})
        commit_info = changes.get("commit_info", {})
        
        # Show commit comparison
        if commit_info:
            local_hash = commit_info.get("local_hash", "unknown")[:8]
            remote_hash = commit_info.get("remote_hash", "unknown")[:8]
            needs_update = commit_info.get("needs_update", False)
            
            if not needs_update:
                self.ui.print_success("✅ Project was already up to date (same commit hash)!")
                return
            else:
                self.ui.print_info(f"📋 Updated from {local_hash} to {remote_hash}")
        
        if not any([changes.get("new_files"), changes.get("updated_files")]):
            self.ui.print_success("✅ Commit updated, no file changes needed!")
            return

        self.ui.print_success("✅ Project upgrade completed!")
        
        if changes.get("new_files"):
            self.ui.print_info(f"  📄 Downloaded {len(changes['new_files'])} new files")
        
        if changes.get("updated_files"):
            self.ui.print_info(f"  🔄 Updated {len(changes['updated_files'])} files")
        
        if changes.get("skipped"):
            self.ui.print_warning(f"  ⏭️  Skipped {len(changes['skipped'])} files (use --force to override)")


# Create the Click command
cli = ProjectUpgradeCommand.as_click_command(
    help="Upgrade project scaffold files from remote template"
)(
    click.option(
        "--project-path",
        "-p",
        default=".",
        help="Path to the project directory (default: current directory)",
        type=click.Path(exists=True, file_okay=False, dir_okay=True),
    ),
    click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Show what would be updated without making changes",
    ),
    click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Force update even if files have local modifications",
    ),
    click.option(
        "--interactive",
        "-i",
        is_flag=True,
        default=False,
        help="Allow selective file import with interactive prompts",
    ),
)
