"""Trivy IaC misconfiguration scanner — per-stack with HTML reports."""
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from ....core.cli_ui import ScannerUI
from ....utils.platform_utils import find_executable
from .scanners import ScannerPort

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "utils", "common", "templates"
)


class TrivyScanner(ScannerPort):
    """Trivy security scanner for IaC misconfigurations. Per-stack scanning with HTML reports."""

    def __init__(self):
        self.ui = ScannerUI("Trivy")
        self.logger = logging.getLogger(__name__)

    def scan(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        tftool: str = "tofu",
    ) -> Dict[str, str]:
        """Execute Trivy IaC scan per-stack and return structured results."""
        trivy = find_executable("trivy")
        if not trivy:
            raise FileNotFoundError(
                "trivy not found in PATH. Install: https://trivy.dev/latest/getting-started/installation/"
            )

        abs_dir = os.path.abspath(directory)
        report_dir = os.path.join(os.path.abspath(reports_dir), "trivy")
        os.makedirs(report_dir, exist_ok=True)

        # Find stacks — only .tf dirs, skip tfplan (1:1 duplicate)
        stacks = self._find_stacks(abs_dir)
        if not stacks:
            stacks = [abs_dir]

        self.ui.start_scan_message(f"{directory} ({len(stacks)} stacks)")

        all_findings: List[Dict] = []
        total_passed = total_failed = 0
        detailed = {}

        for stack_dir in stacks:
            rel = os.path.relpath(stack_dir, abs_dir)
            stack_name = rel.replace(os.sep, "_") if rel != "." else "root"
            stack_report_dir = os.path.join(report_dir, f"report_{stack_name}")
            os.makedirs(stack_report_dir, exist_ok=True)
            json_report = os.path.join(stack_report_dir, "results.json")

            cmd = [trivy, "config", "--format", "json", "--output", json_report, stack_dir]
            if options and options.get("severity"):
                cmd.insert(3, "--severity")
                cmd.insert(4, options["severity"])

            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            except (subprocess.TimeoutExpired, Exception) as e:
                self.logger.warning(f"Trivy scan failed for {stack_name}: {e}")
                continue

            passed, failed, findings = self._parse_stack_results(json_report)

            # Also scan corresponding tfplan dir and merge results
            tfplan_dir = self._find_tfplan_for_stack(abs_dir, stack_dir)
            if tfplan_dir:
                tfplan_json = os.path.join(tfplan_dir, "tfplan.json")
                tfplan_report = os.path.join(stack_report_dir, "tfplan_results.json")
                # If tfplan.json exists, scan it directly; otherwise scan the dir
                scan_target = tfplan_json if os.path.exists(tfplan_json) else tfplan_dir
                tfplan_cmd = [trivy, "config", "--format", "json", "--output", tfplan_report, scan_target]
                if options and options.get("severity"):
                    tfplan_cmd.insert(3, "--severity")
                    tfplan_cmd.insert(4, options["severity"])
                try:
                    subprocess.run(tfplan_cmd, capture_output=True, text=True, timeout=120)
                    tp_passed, tp_failed, tp_findings = self._parse_stack_results(tfplan_report)
                    passed += tp_passed
                    failed += tp_failed
                    # Deduplicate findings by ID+resource (same check may fire on both .tf and plan)
                    existing_ids = {f["id"] + f.get("resource", "") for f in findings}
                    for f in tp_findings:
                        if f["id"] + f.get("resource", "") not in existing_ids:
                            findings.append(f)
                except (subprocess.TimeoutExpired, Exception) as e:
                    self.logger.warning(f"Trivy tfplan scan failed for {stack_name}: {e}")

            total_passed += passed
            total_failed += failed
            all_findings.extend(findings)
            detailed[stack_name] = {
                "passed": passed,
                "failed": failed,
                "skipped": 0,
                "error": 0,
                "total": passed + failed,
                "report_path": json_report,
                "findings": findings,
            }

        self.ui.show_success()

        # Generate HTML reports (per-stack + index)
        self._generate_html_reports(report_dir, detailed)

        return {
            "status": "COMPLETE",
            "report_path": report_dir,
            "report_data": {
                "passed_count": total_passed,
                "failed_count": total_failed,
                "skipped_count": 0,
                "error_count": 0,
                "warning_count": 0,
            },
            "detailed_reports": detailed,
            "issues_count": total_failed,
            "findings": all_findings,
        }

    def _find_stacks(self, directory: str) -> List[str]:
        """Find directories with .tf files, excluding internal dirs.
        
        Returns a list of stack dirs. tfplan/ dirs are NOT separate stacks — 
        they'll be scanned and merged into their corresponding stack in the scan loop.
        """
        stacks = []
        exclude = {".terraform", ".git", "node_modules", ".terragrunt-cache", "Reports", "cdk.out"}

        for dirpath, dirnames, filenames in os.walk(directory):
            dirnames[:] = [d for d in dirnames if d not in exclude]
            # Skip tfplan directories (handled separately via _find_tfplan_for_stack)
            if "tfplan" in dirpath.split(os.sep):
                continue
            if any(f.endswith(".tf") for f in filenames):
                stacks.append(dirpath)

        return stacks

    def _find_tfplan_for_stack(self, abs_dir: str, stack_dir: str) -> Optional[str]:
        """Find the corresponding tfplan directory for a stack, if it exists.
        
        Pattern: stacks/foundation/network/vpc → stacks/tfplan/foundation/network/vpc
        """
        rel = os.path.relpath(stack_dir, abs_dir)
        parts = rel.split(os.sep)
        
        # Insert 'tfplan' after the first directory (e.g., stacks/ → stacks/tfplan/)
        if len(parts) >= 2:
            tfplan_parts = [parts[0], "tfplan"] + parts[1:]
            tfplan_dir = os.path.join(abs_dir, *tfplan_parts)
            if os.path.isdir(tfplan_dir) and (
                os.path.exists(os.path.join(tfplan_dir, "tfplan.json"))
                or any(f.endswith(".tf") for f in os.listdir(tfplan_dir))
            ):
                return tfplan_dir
        
        return None

    def _parse_stack_results(self, json_path: str):
        """Parse Trivy JSON for a single stack. Returns (passed, failed, findings)."""
        if not os.path.exists(json_path):
            return 0, 0, []
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return 0, 0, []

        passed = 0
        failed = 0
        findings = []

        for result in data.get("Results", []):
            target = result.get("Target", "")
            # Read pass/fail summary (Trivy reports successes at result level)
            summary = result.get("MisconfSummary", {})
            passed += summary.get("Successes", 0)
            failed += summary.get("Failures", 0)
            # Extract individual failure details
            for misconf in result.get("Misconfigurations", []):
                if misconf.get("Status") == "PASS":
                    continue
                severity = (misconf.get("Severity") or "MEDIUM").upper()
                cause = misconf.get("CauseMetadata", {})
                findings.append({
                    "id": misconf.get("AVDID") or misconf.get("ID", ""),
                    "severity": severity,
                    "title": misconf.get("Title", ""),
                    "resource": cause.get("Resource", ""),
                    "file": cause.get("Filename", target),
                    "line": cause.get("StartLine", 0),
                })

        return passed, failed, findings

    def _generate_html_reports(self, report_dir: str, detailed: Dict) -> None:
        """Generate per-stack HTML reports and an index page for Trivy results."""
        html_dir = os.path.join(report_dir, "html_reports")
        os.makedirs(html_dir, exist_ok=True)

        stack_reports = []

        for stack_name, data in detailed.items():
            html_file = os.path.join(html_dir, f"report_{stack_name}.html")
            findings = data.get("findings", [])
            passed = data.get("passed", 0)
            failed = data.get("failed", 0)
            total = passed + failed

            html = self._render_stack_html(stack_name, passed, failed, findings)
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html)

            stack_reports.append({
                "name": stack_name,
                "file": f"report_{stack_name}.html",
                "passed": passed,
                "failed": failed,
                "total": total,
                "rate": round(passed / total * 100, 1) if total > 0 else 100.0,
            })

        # Generate index
        index_html = self._render_index_html(stack_reports)
        with open(os.path.join(html_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(index_html)

    def _render_stack_html(self, stack_name: str, passed: int, failed: int, findings: List[Dict]) -> str:
        """Render a single stack HTML report using ThothCTL unified style."""
        total = passed + failed
        rate = round(passed / total * 100, 1) if total > 0 else 100.0

        rows = ""
        for f in findings:
            sev = f.get("severity", "MEDIUM")
            sev_class = sev.lower()
            rows += f"""<tr>
                <td><span class="sev {sev_class}">{sev}</span></td>
                <td><code>{f.get('id','')}</code></td>
                <td>{f.get('title','')}</td>
                <td>{f.get('file','')}:{f.get('line',0)}</td>
                <td>{f.get('resource','')}</td>
            </tr>"""

        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Trivy - {stack_name}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
body{{font-family:'Inter',sans-serif;margin:0;padding:20px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;color:#111827}}
.container{{max-width:1100px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,0.15);overflow:hidden}}
.header{{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:20px 24px}}
.header h1{{margin:0;font-size:1.3rem}} .tool-badge{{background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:12px;font-size:0.75rem;margin-left:8px}}
.content{{padding:24px}}
.cards{{display:flex;gap:12px;margin-bottom:20px}}
.card{{background:#f9fafb;padding:16px;border-radius:8px;text-align:center;flex:1}}
.card .val{{font-size:1.5rem;font-weight:700}} .card .lbl{{font-size:0.7rem;color:#6b7280;text-transform:uppercase}}
.val.pass{{color:#10b981}} .val.fail{{color:#ef4444}} .val.rate{{color:#667eea}}
table{{width:100%;border-collapse:collapse;font-size:0.83rem}}
th{{background:#f3f4f6;padding:10px 12px;text-align:left;font-size:0.75rem;text-transform:uppercase;color:#6b7280}}
td{{padding:8px 12px;border-top:1px solid #e5e7eb}}
tr:hover{{background:#f9fafb}}
.sev{{padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600}}
.sev.critical{{background:#fef2f2;color:#dc2626}} .sev.high{{background:#fef2f2;color:#ef4444}}
.sev.medium{{background:#fffbeb;color:#b45309}} .sev.low{{background:#fefce8;color:#92400e}}
a{{color:#667eea}} code{{background:#f3f4f6;padding:2px 4px;border-radius:3px;font-size:0.8rem}}
.footer{{padding:16px 24px;background:#f9fafb;font-size:0.75rem;color:#9ca3af;text-align:center}}
@media print{{body{{background:white;padding:0}} .container{{box-shadow:none}}}}
</style></head><body>
<div class="container">
<div class="header"><h1>🛡️ Security Scan<span class="tool-badge">Trivy</span></h1><p>{stack_name.replace('_','/')}</p></div>
<div class="content">
<div class="cards">
<div class="card"><div class="val">{total}</div><div class="lbl">Total</div></div>
<div class="card"><div class="val pass">{passed}</div><div class="lbl">Passed</div></div>
<div class="card"><div class="val fail">{failed}</div><div class="lbl">Failed</div></div>
<div class="card"><div class="val rate">{rate}%</div><div class="lbl">Success Rate</div></div>
</div>
{'<table><thead><tr><th>Severity</th><th>Rule</th><th>Title</th><th>File</th><th>Resource</th></tr></thead><tbody>' + rows + '</tbody></table>' if findings else '<p style="color:#10b981;font-weight:600">✅ No misconfigurations found</p>'}
</div>
<div class="footer"><a href="index.html">← Back to index</a> | Generated by ThothCTL</div>
</div></body></html>"""

    def _render_index_html(self, stack_reports: List[Dict]) -> str:
        """Render the index HTML page using ThothCTL unified style."""
        total_stacks = len(stack_reports)
        total_passed = sum(s["passed"] for s in stack_reports)
        total_failed = sum(s["failed"] for s in stack_reports)
        total_all = total_passed + total_failed
        overall_rate = round(total_passed / total_all * 100, 1) if total_all > 0 else 100.0

        rows = ""
        for s in sorted(stack_reports, key=lambda x: x["failed"], reverse=True):
            status = "✅" if s["failed"] == 0 else "❌"
            rows += f"""<tr>
                <td><a href="{s['file']}">{s['name'].replace('_','/')}</a></td>
                <td>{s['total']}</td><td>{s['passed']}</td><td>{s['failed']}</td>
                <td>{s['rate']}%</td><td>{status}</td></tr>"""

        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Trivy Scan Results</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
body{{font-family:'Inter',sans-serif;margin:0;padding:20px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;color:#111827}}
.container{{max-width:1100px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,0.15);overflow:hidden}}
.header{{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:24px}} 
.header h1{{margin:0;font-size:1.5rem}} .header p{{margin:5px 0 0;opacity:0.9;font-size:0.85rem}}
.tool-badge{{background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:12px;font-size:0.75rem;margin-left:8px}}
.content{{padding:24px}}
.summary{{display:flex;gap:12px;margin-bottom:20px}}
.card{{background:#f9fafb;padding:16px;border-radius:8px;text-align:center;flex:1}}
.card .val{{font-size:1.5rem;font-weight:700}} .card .lbl{{font-size:0.7rem;color:#6b7280;text-transform:uppercase}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
th{{background:#f3f4f6;padding:10px 12px;text-align:left;font-size:0.75rem;text-transform:uppercase;color:#6b7280}}
td{{padding:8px 12px;border-top:1px solid #e5e7eb}} a{{color:#667eea}}
tr:hover{{background:#f9fafb}}
.footer{{padding:16px 24px;background:#f9fafb;font-size:0.75rem;color:#9ca3af;text-align:center}}
@media print{{body{{background:white;padding:0}} .container{{box-shadow:none}}}}
</style></head><body>
<div class="container">
<div class="header"><h1>🛡️ Security Scan Results<span class="tool-badge">Trivy</span></h1><p>{total_stacks} stacks scanned — {datetime.now().strftime('%Y-%m-%d %H:%M')}</p></div>
<div class="content">
<div class="summary">
<div class="card"><div class="val">{total_stacks}</div><div class="lbl">Stacks</div></div>
<div class="card"><div class="val" style="color:#10b981">{total_passed}</div><div class="lbl">Passed</div></div>
<div class="card"><div class="val" style="color:#ef4444">{total_failed}</div><div class="lbl">Failed</div></div>
<div class="card"><div class="val" style="color:#667eea">{overall_rate}%</div><div class="lbl">Success Rate</div></div>
</div>
<table><thead><tr><th>Stack</th><th>Total</th><th>Passed</th><th>Failed</th><th>Rate</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>
<div class="footer">Generated by ThothCTL</div>
</div></body></html>"""
