# infrastructure/report_generator.py
import datetime
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import xmltodict
from json2html import json2html


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


@dataclass
class ReportConfig:
    page_size: str = "A0"
    orientation: str = "Landscape"
    margins: Dict[str, str] = None
    encoding: str = "UTF-8"

    def __post_init__(self):
        if self.margins is None:
            self.margins = {
                "top": "0.7in",
                "right": "0.7in",
                "bottom": "0.7in",
                "left": "0.7in",
            }

    @property
    def pdf_options(self) -> Dict:
        return {
            "page-size": self.page_size,
            "orientation": self.orientation,
            "encoding": self.encoding,
            **{f"margin-{k}": v for k, v in self.margins.items()},
        }


class ComplianceReportGenerator:
    def __init__(self, output_dir: str, config: Optional[ReportConfig] = None):
        self.output_dir = output_dir
        self.config = config or ReportConfig()
        self._css = self._get_default_css()

    def generate_report(self, summary_data: Dict) -> List[str]:
        """
        Generate HTML and PDF reports from compliance scan results.
        Returns list of generated file paths.
        """
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"SummaryComplianceFindings_{timestamp}"

            html_path = self._generate_html_report(base_filename, summary_data)
            pdf_path = self._generate_pdf_report(html_path, base_filename)

            return [html_path, pdf_path]

        except Exception as e:
            logging.error(f"Failed to generate reports: {str(e)}")
            return []

    def _generate_html_report(self, base_filename: str, summary_data: Dict) -> str:
        """Generate HTML report with styling"""
        html_content = self._create_html_content(summary_data)
        html_path = os.path.join(self.output_dir, f"{base_filename}.html")

        try:
            with open(html_path, "w") as f:
                f.write(html_content)
            logging.info(f"Created HTML report: {html_path}")
            return html_path

        except Exception as e:
            logging.error(f"Failed to create HTML report: {str(e)}")
            raise

    def _generate_pdf_report(self, html_path: str, base_filename: str) -> str:
        """Generate PDF from HTML report"""
        pdf_path = os.path.join(self.output_dir, f"{base_filename}.pdf")

        try:
            # pdfkit.from_file  # REMOVED(html_path, pdf_path, options=self.config.pdf_options)
            logging.info(f"Created PDF report: {pdf_path}")
            return pdf_path

        except Exception as e:
            logging.error(f"Failed to create PDF report: {str(e)}")
            raise

    def _create_html_content(self, summary_data: Dict) -> str:
        """Create complete HTML content with styling and data"""
        table_html = json2html.convert(
            json=summary_data, table_attributes='id="report-table" class="fl-table"'
        )

        return f"""
        <html>
        <style>
        {self._css}
        </style>
        <body>
            <h1 style="font-size:100px; color:black; margin:10px;">Compliance Findings for IaC</h1>
            <p style="font-size:30px; color: black;">
                <em>Compliance Findings for IaC using IaC peerbot</em>
            </p>
            {table_html}
        </body>
        </html>
        """

    @staticmethod
    def _get_default_css() -> str:
        return """
        .fl-table {
            border-radius: 5px;
            font-size: 12px;
            font-weight: normal;
            border: none;
            border-collapse: collapse;
            width: 100%;
            max-width: 100%;
            white-space: nowrap;
            background-color: white;
        }

        .fl-table td, .fl-table th {
            text-align: left;
            padding: 8px;
            border: solid 1px #777;
        }

        .fl-table td {
            border-right: 1px solid #f8f8f8;
            font-size: 14px;
        }

        .fl-table thead th {
            color: #ffffff;
            background: #35259C;
        }

        .fl-table thead th:nth-child(odd) {
            color: #ffffff;
            background: #324960;
        }

        .fl-table tr:nth-child(even) {
            background: #F8F8F8;
        }
        """


# use_cases/report_processor.py
class ComplianceReportProcessor:
    def __init__(self, scanner, report_generator, teams_notifier=None):
        self.scanner = scanner
        self.report_generator = report_generator
        self.teams_notifier = teams_notifier

    def process_reports(self, directory: str, report_tool: str) -> None:
        """Process all reports in directory and generate summary"""
        summary = {"Summary": []}
        print("reports chekov")
        for filename in os.listdir(directory):
            if not filename.endswith(".xml"):
                continue

            filepath = os.path.join(directory, filename)
            scan_result = self.scanner.scan_report(filepath, report_tool)

            if scan_result and scan_result.failures > 0 and scan_result.total_tests > 0:
                summary["Summary"].append(
                    {
                        "Name": filename,
                        "summary": scan_result.message,
                        "fails": scan_result.failures,
                        "tests": scan_result.total_tests,
                    }
                )

                if self.teams_notifier:
                    self.teams_notifier.send_scan_result(scan_result)

        if summary["Summary"]:
            self.report_generator.generate_report(summary)


from pathlib import Path  # noqa: E402


@dataclass
class ScanSummary:
    file_path: str
    name: str
    summary: str
    fails: int
    tests: int


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


reports_dir = "/home/labvel/projects/thoth/IaCTemplates/demos/eks_demo2/Reports/checkov"
report_generator = ComplianceReportGenerator(
    output_dir=reports_dir, config=ReportConfig(page_size="A0", orientation="Landscape")
)
scanner = ReportScanner()
processor = ReportProcessor(
    scanner=scanner,
    report_generator=report_generator,
    # teams_notifier=teams_notifier
)

processor.process_directory(directory=reports_dir, report_tool="checkov")
