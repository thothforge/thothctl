import logging
import time
import os
from pathlib import Path
from typing import Dict, List, Tuple

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
from .scanners.kics import KICSScanner
from .scanners.scan_reports import ReportProcessor, ReportScanner
from .report_parser import parse_checkov_dir, parse_tool_result


def debug_print(message: str) -> None:
    """Print debug message only if debug mode is enabled."""
    if os.environ.get("THOTHCTL_DEBUG") == "true":
        print(f"[DEBUG] {message}")


def verbose_print(message: str) -> None:
    """Print verbose message if verbose or debug mode is enabled."""
    if os.environ.get("THOTHCTL_DEBUG") == "true" or os.environ.get("THOTHCTL_VERBOSE") == "true":
        print(f"[INFO] {message}")
# thothctl/application/scan_service.py (Application Layer)
from .scanners.scanners import ScanOrchestrator, Scanner
from .scanners.trivy import TrivyScanner
from .scanners.opa import OPAScanner
from .scanners.terraform_compliance import TerraformComplianceScanner


class ScanService:
    """Application service for managing security scans."""

    def __init__(self):
        self.available_scanners = {
            "trivy": Scanner("trivy", TrivyScanner()),
            "checkov": Scanner("checkov", CheckovScanner()),
            "kics": Scanner("kics", KICSScanner()),
            "opa": Scanner("opa", OPAScanner()),
            "terraform-compliance": Scanner("terraform-compliance", TerraformComplianceScanner()),
        }
        self.logger = logging.getLogger(__name__)

    def execute_scans(
        self,
        directory: str,
        reports_dir: str,
        selected_tools: List[str],
        options: Dict[str, Dict],
        tftool: str = "tofu",
        max_workers: int = 2,
        compact: bool = False,
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
                verbose_print("Clean up Directory")
                for t in selected_tools:
                    verbose_print(f"Removing {path.join(reports_path, t)}")
                    p = path.join(reports_path, t)
                    if path.exists(p):
                        DirectoryManager.ensure_empty_directory(
                            p, verbose=options.get("verbose", False), force_close=True
                        )
            results = {}
            total_issues = 0
            
            # Process Checkov reports if selected
            if "checkov" in selected_tools:
                checkov_reports_path = path.join(reports_path, "checkov")
                self._recursive_terraform_scan(
                    directory=directory,
                    reports_dir=checkov_reports_path,
                    options=options.get("checkov", {}),
                    tftool=tftool,
                    max_workers=max_workers,
                    compact=compact,
                )
                
                # Process the directory to generate HTML/compliance reports
                checkov_scan_dir = path.join(checkov_reports_path, "security-scan")
                if path.exists(checkov_scan_dir):
                    processor.process_directory(
                        directory=checkov_scan_dir, report_tool="checkov"
                    )
                
                # Parse all Checkov results using unified parser
                checkov_report = parse_checkov_dir(checkov_reports_path)
                
                results["checkov"] = {
                    "status": checkov_report.status,
                    "report_path": checkov_report.report_path,
                    "detailed_reports": checkov_report.detailed,
                    "issues_count": checkov_report.issues_count,
                    "report_data": checkov_report.to_report_data(),
                    "findings": [
                        {"id": f.id, "severity": f.severity, "title": f.title,
                         "resource": f.resource, "file": f.file, "line": f.line}
                        for f in checkov_report.findings
                    ],
                }
                total_issues += checkov_report.issues_count
                
                self.logger.info(
                    f"Checkov results: passed={checkov_report.passed}, "
                    f"failed={checkov_report.failed}, skipped={checkov_report.skipped}, "
                    f"errors={checkov_report.errors}"
                )
                    
            # Run other scanners (excluding checkov which is handled above)
            other_scanners = [
                self.available_scanners[tool]
                for tool in selected_tools
                if tool in self.available_scanners and tool != "checkov"
            ]
            if other_scanners:
                orchestrator = ScanOrchestrator(other_scanners)
                scan_results = orchestrator.run_scans(directory, reports_path, options)
                
                # Normalize results using unified parser
                for tool, raw_result in scan_results.items():
                    tool_report = parse_tool_result(tool, raw_result)
                    results[tool] = {
                        "status": tool_report.status,
                        "report_path": tool_report.report_path,
                        "report_data": tool_report.to_report_data(),
                        "issues_count": tool_report.issues_count,
                        "error": tool_report.error_message,
                        "findings": raw_result.get("findings", []),
                    }
                    total_issues += tool_report.issues_count
                
            # Add total issues to results
            results["summary"] = {"total_issues": total_issues}

            # Generate per-stack HTML reports with index browsing
            try:
                generator = HTMLReportGenerator()
                checkov_scan_path = path.join(reports_path, "checkov", "security-scan")
                if path.exists(checkov_scan_path):
                    generator.create_html_reports(directory=checkov_scan_path, mode="simple")
            except Exception as e:
                self.logger.warning(f"Per-stack HTML report generation failed: {e}")

            return results

        except Exception as e:
            self.logger.error(f"Scan execution failed: {e}")
            raise
            
    def _recursive_terraform_scan(
        self, directory: str, reports_dir: str, options: Dict, tftool: str,
        max_workers: int = 2, compact: bool = False,
    ) -> Dict[str, Dict]:
        """
        Recursively scan directories for Terraform files and run Checkov.

        Optimized for memory-constrained CI agents (4 CPU / 8 GB):
        - Parallel execution with controlled concurrency (max_workers)
        - GC runs after each completed scan to free memory
        - compact flag reduces checkov output memory usage
        """
        import gc
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {}
        scanner = self.available_scanners.get("checkov")
        if not scanner:
            raise ValueError("Checkov scanner not available")

        # Collect all scannable stack directories
        stacks = self._find_terraform_stacks(directory)

        if not stacks:
            self.logger.info(f"No terraform stacks found in {directory}")
            return results

        self.logger.info(f"Found {len(stacks)} terraform stacks to scan (workers={max_workers})")
        print(f"{Fore.MAGENTA}\n \U0001f50e Found {len(stacks)} stacks to scan (parallel={max_workers})")

        scan_options = dict(options)
        if compact:
            scan_options["compact"] = True

        def _scan_stack(stack_dir: str) -> Tuple[str, Dict]:
            print(f"{Fore.MAGENTA} \n \U0001f50e {stack_dir}")
            try:
                result = scanner.execute_scan(
                    directory=str(stack_dir),
                    reports_dir=str(reports_dir),
                    options=scan_options,
                    tftool=tftool,
                )
                return (stack_dir, result)
            except Exception as e:
                self.logger.error(f"Error scanning {stack_dir}: {e}")
                return (stack_dir, {"status": "FAIL", "error": str(e)})

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_scan_stack, s): s for s in stacks}
            for future in as_completed(futures):
                stack_dir, result = future.result()
                results[stack_dir] = result
                gc.collect()

        return results

    def _find_terraform_stacks(self, directory: str) -> List[str]:
        """Find all directories containing main.tf or tfplan.json."""
        stacks = []
        root = Path(directory)
        if (root / "main.tf").exists() or (root / "tfplan.json").exists():
            stacks.append(str(root))
        for d in sorted(root.rglob("*")):
            if not d.is_dir():
                continue
            if any(part.startswith(".") for part in d.relative_to(root).parts):
                continue
            if (d / "main.tf").exists() or (d / "tfplan.json").exists():
                stacks.append(str(d))
        return stacks
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
