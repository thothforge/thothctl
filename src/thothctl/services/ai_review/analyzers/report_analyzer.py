"""Report analyzer - parses scan results and sends to AI for analysis."""
import json
import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ReportAnalyzer:
    """Analyzes existing scan reports (Checkov, KICS, Trivy) and prepares them for AI analysis."""

    def parse_scan_results(self, scan_dir: str) -> Dict[str, Any]:
        """Parse all scan results from a reports directory."""
        results: Dict[str, Any] = {"tools": {}, "total_findings": 0}
        scan_path = Path(scan_dir)

        if not scan_path.exists():
            logger.warning(f"Scan directory not found: {scan_dir}")
            return results

        # Auto-detect and parse different report formats
        for tool_dir in scan_path.iterdir():
            if tool_dir.is_dir():
                tool_name = tool_dir.name.lower()
                parser = self._get_parser(tool_name)
                if parser:
                    tool_results = parser(tool_dir)
                    results["tools"][tool_name] = tool_results
                    results["total_findings"] += tool_results.get("total_issues", 0)

        # Also check for standalone files
        for f in scan_path.glob("*.json"):
            self._try_parse_json_report(f, results)

        return results

    def format_for_ai(self, scan_results: Dict[str, Any]) -> str:
        """Format parsed scan results into a concise string for AI analysis."""
        lines = [f"Total findings across all tools: {scan_results.get('total_findings', 0)}\n"]

        for tool, data in scan_results.get("tools", {}).items():
            lines.append(f"## {tool.upper()} Results")
            lines.append(f"Passed: {data.get('passed', 0)}, Failed: {data.get('failed', 0)}")

            for finding in data.get("findings", [])[:50]:  # Limit to avoid token overflow
                lines.append(
                    f"- [{finding.get('severity', 'UNKNOWN')}] {finding.get('check_id', '')}: "
                    f"{finding.get('check_name', '')} in {finding.get('resource', 'N/A')} "
                    f"({finding.get('file', 'N/A')})"
                )
            lines.append("")

        return "\n".join(lines)

    def _get_parser(self, tool_name: str):
        parsers = {
            "checkov": self._parse_checkov,
            "kics": self._parse_kics,
            "trivy": self._parse_trivy,
        }
        return parsers.get(tool_name)

    def _parse_checkov(self, tool_dir: Path) -> Dict[str, Any]:
        """Parse Checkov JSON/XML results."""
        result = {"passed": 0, "failed": 0, "total_issues": 0, "findings": []}

        for json_file in tool_dir.rglob("results_json.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)

                if isinstance(data, list):
                    for entry in data:
                        self._extract_checkov_entry(entry, result)
                elif isinstance(data, dict):
                    self._extract_checkov_entry(data, result)
            except Exception as e:
                logger.debug(f"Error parsing {json_file}: {e}")

        # Fallback to XML
        if not result["findings"]:
            for xml_file in tool_dir.rglob("*.xml"):
                self._parse_checkov_xml(xml_file, result)

        result["total_issues"] = result["failed"]
        return result

    def _extract_checkov_entry(self, data: Dict, result: Dict) -> None:
        results_section = data.get("results", {})
        for check_type, checks in results_section.items():
            if isinstance(checks, dict):
                for check in checks.get("passed_checks", []):
                    result["passed"] += 1
                for check in checks.get("failed_checks", []):
                    result["failed"] += 1
                    result["findings"].append({
                        "check_id": check.get("check_id", ""),
                        "check_name": check.get("check_name", ""),
                        "severity": check.get("severity", "MEDIUM"),
                        "resource": check.get("resource", ""),
                        "file": check.get("file_path", ""),
                        "guideline": check.get("guideline", ""),
                    })

    def _parse_checkov_xml(self, xml_file: Path, result: Dict) -> None:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            for ts in root.findall(".//testsuite"):
                tests = int(ts.get("tests", "0"))
                failures = int(ts.get("failures", "0"))
                result["passed"] += tests - failures
                result["failed"] += failures
        except Exception as e:
            logger.debug(f"Error parsing XML {xml_file}: {e}")

    def _parse_kics(self, tool_dir: Path) -> Dict[str, Any]:
        """Parse KICS JSON results."""
        result = {"passed": 0, "failed": 0, "total_issues": 0, "findings": []}

        for json_file in tool_dir.rglob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                for query in data.get("queries", []):
                    severity = query.get("severity", "MEDIUM").upper()
                    for file_entry in query.get("files", []):
                        result["failed"] += 1
                        result["findings"].append({
                            "check_id": query.get("query_id", ""),
                            "check_name": query.get("query_name", ""),
                            "severity": severity,
                            "resource": file_entry.get("resource_type", ""),
                            "file": file_entry.get("file_name", ""),
                        })
            except Exception as e:
                logger.debug(f"Error parsing KICS {json_file}: {e}")

        result["total_issues"] = result["failed"]
        return result

    def _parse_trivy(self, tool_dir: Path) -> Dict[str, Any]:
        """Parse Trivy JSON results."""
        result = {"passed": 0, "failed": 0, "total_issues": 0, "findings": []}

        for json_file in tool_dir.rglob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                for res in data.get("Results", []):
                    for vuln in res.get("Misconfigurations", []):
                        status = vuln.get("Status", "FAIL")
                        if status == "PASS":
                            result["passed"] += 1
                        else:
                            result["failed"] += 1
                            result["findings"].append({
                                "check_id": vuln.get("ID", ""),
                                "check_name": vuln.get("Title", ""),
                                "severity": vuln.get("Severity", "MEDIUM").upper(),
                                "resource": vuln.get("CauseMetadata", {}).get("Resource", ""),
                                "file": res.get("Target", ""),
                            })
            except Exception as e:
                logger.debug(f"Error parsing Trivy {json_file}: {e}")

        result["total_issues"] = result["failed"]
        return result

    def _try_parse_json_report(self, json_file: Path, results: Dict) -> None:
        """Try to auto-detect and parse a standalone JSON report."""
        try:
            with open(json_file) as f:
                data = json.load(f)
            # Detect format by keys
            if "queries" in data:
                results["tools"]["kics"] = self._parse_kics(json_file.parent)
            elif "Results" in data:
                results["tools"]["trivy"] = self._parse_trivy(json_file.parent)
        except Exception:
            pass
