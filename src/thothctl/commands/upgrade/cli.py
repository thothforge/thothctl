"""ThothCTL upgrade command implementation."""
import logging
import subprocess
import sys
from importlib.metadata import version

import click
import requests

from ...core.cli_ui import CliUI
from ...core.commands import ClickCommand


logger = logging.getLogger(__name__)


class UpgradeCommand(ClickCommand):
    """Command to upgrade thothctl to the latest version."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, **kwargs) -> bool:
        """Validate upgrade parameters."""
        return True

    def _execute(self, check_only: bool = False, **kwargs) -> None:
        """
        Execute thothctl upgrade.

        Args:
            check_only: Only check for updates without installing
        """
        try:
            current_version = self._get_current_version()
            latest_version = self._get_latest_version()

            self.ui.print_info(f"📦 Current version: {current_version}")
            self.ui.print_info(f"🔍 Latest version: {latest_version}")

            if current_version == latest_version:
                self.ui.print_success("✅ ThothCTL is already up to date!")
                return

            self.ui.print_warning(f"⚠️  Update available: {current_version} → {latest_version}")

            if check_only:
                self.ui.print_info("💡 Run 'thothctl upgrade' to install the update")
                return

            if self._confirm_upgrade(current_version, latest_version):
                self._perform_upgrade()
            else:
                self.ui.print_info("❌ Upgrade cancelled")

        except Exception as e:
            self.ui.print_error(f"Failed to upgrade thothctl: {str(e)}")
            logger.exception("ThothCTL upgrade failed")
            raise click.Abort()

    def _get_current_version(self) -> str:
        """Get current thothctl version."""
        try:
            return version('thothctl')
        except Exception:
            return "unknown"

    def _get_latest_version(self) -> str:
        """Get latest thothctl version from PyPI."""
        try:
            response = requests.get("https://pypi.org/pypi/thothctl/json", timeout=10)
            response.raise_for_status()
            data = response.json()
            return data["info"]["version"]
        except Exception as e:
            logger.error(f"Failed to get latest version: {e}")
            raise Exception("Unable to check for updates. Please check your internet connection.")

    def _confirm_upgrade(self, current: str, latest: str) -> bool:
        """Confirm upgrade with user."""
        return click.confirm(f"Upgrade from {current} to {latest}?", default=True)

    def _perform_upgrade(self) -> None:
        """Perform the actual upgrade."""
        self.ui.print_info("🚀 Upgrading thothctl...")
        
        try:
            # Use pip to upgrade thothctl with --break-system-packages flag
            cmd = [
                sys.executable, 
                "-m", 
                "pip", 
                "install", 
                "--upgrade", 
                "--break-system-packages",
                "thothctl"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            self.ui.print_success("✅ ThothCTL upgraded successfully!")
            self.ui.print_info("💡 Restart your terminal or run 'hash -r' to use the new version")
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise Exception(f"Upgrade failed: {error_msg}")


# Create the Click command
cli = UpgradeCommand.as_click_command(
    help="Upgrade thothctl to the latest version"
)(
    click.option(
        "--check-only",
        is_flag=True,
        default=False,
        help="Only check for updates without installing",
    ),
)
