"""Project bootstrap command implementation."""
import logging
from pathlib import Path
from typing import Optional

import click

from ....core.cli_ui import CliUI
from ....core.commands import ClickCommand
from ....services.project.bootstrap.bootstrap_service import ProjectBootstrapService


logger = logging.getLogger(__name__)


class ProjectBootstrapCommand(ClickCommand):
    """Command to bootstrap existing projects with ThothCTL support."""

    def __init__(self):
        super().__init__()
        self.bootstrap_service = ProjectBootstrapService()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        """Validate bootstrap parameters."""
        return True

    def _execute(
        self,
        project_path: str = ".",
        project_type: str = "auto",
        template_url: Optional[str] = None,
        force: bool = False,
        dry_run: bool = False,
        **kwargs,
    ) -> None:
        """
        Execute project bootstrap.

        Args:
            project_path: Path to the project directory
            project_type: Type of project (auto-detect or specify)
            template_url: Custom template URL to use
            force: Force update existing files
            dry_run: Show what would be created without making changes
        """
        try:
            project_path = Path(project_path).resolve()
            
            if dry_run:
                self.ui.print_info("🔍 Running bootstrap check (dry run)...")
            else:
                self.ui.print_info("🚀 Bootstrapping project with ThothCTL support...")

            with self.ui.status_spinner("Analyzing project structure..."):
                result = self.bootstrap_service.bootstrap_project(
                    project_path=project_path,
                    project_type=project_type,
                    template_url=template_url,
                    force=force,
                    dry_run=dry_run
                )

            if result["success"]:
                if dry_run:
                    self._display_dry_run_results(result)
                else:
                    self._display_bootstrap_results(result)
            else:
                self.ui.print_error(f"❌ Bootstrap failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.ui.print_error(f"Failed to bootstrap project: {str(e)}")
            logger.exception("Project bootstrap failed")
            raise click.Abort()

    def _display_dry_run_results(self, result: dict) -> None:
        """Display dry run results."""
        changes = result.get("changes", {})
        project_info = result.get("project_info", {})
        
        self.ui.print_info(f"📋 Project Analysis:")
        self.ui.print_info(f"  📁 Project Type: {project_info.get('detected_type', 'unknown')}")
        self.ui.print_info(f"  📄 Has .thothcf.toml: {'Yes' if project_info.get('has_config') else 'No'}")
        
        if not any(changes.values()):
            self.ui.print_success("✅ Project is already bootstrapped!")
            return

        self.ui.print_info("\n📋 Changes that would be made:")
        
        if changes.get("config_action"):
            action = changes["config_action"]
            if action == "create":
                self.ui.print_info("  📄 Create .thothcf.toml configuration file")
            elif action == "update":
                self.ui.print_info("  🔄 Update .thothcf.toml with missing metadata")
        
        if changes.get("new_files"):
            self.ui.print_info("  📄 New files to create:")
            for file_path in changes["new_files"]:
                self.ui.print_info(f"    + {file_path}")
        
        if changes.get("updated_files"):
            self.ui.print_info("  🔄 Files to update:")
            for file_path in changes["updated_files"]:
                self.ui.print_info(f"    ~ {file_path}")
        
        if changes.get("skipped"):
            self.ui.print_warning("  ⏭️  Files that exist (use --force to override):")
            for file_path in changes["skipped"]:
                self.ui.print_warning(f"    ! {file_path}")

    def _display_bootstrap_results(self, result: dict) -> None:
        """Display bootstrap results."""
        changes = result.get("changes", {})
        project_info = result.get("project_info", {})
        
        self.ui.print_success("✅ Project bootstrap completed!")
        self.ui.print_info(f"  📁 Project Type: {project_info.get('detected_type', 'unknown')}")
        
        if changes.get("config_action"):
            action = changes["config_action"]
            if action == "create":
                self.ui.print_info("  📄 Created .thothcf.toml configuration")
            elif action == "update":
                self.ui.print_info("  🔄 Updated .thothcf.toml metadata")
        
        if changes.get("new_files"):
            self.ui.print_info(f"  📄 Created {len(changes['new_files'])} new files")
        
        if changes.get("updated_files"):
            self.ui.print_info(f"  🔄 Updated {len(changes['updated_files'])} files")
        
        if changes.get("skipped"):
            self.ui.print_warning(f"  ⏭️  Skipped {len(changes['skipped'])} existing files")


# Create the Click command
cli = ProjectBootstrapCommand.as_click_command(
    help="Bootstrap existing projects with ThothCTL support"
)(
    click.option(
        "--project-path",
        "-p",
        default=".",
        help="Path to the project directory (default: current directory)",
        type=click.Path(exists=True, file_okay=False, dir_okay=True),
    ),
    click.option(
        "--project-type",
        "-pt",
        default="auto",
        type=click.Choice(["auto", "terraform", "terragrunt", "terraform-terragrunt", "tofu", "cdkv2", "terraform_module"], case_sensitive=False),
        help="Project type (auto for automatic detection)",
    ),
    click.option(
        "--template-url",
        "-t",
        help="Custom template URL to use for scaffold files",
    ),
    click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Force update existing files",
    ),
    click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Show what would be created without making changes",
    ),
)
