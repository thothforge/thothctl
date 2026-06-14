"""Unified report parser — single place to parse XML/JSON reports from all scan tools."""
import json
import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

from .models import Finding, ToolReport

logger = logging.getLogger(__name__)


def parse_junit_xml(xml_path: str) -> Dict[str, int]:
    """Parse a JUnit XML file and return pass/fail/skip/error counts."""
    passed = failed = skipped = errors = 0
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for testsuite in root.findall(".//testsuite"):
            tests = int(testsuite.get("tests", "0"))
            f = int(testsuite.get("failures", "0"))
            e = int(testsuite.get("errors", "0"))
            s = int(testsuite.get("skipped", "0"))
            failed += f
            errors += e
            skipped += s
            passed += tests - f - e - s

        # Fallback: count individual testcases if testsuite attrs are empty
        if passed + failed + skipped + errors == 0:
            for tc in root.findall(".//testcase"):
                if tc.find("failure") is not None:
                    failed += 1
                elif tc.find("error") is not None:
                    errors += 1
                elif tc.find("skipped") is not None:
                    skipped += 1
                else:
                    passed += 1
    except Exception as e:
        logger.warning(f"Error parsing XML {xml_path}: {e}")

    return {"passed": passed, "failed": failed, "skipped": skipped, "errors": errors}


def find_xml_reports(base_dir: str) -> List[str]:
    """Find all JUnit XML report files under a directory."""
    xml_files = []
    if not os.path.isdir(base_dir):
        return xml_files
    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.endswith(".xml"):
                xml_files.append(os.path.join(root, f))
    return xml_files


def parse_checkov_dir(reports_dir: str) -> ToolReport:
    """Parse all Checkov reports under reports_dir into a ToolReport."""
    report = ToolReport(tool="checkov", report_path=os.path.join(reports_dir, "security-scan"))

    # Checkov scanner writes to security-scan/ subdirectory
    checkov_dir = os.path.join(reports_dir, "security-scan")
    if not os.path.isdir(checkov_dir):
        # Fallback: try checkov/ or the reports_dir itself
        checkov_dir = os.path.join(reports_dir, "checkov")
        if not os.path.isdir(checkov_dir):
            checkov_dir = reports_dir

    xml_files = find_xml_reports(checkov_dir)
    if not xml_files:
        # Fallback: search entire reports_dir
        xml_files = find_xml_reports(reports_dir)

    if not xml_files:
        report.status = "COMPLETE"
        return report

    for xml_path in xml_files:
        counts = parse_junit_xml(xml_path)
        stack_name = os.path.basename(os.path.dirname(xml_path))
        report.detailed[stack_name] = {
            "passed": counts["passed"],
            "failed": counts["failed"],
            "skipped": counts["skipped"],
            "error": counts["errors"],
            "total": sum(counts.values()),
            "report_path": xml_path,
        }
        report.passed += counts["passed"]
        report.failed += counts["failed"]
        report.skipped += counts["skipped"]
        report.errors += counts["errors"]

    # Extract findings from JSON if available
    report.findings = _extract_checkov_findings(checkov_dir)
    report.status = "COMPLETE"
    return report


def parse_tool_result(tool: str, raw_result: Dict) -> ToolReport:
    """Convert a raw scanner result dict into a ToolReport."""
    report = ToolReport(
        tool=tool,
        status=raw_result.get("status", "UNKNOWN"),
        report_path=raw_result.get("report_path", ""),
        error_message=raw_result.get("error", ""),
    )

    rd = raw_result.get("report_data", {})
    if rd:
        report.passed = rd.get("passed_count", 0)
        report.failed = rd.get("failed_count", 0)
        report.skipped = rd.get("skipped_count", 0)
        report.errors = rd.get("error_count", 0)
        report.warnings = rd.get("warning_count", 0)

    # If report_data was empty, try report_path XML files
    if report.total == 0 and report.status == "COMPLETE" and report.report_path:
        xml_files = find_xml_reports(report.report_path)
        for xml_path in xml_files:
            counts = parse_junit_xml(xml_path)
            report.passed += counts["passed"]
            report.failed += counts["failed"]
            report.skipped += counts["skipped"]
            report.errors += counts["errors"]

    return report


def _extract_checkov_findings(checkov_dir: str) -> List[Finding]:
    """Extract individual findings from Checkov JSON reports."""
    findings: List[Finding] = []
    if not os.path.isdir(checkov_dir):
        return findings

    for root, _, files in os.walk(checkov_dir):
        for f in files:
            if not f.endswith(".json"):
                continue
            json_path = os.path.join(root, f)
            try:
                with open(json_path, "r") as fh:
                    data = json.load(fh)
                if not isinstance(data, dict) or "results" not in data:
                    continue
                results = data["results"]
                # Handle both formats:
                # Format 1: {"results": {"failed_checks": [...]}}
                # Format 2: {"results": {"check_type": {"failed_checks": [...]}}}
                failed_checks = []
                if isinstance(results, dict):
                    if "failed_checks" in results:
                        failed_checks = results["failed_checks"]
                    else:
                        for section in results.values():
                            if isinstance(section, dict) and "failed_checks" in section:
                                failed_checks.extend(section["failed_checks"])
                            elif isinstance(section, list):
                                # Some formats have the list directly
                                failed_checks.extend(section)

                for check in failed_checks:
                    if not isinstance(check, dict):
                        continue
                    severity = check.get("severity") or "MEDIUM"
                    findings.append(Finding(
                        id=check.get("check_id", ""),
                        severity=severity.upper() if severity else "MEDIUM",
                        title=check.get("check_name", ""),
                        resource=check.get("resource", ""),
                        file=check.get("file_path", ""),
                        line=check.get("file_line_range", [0])[0] if check.get("file_line_range") else 0,
                    ))
            except (json.JSONDecodeError, OSError):
                continue

    return findings
