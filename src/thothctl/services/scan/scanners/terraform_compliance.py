"""Terraform-compliance scanner — BDD-style compliance testing against tfplan.json."""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from ....core.cli_ui import ScannerUI
from ....utils.platform_utils import find_executable
from .scanners import ScannerPort


class TerraformComplianceScanner(ScannerPort):
    """Terraform-compliance BDD scanner. Requires .feature files and tfplan.json."""

    def __init__(self):
        self.ui = ScannerUI("Terraform-compliance")
        self.logger = logging.getLogger(__name__)

    def scan(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        tftool: str = "tofu",
    ) -> Dict[str, str]:
        """Execute terraform-compliance scan per-stack."""
        tc = find_executable("terraform-compliance")
        if not tc:
            raise FileNotFoundError(
                "terraform-compliance not found. Install: pip install terraform-compliance"
            )

        options = options or {}
        abs_dir = os.path.abspath(directory)
        report_dir = os.path.join(os.path.abspath(reports_dir), "terraform-compliance")
        os.makedirs(report_dir, exist_ok=True)

        # Resolve features directory
        features_dir = self._resolve_features_dir(abs_dir, options.get("features_dir", "features"))
        if not features_dir:
            self.ui.show_warning("No features directory found. Skipping terraform-compliance.")
            return {"status": "SKIPPED", "error": "No features directory found"}

        # Find tfplan.json files
        plan_files = self._find_plan_files(abs_dir)
        if not plan_files:
            self.ui.show_warning("No tfplan.json files found. terraform-compliance requires plan files.")
            return {"status": "SKIPPED", "error": "No tfplan.json files found"}

        self.ui.start_scan_message(f"{directory} ({len(plan_files)} plans)")

        total_passed = total_failed = total_skipped = 0
        all_findings: List[Dict] = []
        detailed = {}

        for plan_file in plan_files:
            stack_rel = os.path.relpath(os.path.dirname(plan_file), abs_dir)
            stack_name = stack_rel.replace(os.sep, "_") if stack_rel != "." else "root"
            stack_report_dir = os.path.join(report_dir, f"report_{stack_name}")
            os.makedirs(stack_report_dir, exist_ok=True)

            junit_path = os.path.join(stack_report_dir, "results_junitxml.xml")

            cmd = [
                tc,
                "-f", features_dir,
                "-p", plan_file,
                "--junitxml", junit_path,
                "--no-ansi",
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            except (subprocess.TimeoutExpired, Exception) as e:
                self.logger.warning(f"terraform-compliance failed for {stack_name}: {e}")
                continue

            # Parse JUnit XML results
            from ..report_parser import parse_junit_xml
            counts = parse_junit_xml(junit_path)
            passed = counts["passed"]
            failed = counts["failed"]
            skipped = counts["skipped"]
            errors = counts["errors"]

            total_passed += passed
            total_failed += failed + errors
            total_skipped += skipped

            # Extract findings from failures
            findings = self._extract_findings(junit_path, stack_name)
            all_findings.extend(findings)

            detailed[stack_name] = {
                "passed": passed,
                "failed": failed + errors,
                "skipped": skipped,
                "error": 0,
                "total": passed + failed + errors + skipped,
                "report_path": junit_path,
                "findings": findings,
            }

        self.ui.show_success()

        # Generate HTML reports
        self._generate_html_reports(report_dir, detailed)

        return {
            "status": "COMPLETE",
            "report_path": report_dir,
            "report_data": {
                "passed_count": total_passed,
                "failed_count": total_failed,
                "skipped_count": total_skipped,
                "error_count": 0,
                "warning_count": 0,
            },
            "detailed_reports": detailed,
            "issues_count": total_failed,
            "findings": all_findings,
        }

    def _resolve_features_dir(self, base_dir: str, features_dir: str) -> Optional[str]:
        """Resolve features directory.
        
        terraform-compliance natively supports:
        - Local paths
        - Git URLs via git: prefix (e.g., git:https://github.com/org/repo.git)
        
        Resolution:
        1. If starts with git: — pass through directly (native support)
        2. If Git URL without prefix — add git: prefix for native support
        3. Relative to project
        4. Absolute path
        5. THOTH_ORG_POLICY/compliance/features/
        """
        # 1-2. Git URLs — terraform-compliance handles them natively
        if features_dir.startswith("git:"):
            return features_dir
        if features_dir.startswith(("https://", "git@", "ssh://")):
            return f"git:{features_dir}"

        # 3. Relative to project
        candidate = os.path.join(base_dir, features_dir)
        if os.path.isdir(candidate):
            return candidate

        # 4. Absolute path
        if os.path.isabs(features_dir) and os.path.isdir(features_dir):
            return features_dir

        # 5. THOTH_ORG_POLICY repo — look for compliance/features/
        org_policy_url = os.environ.get("THOTH_ORG_POLICY")
        if org_policy_url:
            from ....services.check.org_policy_loader import get_org_policy_path
            org_path = get_org_policy_path(org_policy_url)
            if org_path:
                for subdir in ["compliance/features", "features", "compliance"]:
                    candidate = os.path.join(org_path, subdir)
                    if os.path.isdir(candidate):
                        return candidate

        return None

    def _find_plan_files(self, directory: str) -> List[str]:
        """Find tfplan.json files recursively."""
        plans = []
        exclude = {".terraform", ".git", "node_modules", "Reports"}
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in exclude]
            if "tfplan.json" in files:
                plans.append(os.path.join(root, "tfplan.json"))
        return plans

    def _extract_findings(self, junit_path: str, stack_name: str) -> List[Dict]:
        """Extract findings from JUnit XML failures."""
        import xml.etree.ElementTree as ET
        findings = []
        if not os.path.exists(junit_path):
            return findings
        try:
            tree = ET.parse(junit_path)
            root = tree.getroot()
            for tc in root.findall(".//testcase"):
                failure = tc.find("failure")
                if failure is not None:
                    findings.append({
                        "id": tc.get("classname", "")[:30],
                        "severity": "HIGH",
                        "title": tc.get("name", ""),
                        "resource": stack_name,
                        "file": "tfplan.json",
                        "line": 0,
                    })
        except Exception:
            pass
        return findings

    def _generate_html_reports(self, report_dir: str, detailed: Dict) -> None:
        """Generate per-stack HTML reports in unified ThothCTL style."""
        from datetime import datetime

        html_dir = os.path.join(report_dir, "html_reports")
        os.makedirs(html_dir, exist_ok=True)

        stack_reports = []
        for stack_name, data in detailed.items():
            passed = data.get("passed", 0)
            failed = data.get("failed", 0)
            total = passed + failed + data.get("skipped", 0)
            rate = round(passed / total * 100, 1) if total > 0 else 100.0

            findings = data.get("findings", [])
            rows = "".join(
                f'<tr><td><span class="sev high">HIGH</span></td><td>{f["title"]}</td><td>{f["resource"]}</td></tr>'
                for f in findings
            )

            html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Terraform-compliance - {stack_name}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
body{{font-family:'Inter',sans-serif;margin:0;padding:20px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;color:#111827}}
.container{{max-width:1100px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,0.15);overflow:hidden}}
.header{{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:24px}}
.header h1{{margin:0;font-size:1.3rem}} .tool-badge{{background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:12px;font-size:0.75rem;margin-left:8px}}
.content{{padding:24px}}
.cards{{display:flex;gap:12px;margin-bottom:20px}}
.card{{background:#f9fafb;padding:16px;border-radius:8px;text-align:center;flex:1}}
.card .val{{font-size:1.5rem;font-weight:700}} .card .lbl{{font-size:0.7rem;color:#6b7280;text-transform:uppercase}}
table{{width:100%;border-collapse:collapse;font-size:0.83rem}}
th{{background:#f3f4f6;padding:10px 12px;text-align:left;font-size:0.75rem;text-transform:uppercase;color:#6b7280}}
td{{padding:8px 12px;border-top:1px solid #e5e7eb}} tr:hover{{background:#f9fafb}}
.sev{{padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600}}
.sev.high{{background:#fef2f2;color:#ef4444}}
.footer{{padding:16px 24px;background:#f9fafb;font-size:0.75rem;color:#9ca3af;text-align:center}}
</style></head><body>
<div class="container">
<div class="header"><h1>🛡️ Security Scan<span class="tool-badge">Terraform-compliance</span></h1><p>{stack_name.replace('_','/')}</p></div>
<div class="content">
<div class="cards">
<div class="card"><div class="val">{total}</div><div class="lbl">Total</div></div>
<div class="card"><div class="val" style="color:#10b981">{passed}</div><div class="lbl">Passed</div></div>
<div class="card"><div class="val" style="color:#ef4444">{failed}</div><div class="lbl">Failed</div></div>
<div class="card"><div class="val" style="color:#667eea">{rate}%</div><div class="lbl">Success Rate</div></div>
</div>
{'<table><thead><tr><th>Severity</th><th>Scenario</th><th>Stack</th></tr></thead><tbody>' + rows + '</tbody></table>' if findings else '<p style="color:#10b981;font-weight:600">✅ All compliance scenarios passed</p>'}
</div>
<div class="footer"><a href="index.html">← Back to index</a> | Generated by ThothCTL</div>
</div></body></html>"""

            report_file = f"report_{stack_name}.html"
            with open(os.path.join(html_dir, report_file), "w", encoding="utf-8") as f:
                f.write(html)
            stack_reports.append({"name": stack_name, "file": report_file, "passed": passed, "failed": failed, "total": total, "rate": rate})

        # Index page
        total_stacks = len(stack_reports)
        tp = sum(s["passed"] for s in stack_reports)
        tf = sum(s["failed"] for s in stack_reports)
        ta = tp + tf
        overall_rate = round(tp / ta * 100, 1) if ta > 0 else 100.0
        rows = "".join(
            f'<tr><td><a href="{s["file"]}">{s["name"].replace("_","/")}</a></td><td>{s["total"]}</td><td>{s["passed"]}</td><td>{s["failed"]}</td><td>{s["rate"]}%</td><td>{"✅" if s["failed"]==0 else "❌"}</td></tr>'
            for s in sorted(stack_reports, key=lambda x: x["failed"], reverse=True)
        )
        index_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Terraform-compliance Results</title>
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
td{{padding:8px 12px;border-top:1px solid #e5e7eb}} a{{color:#667eea}} tr:hover{{background:#f9fafb}}
.footer{{padding:16px 24px;background:#f9fafb;font-size:0.75rem;color:#9ca3af;text-align:center}}
</style></head><body>
<div class="container">
<div class="header"><h1>🛡️ Security Scan Results<span class="tool-badge">Terraform-compliance</span></h1><p>{total_stacks} plans evaluated — {datetime.now().strftime('%Y-%m-%d %H:%M')}</p></div>
<div class="content">
<div class="summary">
<div class="card"><div class="val">{total_stacks}</div><div class="lbl">Plans</div></div>
<div class="card"><div class="val" style="color:#10b981">{tp}</div><div class="lbl">Passed</div></div>
<div class="card"><div class="val" style="color:#ef4444">{tf}</div><div class="lbl">Failed</div></div>
<div class="card"><div class="val" style="color:#667eea">{overall_rate}%</div><div class="lbl">Success Rate</div></div>
</div>
<table><thead><tr><th>Plan</th><th>Total</th><th>Passed</th><th>Failed</th><th>Rate</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>
<div class="footer">Generated by ThothCTL</div>
</div></body></html>"""
        with open(os.path.join(html_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(index_html)
