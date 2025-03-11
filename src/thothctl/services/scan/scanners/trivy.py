from pathlib import Path
from typing import Dict, Optional

from ....core.cli_ui import ScannerUI
from .scanners import ScannerPort


# from ....config.models import ScanResult, ScanStatus


class TrivyScanner(ScannerPort):
    """Trivy security scanner implementation."""

    def __init__(self):
        self.ui = ScannerUI("Trivy")
        self.report_filename = "trivy_report.txt"
        self.reports_path = "trivy"

    def scan(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        tftoo: str = None,
    ) -> Dict[str, str]:
        """
        Execute Trivy scan on specified directory.

        Args:
            directory: Directory to scan
            reports_dir: Directory to store reports
            options: Optional configuration for the scanner

        Returns:
            Dict containing scan status and results
        """
        try:
            # Prepare directory and command
            reports_path = self._prepare_reports_directory(reports_dir)
            cmd = self._build_command(directory, options)

            # Execute scan with UI
            self.ui.start_scan_message(directory)
            return self.ui.run_with_progress(
                cmd=cmd,
                reports_path=reports_path,
                report_filename=self.report_filename,
                additional_processors=self._get_custom_processors(),
            )

        except Exception as e:
            self.ui.show_error(f"Trivy scan failed: {str(e)}")
            return {
                #'status': ScanStatus.FAIL.value,
                "error": str(e)
            }

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

    def _build_command(self, directory: str, options: Optional[Dict]) -> list:
        """
        Build the Trivy command with options.

        Args:
            directory: Directory to scan
            options: Additional options for Trivy

        Returns:
            List of command components
        """
        cmd = ["trivy", "config", directory]

        if options:
            # Add severity filter if specified
            if "severity" in options:
                cmd.extend(["--severity", options["severity"]])

            # Add format option if specified
            if "format" in options:
                cmd.extend(["--format", options["format"]])

            # Add any additional arguments
            if "additional_args" in options:
                if isinstance(options["additional_args"], list):
                    cmd.extend(options["additional_args"])
                elif isinstance(options["additional_args"], str):
                    cmd.extend(options["additional_args"].split())

        return cmd

    def _get_custom_processors(self) -> Dict:
        """
        Get custom processors for Trivy-specific output.

        Returns:
            Dictionary of custom message processors
        """

        def process_vulnerability(content: str):
            """Process vulnerability information."""
            if "CRITICAL" in content or "HIGH" in content:
                self.ui.console.print(f"[red]{content}[/red]")
            elif "MEDIUM" in content:
                self.ui.console.print(f"[yellow]{content}[/yellow]")
            elif "LOW" in content:
                self.ui.console.print(f"[blue]{content}[/blue]")

        def process_summary(content: str):
            """Process summary information."""
            if "Total:" in content:
                self.ui.console.print(f"[cyan]{content}[/cyan]")

        return {"vulnerability": process_vulnerability, "summary": process_summary}
