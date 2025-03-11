from pathlib import Path, PurePath
from typing import Dict, Optional

import os

from ....core.cli_ui import ScannerUI
from .scanners import ScannerPort


class CheckovScanner(ScannerPort):
    def __init__(self):
        self.ui = ScannerUI("Checkov")
        self.reports_path = "checkov"
        self.report_filename = "checkov_log_report.txt"

    def scan(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        tftool="tofu",
    ) -> Dict[str, str]:
        try:
            cmd = self._build_command(directory, options)
            tf_plan = PurePath(os.path.join(directory, "tfplan"))
            tf_plan_json = PurePath(os.path.join(directory, "tfplan.json"))

            if not os.path.exists(PurePath(tf_plan_json)) and os.path.exists(
                PurePath(tf_plan)
            ):
                os.system(
                    f"cd {directory} && {tftool} show -json tfplan  > tfplan.json"
                )

                cmd.extend(["-f", tf_plan_json])
            elif os.path.exists(PurePath(tf_plan_json)):
                cmd.extend(["-f", tf_plan_json])

            parent = Path(directory).resolve().parent.name
            name = Path(directory).resolve().name

            report_name = "report_" + (parent + "_" + name).replace("/", "_")
            reports_dir = self._prepare_reports_directory(reports_dir)
            report_path = PurePath(os.path.join(reports_dir, f"{report_name}"))  # .xml
            cmd.extend(
                [
                    "-s",
                    "-o",
                    "json",
                    "-o",
                    "junitxml",
                    "--output-file-path",
                    str(report_path),
                ]
            )

            # result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return self.ui.run_with_progress(
                cmd=cmd,
                reports_path=Path(reports_dir).resolve(),
                report_filename=self.report_filename,
            )
            # Generate report

        except Exception as e:
            self.ui.show_error(f"Checkov scan failed: {str(e)}")
            return {
                # 'status': ScanStatus.FAIL.value,
                "error": str(e)
            }

    def _build_command(self, directory: str, options: Optional[Dict]) -> list:
        """
        Build the Checkov command with options.

        Args:
            directory: Directory to scan
            options: Additional options for Checkov

        Returns:
            List of command components
        """

        cmd = ["checkov", "-d", directory]

        if options:
            # Add any additional arguments
            if "additional_args" in options:
                if isinstance(options["additional_args"], list):
                    cmd.extend(options["additional_args"])
                elif isinstance(options["additional_args"], str):
                    cmd.extend(options["additional_args"].split())

        return cmd

    def _prepare_reports_directory(self, reports_dir: str) -> Path:
        """
        Prepare the reports directory.

        Args:
            reports_dir: Base directory for reports

        Returns:
            Path object for the reports directory
        """
        reports_path = Path(reports_dir).joinpath(self.reports_path).resolve()
        reports_path.mkdir(parents=True, exist_ok=True)
        return reports_path
