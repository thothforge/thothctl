"""Apply-fix command — apply generated fixes with backup."""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

import click

from ....core.commands import ClickCommand
from ....core.cli_ui import CliUI

logger = logging.getLogger(__name__)

BACKUP_DIR = ".thothctl/fix_backups"


class ApplyFixCommand(ClickCommand):
    """Apply code fixes from a generated fixes file."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        if not kwargs.get("fixes_file"):
            self.ui.print_error("--fixes-file is required")
            return False
        return True

    def _execute(self, fixes_file, fix_ids=None, dry_run=False,
                 no_backup=False, directory=None, **kwargs):
        # Load fixes
        try:
            with open(fixes_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            self.ui.print_error(f"Cannot read fixes file: {e}")
            return

        fixes = data.get("fixes", [])
        if not fixes:
            self.ui.print_warning("No fixes found in file.")
            return

        # Filter by IDs if specified
        if fix_ids:
            ids = [x.strip() for x in fix_ids.split(",")]
            fixes = [f for f in fixes if f.get("fix_id") in ids]
            if not fixes:
                self.ui.print_error(f"No fixes match IDs: {fix_ids}")
                return

        # Only apply fixes that have both original and replacement
        applicable = [f for f in fixes if f.get("replacement") and f.get("file")
                      and f.get("fix_type") != "manual"]
        manual = [f for f in fixes if f.get("fix_type") == "manual" or not f.get("replacement")]

        if not applicable and not manual:
            self.ui.print_warning("No applicable fixes.")
            return

        base_dir = Path(directory) if directory else Path(".")

        if dry_run:
            self.ui.print_warning("[DRY RUN] Showing what would be applied:\n")

        applied, failed = 0, 0
        for fix in applicable:
            file_path = base_dir / fix["file"]
            fix_id = fix.get("fix_id", "?")

            if not file_path.exists():
                self.ui.print_warning(f"  {fix_id}: File not found: {fix['file']}")
                failed += 1
                continue

            original = fix.get("original", "")
            replacement = fix["replacement"]

            if dry_run:
                self.ui.console.print(f"[cyan]{fix_id}[/cyan] → {fix['file']}: {fix.get('description', '')}")
                if original and not original.startswith("#"):
                    self.ui.console.print(f"  [red]- {original[:80]}[/red]")
                self.ui.console.print(f"  [green]+ {replacement[:80]}[/green]")
                applied += 1
                continue

            content = file_path.read_text()

            # Backup before modifying
            if not no_backup:
                self._backup(file_path)

            # Apply fix based on type
            if fix["fix_type"] == "add_resource":
                # Append new resource to file
                new_content = content.rstrip() + "\n\n" + replacement + "\n"
                file_path.write_text(new_content)
                self.ui.print_success(f"  {fix_id}: Added resource to {fix['file']}")
                applied += 1
            elif original and not original.startswith("#") and original in content:
                # Replace exact match
                new_content = content.replace(original, replacement, 1)
                file_path.write_text(new_content)
                self.ui.print_success(f"  {fix_id}: Applied to {fix['file']}")
                applied += 1
            elif fix["fix_type"] in ("add_attribute", "add_block"):
                # Append to file (best effort)
                new_content = content.rstrip() + "\n\n" + replacement + "\n"
                file_path.write_text(new_content)
                self.ui.print_success(f"  {fix_id}: Appended to {fix['file']}")
                applied += 1
            else:
                self.ui.print_warning(f"  {fix_id}: Cannot auto-apply — original not found in {fix['file']}")
                failed += 1

        # Report manual fixes
        if manual:
            self.ui.console.print(f"\n[bold]Manual fixes ({len(manual)}):[/bold]")
            for fix in manual:
                self.ui.console.print(f"  - {fix.get('fix_id', '?')}: {fix.get('description', '')}")

        action = "Would apply" if dry_run else "Applied"
        self.ui.print_info(f"\n{action}: {applied} | Failed: {failed} | Manual: {len(manual)}")

        if not dry_run and not no_backup and applied > 0:
            self.ui.print_info(f"Backups saved to {BACKUP_DIR}/")

    @staticmethod
    def _backup(file_path: Path):
        """Create timestamped backup of a file."""
        backup_dir = Path(BACKUP_DIR) / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        dest = backup_dir / file_path.name
        shutil.copy2(file_path, dest)


cli = ApplyFixCommand.as_click_command(name="apply-fix")(
    click.option("--fixes-file", required=True, type=click.Path(exists=True),
                 help="JSON file with generated fixes (from improve --output)"),
    click.option("--fix-ids", help="Comma-separated fix IDs to apply (default: all)"),
    click.option("--dry-run", is_flag=True, help="Preview changes without applying"),
    click.option("--no-backup", is_flag=True, help="Skip creating backups"),
    click.option("-d", "--directory", type=click.Path(exists=True), help="Base directory for file paths"),
)
