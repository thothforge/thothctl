from pathlib import Path
from typing import Dict, Optional

from ....core.cli_ui import ScannerUI
from .scanners import ScannerPort


class TFSecScanner(ScannerPort):
    def __init__(self):
        self.ui = ScannerUI("TFSec")

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
