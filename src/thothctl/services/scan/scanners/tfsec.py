from pathlib import Path
from typing import Dict, Optional

from ....core.cli_ui import ScannerUI
from ....utils.platform_utils import find_executable, get_executable_name
from .scanners import ScannerPort


class TFSecScanner(ScannerPort):
    def __init__(self):
        self.ui = ScannerUI("TFSec")

    def _get_tfsec_executable(self) -> str:
        """Get the TFSec executable with platform-specific handling."""
        tfsec_path = find_executable("tfsec")
        if not tfsec_path:
            raise FileNotFoundError("TFSec executable not found in PATH")
        return tfsec_path

    def scan(
        self, directory: str, reports_dir: str, options: Optional[Dict] = None
    ) -> Dict[str, str]:
        try:
            reports_path = Path(reports_dir).resolve()
            reports_path.mkdir(parents=True, exist_ok=True)

            cmd = ["tfsec", directory]
            if options and options.get("additional_args"):
                cmd.extend(options["additional_args"])

            self.ui.start_scan_message(directory)
            return self.ui.run_with_progress(
                cmd=cmd, reports_path=reports_path, report_filename="tfsec_report.txt"
            )

        except Exception as e:
            self.ui.show_error(f"Scan failed: {str(e)}")
            return {"status": "FAIL", "error": str(e)}
