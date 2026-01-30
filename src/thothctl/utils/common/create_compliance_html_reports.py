import datetime
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import os
from json2html import json2html


@dataclass
class ReportConfig:
    encoding: str = "UTF-8"
    page_size: str = "A4"
    orientation: str = "Portrait"


class ComplianceReportGenerator:
    def __init__(self, output_dir: str, config: Optional[ReportConfig] = None):
        self.output_dir = output_dir
        self.config = config or ReportConfig()
        self._css = self._get_default_css()

    def generate_report(self, summary_data: Dict) -> List[str]:
        """
        Generate HTML report from compliance scan results.
        Returns list of generated file paths.
        """
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"SummaryComplianceFindings_{timestamp}"

            html_path = self._generate_html_report(base_filename, summary_data)
            return [html_path]

        except Exception as e:
            logging.error(f"Failed to generate report: {str(e)}")
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
