import logging
import time
from pathlib import Path
from typing import Dict, List, Literal

from colorama import Fore
from os import path

from ...utils.common.create_compliance_html_reports import (
    ComplianceReportGenerator,
    ReportConfig,
)
from ...utils.common.create_html_reports import HTMLReportGenerator
from ...utils.common.delete_directory import DirectoryManager
# from .scanners.tfsec import TFSecScanner
from .scanners.checkov import CheckovScanner
from .scanners.scan_reports import ReportProcessor, ReportScanner
# thothctl/application/scan_service.py (Application Layer)
from .scanners.scanners import ScanOrchestrator, Scanner
from .scanners.trivy import TrivyScanner


class ScanService:
    """Application service for managing security scans."""

    def __init__(self):
        self.available_scanners = {
            "trivy": Scanner("trivy", TrivyScanner()),
            #           'tfsec': Scanner('tfsec', TFSecScanner()),
            "checkov": Scanner("checkov", CheckovScanner()),
            # Add other scanners
        }
        self.logger = logging.getLogger(__name__)

    def execute_scans(
        self,
        directory: str,
        reports_dir: str,
        selected_tools: List[str],
        options: Dict[str, Dict],
        tftool: str = "tofu",
        html_reports_format: Literal["simple", "xunit"] = "simple",
    ) -> Dict[str, Dict]:
        """Execute selected security scans."""
        try:
            report_generator = ComplianceReportGenerator(
                output_dir=reports_dir,
                config=ReportConfig(page_size="A0", orientation="Landscape"),
            )
            scanner = ReportScanner()
            processor = ReportProcessor(
                scanner=scanner,
                report_generator=report_generator,
                # teams_notifier=teams_notifier
            )

            if options is None:
                options = {}

            # Validate and prepare scanners
            scanners = [
                self.available_scanners[tool]
                for tool in selected_tools
                if tool in self.available_scanners
            ]

            if not scanners:
                raise ValueError("No valid scanners selected")

            # Create orchestrator and run scans
            self.logger.info(f"Executing scans with options: {options}")
            reports_path = path.join(directory, reports_dir)
            # Ensure clean reports directory

            if path.exists(reports_dir):
                print(Fore.GREEN + "Clean up Directory" + Fore.RESET)
                for t in selected_tools:
                    print(f"Removing {path.join(reports_path, t)}")
                    p = path.join(reports_path, t)
                    if path.exists(p):
                        reports_path = DirectoryManager.ensure_empty_directory(
                            p, verbose=options.get("verbose", False), force_close=True
                        )
            results = {}
            for tool in selected_tools:
                if tool == "checkov":
                    tool_results = self._recursive_terraform_scan(
                        directory=directory,
                        reports_dir=reports_dir,
                        options=options.get(tool, {}),
                        tftool=tftool,
                    )
                    results[tool] = tool_results
                    processor.process_directory(
                        directory=f"{reports_dir}/checkov", report_tool="checkov"
                    )
            orchestrator = ScanOrchestrator(scanners)
            results = orchestrator.run_scans(directory, reports_path, options)
            generator = HTMLReportGenerator()
            generator.create_html_reports(
                directory=reports_dir, mode=html_reports_format
            )

            return results

        except Exception as e:
            self.logger.error(f"Scan execution failed: {e}")
            raise

    def _recursive_terraform_scan(
        self, directory: str, reports_dir: str, options: Dict, tftool: str
    ) -> Dict[str, Dict]:
        """
        Recursively scan directories for Terraform files and run Checkov.
        """
        results = {}
        try:
            scanner = self.available_scanners.get("checkov")
            if not scanner:
                raise ValueError("Checkov scanner not available")

            # Scan current directory if it contains terraform files
            if (Path(directory) / "main.tf").exists() or (
                Path(directory) / "tfplan.json"
            ).exists():
                print(f"{Fore.MAGENTA} \n 🔎 {directory}")
                self.logger.debug(f"Found terraform files in {directory}")

                try:
                    result = scanner.execute_scan(
                        directory=str(directory),
                        reports_dir=str(reports_dir),
                        options=options,
                        tftool=tftool,
                    )
                    results[directory] = result
                except Exception as e:
                    self.logger.error(f"Error scanning {directory}: {e}")
                    results[directory] = {"status": "FAIL", "error": str(e)}

            # Recursively scan subdirectories
            subdirs = [
                d
                for d in Path(directory).iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]

            for subdir in subdirs:
                subdir_results = self._recursive_terraform_scan(
                    directory=str(subdir),
                    reports_dir=reports_dir,
                    options=options,
                    tftool=tftool,
                )
                results.update(subdir_results)

        except Exception as e:
            self.logger.error(f"Error during recursive scan: {e}")
            results[directory] = {"status": "FAIL", "error": str(e)}

        return results


def recursive_scan(
    directory: str,
    tool: str,
    reports_dir: str,
    features_dir: str = "",
    options=None,
    tftool="tofu",
):
    """
    Recursive Scan according to the tool selected.
    """
    try:
        # Initialize scanner
        scanner = CheckovScanner()

        # Scan current directory if it contains terraform files
        if (Path(directory) / "main.tf").exists() or (
            Path(directory) / "tfplan.json"
        ).exists():
            print(f"⚠️ Found terraform files in {directory}")
            print("❇️ Scanning ... ")

            try:
                result = scanner.scan(
                    directory=str(directory),
                    reports_dir=str(reports_dir),
                    options=options,
                    tftool=tftool,
                )
                if result["status"] == "COMPLETE":
                    print(f"✅ Scan complete: {result['report_path']}")
                else:
                    print(f"❌ Scan failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"❌ Error scanning {directory}: {str(e)}")

        # Recursively scan subdirectories
        start_time = time.perf_counter()

        # Get list of subdirectories (excluding hidden directories)
        subdirs = [
            d
            for d in Path(directory).iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

        for subdir in subdirs:
            print(f"📁 Checking directory: {subdir}")
            recursive_scan(
                directory=str(subdir),
                tool=tool,
                reports_dir=reports_dir,
                features_dir=features_dir,
                options=options,
                tftool=tftool,
            )

        finish_time = time.perf_counter()
        print(f"✨ Scan finished in {finish_time - start_time:.2f} seconds")

    except Exception as e:
        print(f"❌ Error during recursive scan: {str(e)}")
        raise
