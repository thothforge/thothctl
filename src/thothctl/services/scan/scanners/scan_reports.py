import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import xmltodict


class ReportStatus(Enum):
    APPROVED = "APPROVED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


@dataclass
class ScanResult:
    module_name: str
    failures: int
    total_tests: int
    status: ReportStatus
    message: str


@dataclass
class ScanSummary:
    file_path: str
    name: str
    summary: str
    fails: int
    tests: int


@dataclass
class ReportSummary:
    results: List[ScanResult]


class ReportScanner:
    def scan_report(self, report_path: str, report_type: str) -> Optional[ScanResult]:
        try:
            with open(report_path) as report_file:
                if report_type in ["checkov", "tfsec", "terraform-compliance"]:
                    data = xmltodict.parse(report_file.read())
                    json_data = json.loads(json.dumps(data))
                else:  # trivy uses JSON format
                    json_data = json.load(report_file)

                scanner_map = {
                    "checkov": self._scan_checkov_report,
                    "tfsec": self._scan_tfsec_report,
                    "trivy": self._scan_trivy_report,
                    "terraform-compliance": self._scan_terraform_compliance_report,
                }

                if report_type in scanner_map:
                    return scanner_map[report_type](json_data)
                else:
                    logging.error(f"Unsupported report type: {report_type}")
                    return None

        except Exception as e:
            logging.error(f"Failed to scan report {report_path}: {str(e)}")
            return None

    def _scan_terraform_compliance_report(self, data: Dict) -> Optional[ScanResult]:
        """
        Scan terraform compliance reports.
        """
        try:
            failures = 0
            tests = 0

            if "testsuites" in data and "testsuite" in data["testsuites"]:
                test_suites = data["testsuites"]["testsuite"]
                # Handle both single testsuite and multiple testsuites
                if isinstance(test_suites, list):
                    for suite in test_suites:
                        failures += int(suite.get("@failures", 0))
                        tests += int(suite.get("@tests", 0))
                else:
                    failures = int(test_suites.get("@failures", 0))
                    tests = int(test_suites.get("@tests", 0))

            status = self._determine_status(failures, tests)
            message = self._create_message(failures, tests, "Terraform-Compliance")

            return ScanResult(
                module_name=data.get("module", "unknown"),
                failures=failures,
                total_tests=tests,
                status=status,
                message=message,
            )
        except Exception as e:
            logging.error(f"Error scanning Terraform-Compliance report: {str(e)}")
            return None

    def _scan_checkov_report(self, data: Dict) -> Optional[ScanResult]:
        try:
            failures = int(data["testsuites"]["@failures"])
            tests = int(data["testsuites"]["@tests"])

            status = self._determine_status(failures, tests)
            message = self._create_message(failures, tests, "Checkov")

            return ScanResult(
                module_name=data.get("module", "unknown"),
                failures=failures,
                total_tests=tests,
                status=status,
                message=message,
            )
        except Exception as e:
            logging.error(f"Error scanning Checkov report: {str(e)}")
            return None

    def _scan_tfsec_report(self, data: Dict) -> Optional[ScanResult]:
        try:
            testsuites = data.get("testsuites", {})
            if isinstance(testsuites.get("testsuite"), list):
                failures = sum(
                    int(suite.get("@failures", 0)) for suite in testsuites["testsuite"]
                )
                tests = sum(
                    int(suite.get("@tests", 0)) for suite in testsuites["testsuite"]
                )
            else:
                failures = int(testsuites.get("testsuite", {}).get("@failures", 0))
                tests = int(testsuites.get("testsuite", {}).get("@tests", 0))

            status = self._determine_status(failures, tests)
            message = self._create_message(failures, tests, "TFSec")

            return ScanResult(
                module_name=data.get("module", "unknown"),
                failures=failures,
                total_tests=tests,
                status=status,
                message=message,
            )
        except Exception as e:
            logging.error(f"Error scanning TFSec report: {str(e)}")
            return None

    def _scan_trivy_report(self, data: Dict) -> Optional[ScanResult]:
        try:
            vulnerabilities: List = []
            total_tests = 0
            failures = 0

            for result in data.get("Results", []):
                if "Vulnerabilities" in result:
                    vulnerabilities.extend(result["Vulnerabilities"])
                    total_tests += len(result["Vulnerabilities"])
                    failures += sum(
                        1
                        for v in result["Vulnerabilities"]
                        if v.get("Severity", "").upper() in ["HIGH", "CRITICAL"]
                    )

            status = self._determine_status(failures, total_tests)
            message = self._create_message(failures, total_tests, "Trivy")

            return ScanResult(
                module_name=data.get("module", "unknown"),
                failures=failures,
                total_tests=total_tests,
                status=status,
                message=message,
            )
        except Exception as e:
            logging.error(f"Error scanning Trivy report: {str(e)}")
            return None

    def _determine_status(self, failures: int, tests: int) -> ReportStatus:
        if failures == 0 and tests == 0:
            return ReportStatus.SKIPPED
        elif failures == 0:
            return ReportStatus.APPROVED
        return ReportStatus.FAILED

    def _create_message(self, failures: int, tests: int, scan_type: str) -> str:
        if failures == 0 and tests == 0:
            return f"No rules defined for {scan_type} scanning"
        elif failures == 0:
            return f"Approved {scan_type} scanning"
        return f"Failed {scan_type} scanning"


class ReportProcessor:
    def __init__(self, scanner, report_generator, teams_notifier=None):
        self.scanner = scanner
        self.report_generator = report_generator
        self.teams_notifier = teams_notifier

    def process_directory(self, directory: str, report_tool: str) -> None:
        """Process all reports in directory and subdirectories"""
        try:
            summary = {"Summary": []}
            scan_results = self._scan_directory(Path(directory), report_tool)

            for result in scan_results:
                if self._should_include_in_summary(result):
                    summary["Summary"].append(self._create_summary_entry(result))

                    if self.teams_notifier:
                        self.teams_notifier.send_scan_result(result)

            if summary["Summary"]:
                self.report_generator.generate_report(summary)

        except Exception as e:
            logging.error(f"Error processing directory {directory}: {e}")
            raise

    def _scan_directory(self, directory: Path, report_tool: str) -> List[ScanSummary]:
        """Recursively scan all XML files in directory and subdirectories"""
        results = []

        try:
            for item in directory.rglob("*.xml"):
                scan_result = self._process_file(item, report_tool)
                if scan_result:
                    results.append(scan_result)

        except Exception as e:
            logging.error(f"Error scanning directory {directory}: {e}")

        return results

    def _process_file(self, file_path: Path, report_tool: str) -> Optional[ScanSummary]:
        """Process a single XML file"""
        try:
            scan_result = self.scanner.scan_report(str(file_path), report_tool)

            if scan_result:
                return ScanSummary(
                    file_path=str(file_path),
                    name=file_path.name,
                    summary=scan_result.message,
                    fails=scan_result.failures,
                    tests=scan_result.total_tests,
                )

        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")

        return None

    def _should_include_in_summary(self, result: ScanSummary) -> bool:
        """Determine if scan result should be included in summary"""
        return result and result.fails > 0 and result.tests > 0

    def _create_summary_entry(self, result: ScanSummary) -> Dict:
        """Create a summary entry for reporting"""
        return {
            "Name": result.name,
            "Path": result.file_path,
            "summary": result.summary,
            "fails": result.fails,
            "tests": result.tests,
        }
