import json
import logging
import xmltodict
from typing import Dict, Optional
from ....config.models import ScanResult, ReportStatus


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
                    "terraform-compliance": self._scan_terraform_compliance_report
                }

                if report_type in scanner_map:
                    return scanner_map[report_type](json_data)
                else:
                    logging.error(f"Unsupported report type: {report_type}")
                    return None

        except Exception as e:
            logging.error(f"Failed to scan report {report_path}: {str(e)}")
            return None

    def _scan_terraform_compliance_report(self, data: Dict) -> ScanResult:
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
                message=message
            )
        except Exception as e:
            logging.error(f"Error scanning Terraform-Compliance report: {str(e)}")
            return None

    def _scan_checkov_report(self, data: Dict) -> ScanResult:
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
                message=message
            )
        except Exception as e:
            logging.error(f"Error scanning Checkov report: {str(e)}")
            return None

    def _scan_tfsec_report(self, data: Dict) -> ScanResult:
        try:
            testsuites = data.get("testsuites", {})
            if isinstance(testsuites.get("testsuite"), list):
                failures = sum(int(suite.get("@failures", 0)) for suite in testsuites["testsuite"])
                tests = sum(int(suite.get("@tests", 0)) for suite in testsuites["testsuite"])
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
                message=message
            )
        except Exception as e:
            logging.error(f"Error scanning TFSec report: {str(e)}")
            return None

    def _scan_trivy_report(self, data: Dict) -> ScanResult:
        try:
            vulnerabilities = []
            total_tests = 0
            failures = 0

            for result in data.get("Results", []):
                if "Vulnerabilities" in result:
                    vulnerabilities.extend(result["Vulnerabilities"])
                    total_tests += len(result["Vulnerabilities"])
                    failures += sum(1 for v in result["Vulnerabilities"]
                                    if v.get("Severity", "").upper() in ["HIGH", "CRITICAL"])

            status = self._determine_status(failures, total_tests)
            message = self._create_message(failures, total_tests, "Trivy")

            return ScanResult(
                module_name=data.get("module", "unknown"),
                failures=failures,
                total_tests=total_tests,
                status=status,
                message=message
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
