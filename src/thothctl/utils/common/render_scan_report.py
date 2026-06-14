"""Render the unified scan HTML report from pre-parsed results (no XML re-parsing)."""
import os
from datetime import datetime
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader


_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def render_unified_report(
    results: dict,
    reports_dir: str,
    project_name: str = "Security Scan",
    scan_duration: str = "",
    trend: Optional[List[dict]] = None,
    trend_date: str = "",
) -> str:
    """Render a unified multi-tool HTML report from scan results.

    Combines current scan results with any existing tool results in the reports
    directory to produce a comprehensive multi-tool report.

    Args:
        results: The scan results dict (same format as ScanService returns)
        reports_dir: Where to write the HTML file
        project_name: Display name for the report header
        scan_duration: Formatted scan time string
        trend: Trend comparison rows (from scan_history.build_trend)
        trend_date: Date label for trend comparison

    Returns:
        Path to the generated HTML file.
    """
    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))
    template = env.get_template("unified_scan_report.html")

    # Merge current results with any existing tool results on disk
    merged = _merge_with_existing(results, reports_dir)

    # Build template context from merged results
    tools = []
    all_findings = []
    total_passed = total_failed = total_warnings = total_skipped = total_errors = 0

    for tool_name, tool_data in merged.items():
        if tool_name == "summary" or not isinstance(tool_data, dict):
            continue

        rd = tool_data.get("report_data", {})
        passed = rd.get("passed_count", 0)
        failed = rd.get("failed_count", 0)
        skipped = rd.get("skipped_count", 0)
        warnings = rd.get("warning_count", 0)
        errors = rd.get("error_count", 0)

        total_passed += passed
        total_failed += failed
        total_warnings += warnings
        total_skipped += skipped
        total_errors += errors

        tools.append({
            "tool": tool_name,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "warnings": warnings,
            "errors": errors,
            "total": passed + failed + skipped + warnings + errors,
        })

        for f in tool_data.get("findings", []):
            all_findings.append({**f, "tool": tool_name})

    # Sort findings: CRITICAL first, then HIGH, etc.
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    all_findings.sort(key=lambda f: sev_order.get(f.get("severity", "MEDIUM"), 2))

    total_tests = total_passed + total_failed + total_warnings + total_skipped + total_errors
    success_rate = round(total_passed / total_tests * 100, 1) if total_tests > 0 else 0

    # Severity counts
    severity_counts: Dict[str, int] = {}
    for f in all_findings:
        sev = f.get("severity", "MEDIUM")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Render
    html = template.render(
        project_name=project_name,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        scan_duration=scan_duration,
        tools=tools,
        total_tests=total_tests,
        total_passed=total_passed,
        total_failed=total_failed + total_errors,
        total_warnings=total_warnings,
        success_rate=success_rate,
        severity_counts=severity_counts,
        findings=all_findings,
        trend=trend,
        trend_date=trend_date,
    )

    # Write
    os.makedirs(reports_dir, exist_ok=True)
    output_path = os.path.join(reports_dir, "scan_report.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def _merge_with_existing(current_results: dict, reports_dir: str) -> dict:
    """Merge current scan results with previously scanned tool data from disk.
    
    Reads Reports/<tool>/report_*/results.json for tools not in current_results.
    """
    import json
    merged = dict(current_results)
    
    # Tools already in current results
    current_tools = {k for k in current_results if k != "summary" and isinstance(current_results.get(k), dict)}
    
    # Check for existing tool folders
    abs_reports = os.path.abspath(reports_dir)
    tool_dirs = {
        "checkov": os.path.join(abs_reports, "checkov"),
        "trivy": os.path.join(abs_reports, "trivy"),
        "opa": os.path.join(abs_reports, "opa"),
        "kics": os.path.join(abs_reports, "kics"),
    }
    
    for tool_name, tool_path in tool_dirs.items():
        if tool_name in current_tools:
            continue  # Already have fresh data
        if not os.path.isdir(tool_path):
            continue
            
        # Load existing results
        if tool_name == "checkov":
            from thothctl.services.scan.report_parser import parse_checkov_dir
            report = parse_checkov_dir(tool_path)
            if report.total > 0:
                merged[tool_name] = {
                    "status": "COMPLETE",
                    "report_data": report.to_report_data(),
                    "findings": [
                        {"id": f.id, "severity": f.severity, "title": f.title,
                         "resource": f.resource, "file": f.file, "line": f.line}
                        for f in report.findings
                    ],
                }
        elif tool_name == "trivy":
            passed, failed, findings = _load_trivy_from_disk(tool_path)
            if passed + failed > 0:
                merged[tool_name] = {
                    "status": "COMPLETE",
                    "report_data": {"passed_count": passed, "failed_count": failed, "skipped_count": 0, "error_count": 0, "warning_count": 0},
                    "findings": findings,
                }

    # Recalculate summary
    total_issues = sum(
        d.get("report_data", {}).get("failed_count", 0) + d.get("report_data", {}).get("error_count", 0)
        for k, d in merged.items() if k != "summary" and isinstance(d, dict)
    )
    merged["summary"] = {"total_issues": total_issues}
    
    return merged


def _load_trivy_from_disk(trivy_dir: str):
    """Load Trivy results from existing report files."""
    import json
    
    passed = failed = 0
    findings = []
    
    for direntry in os.listdir(trivy_dir):
        report_path = os.path.join(trivy_dir, direntry)
        if not os.path.isdir(report_path):
            continue
        # Check for results.json and tfplan_results.json
        for fname in ["results.json", "tfplan_results.json"]:
            fpath = os.path.join(report_path, fname)
            if not os.path.exists(fpath):
                continue
            try:
                with open(fpath) as f:
                    data = json.load(f)
                for result in data.get("Results", []):
                    summary = result.get("MisconfSummary", {})
                    passed += summary.get("Successes", 0)
                    failed += summary.get("Failures", 0)
                    for misconf in result.get("Misconfigurations", []):
                        if misconf.get("Status") == "PASS":
                            continue
                        cause = misconf.get("CauseMetadata", {})
                        findings.append({
                            "id": misconf.get("AVDID") or misconf.get("ID", ""),
                            "severity": (misconf.get("Severity") or "MEDIUM").upper(),
                            "title": misconf.get("Title", ""),
                            "resource": cause.get("Resource", ""),
                            "file": cause.get("Filename", result.get("Target", "")),
                            "line": cause.get("StartLine", 0),
                        })
            except (json.JSONDecodeError, OSError):
                continue
    
    return passed, failed, findings
