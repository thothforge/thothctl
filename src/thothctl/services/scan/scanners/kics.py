"""KICS scanner implementation using Docker."""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

from ....core.cli_ui import ScannerUI
from .scanners import ScannerPort


class KICSScanner(ScannerPort):
    """KICS scanner using Docker container."""
    
    def __init__(self):
        self.ui = ScannerUI("KICS")
        self.logger = logging.getLogger(__name__)
        self.docker_image = "checkmarx/kics:latest"

    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def scan(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        tftool: str = "tofu",
    ) -> Dict[str, str]:
        """
        Execute KICS scan using Docker.
        
        Note: Requires Docker to be installed and running.
        """
        try:
            # Check Docker availability
            if not self._check_docker():
                error_msg = (
                    "Docker is required to run KICS scanner. "
                    "Please install Docker: https://docs.docker.com/get-docker/"
                )
                self.ui.show_error(error_msg)
                raise RuntimeError(error_msg)

            self.logger.info(f"Starting KICS scan in directory: {directory}")
            self.ui.show_info(f"Starting KICS scan in directory: {directory}")

            # Convert to absolute paths
            abs_directory = str(Path(directory).resolve())
            abs_reports_dir = str(Path(reports_dir).resolve())
            
            # Create reports directory
            os.makedirs(abs_reports_dir, exist_ok=True)

            # Prepare output files — Docker mounts abs_reports_dir as /output
            json_output = os.path.join(abs_reports_dir, "kics-results.json")
            sarif_output = os.path.join(abs_reports_dir, "kics-results.sarif")
            
            # Build Docker command
            docker_cmd = [
                "docker", "run", "--rm",
                "-v", f"{abs_directory}:/path",
                "-v", f"{abs_reports_dir}:/output",
                self.docker_image,
                "scan",
                "-p", "/path",
                "-o", "/output",
                "--report-formats", "json,sarif",
                "--output-name", "kics-results"
            ]

            # Add optional parameters
            if options:
                if options.get("exclude_paths"):
                    for exclude in options["exclude_paths"]:
                        docker_cmd.extend(["--exclude-paths", exclude])
                
                if options.get("exclude_queries"):
                    docker_cmd.extend(["--exclude-queries", options["exclude_queries"]])
                
                if options.get("include_queries"):
                    docker_cmd.extend(["--include-queries", options["include_queries"]])

            self.logger.debug(f"Running Docker command: {' '.join(docker_cmd)}")
            self.ui.show_info("Running KICS scan via Docker...")

            # Execute scan
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=600
            )

            # KICS exit codes: 0=no issues, 20=info, 30=low, 40=medium, 50=high, 60=critical
            if result.returncode in [0, 20, 30, 40, 50, 60]:
                self.ui.show_success("KICS scan completed")
                
                # Parse results
                report_data, findings = self._parse_kics_results(json_output)
                
                self.ui.show_info(f"Found {report_data.get('failed_count', 0)} issues")

                # Generate HTML reports (unified style)
                kics_report_dir = os.path.join(abs_reports_dir, "kics")
                os.makedirs(kics_report_dir, exist_ok=True)
                self._generate_html_report(kics_report_dir, report_data, findings)
                
                return {
                    "status": "COMPLETE",
                    "report_path": kics_report_dir,
                    "report_data": report_data,
                    "findings": findings,
                    "issues_count": report_data.get("failed_count", 0),
                }
            else:
                error_msg = f"KICS scan failed with exit code {result.returncode}"
                self.logger.error(f"{error_msg}\nStderr: {result.stderr}")
                self.ui.show_error(error_msg)
                return {
                    "status": "error",
                    "error": error_msg,
                    "stderr": result.stderr
                }

        except subprocess.TimeoutExpired:
            error_msg = "KICS scan timed out after 10 minutes"
            self.logger.error(error_msg)
            self.ui.show_error(error_msg)
            return {"status": "error", "error": error_msg}
        
        except Exception as e:
            error_msg = f"KICS scan failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui.show_error(error_msg)
            return {"status": "FAIL", "error": error_msg}

    def _parse_kics_results(self, json_path: str):
        """Parse KICS JSON results into report_data and findings list."""
        empty_data = {"passed_count": 0, "failed_count": 0, "skipped_count": 0, "error_count": 0, "warning_count": 0}
        if not os.path.exists(json_path):
            return empty_data, []

        try:
            with open(json_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return empty_data, []

        failed = data.get("total_counter", 0)
        queries_total = data.get("queries_total", 0)
        # passed = total rules checked minus rules that produced findings
        queries_with_findings = len(data.get("queries", []))
        passed = max(0, queries_total - queries_with_findings)

        findings = []
        for query in data.get("queries", []):
            severity = (query.get("severity") or "MEDIUM").upper()
            query_name = query.get("query_name", "")
            query_id = query.get("query_id", "")[:12]
            for file_entry in query.get("files", []):
                findings.append({
                    "id": query_id,
                    "severity": severity,
                    "title": query_name,
                    "resource": file_entry.get("resource_type", ""),
                    "file": file_entry.get("file_name", ""),
                    "line": file_entry.get("line", 0),
                })

        report_data = {
            "passed_count": passed,
            "failed_count": failed,
            "skipped_count": 0,
            "error_count": 0,
            "warning_count": 0,
        }

        return report_data, findings

    def _generate_html_report(self, report_dir: str, report_data: dict, findings: list) -> None:
        """Generate HTML report in unified ThothCTL style."""
        from datetime import datetime

        html_dir = os.path.join(report_dir, "html_reports")
        os.makedirs(html_dir, exist_ok=True)

        passed = report_data.get("passed_count", 0)
        failed = report_data.get("failed_count", 0)
        total = passed + failed
        rate = round(passed / total * 100, 1) if total > 0 else 100.0

        # Group findings by severity
        sev_groups = {}
        for f in findings:
            sev = f.get("severity", "MEDIUM")
            sev_groups.setdefault(sev, []).append(f)

        rows = ""
        for f in findings:
            sev = f.get("severity", "MEDIUM").lower()
            rows += f"""<tr>
                <td><span class="sev {sev}">{f.get('severity','')}</span></td>
                <td><code>{f.get('id','')}</code></td>
                <td>{f.get('title','')}</td>
                <td>{f.get('file','')}:{f.get('line',0)}</td>
                <td>{f.get('resource','')}</td>
            </tr>"""

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>KICS Scan Results</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
body{{font-family:'Inter',sans-serif;margin:0;padding:20px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;color:#111827}}
.container{{max-width:1100px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,0.15);overflow:hidden}}
.header{{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:24px}}
.header h1{{margin:0;font-size:1.5rem}} .header p{{margin:5px 0 0;opacity:0.9;font-size:0.85rem}}
.tool-badge{{background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:12px;font-size:0.75rem;margin-left:8px}}
.content{{padding:24px}}
.cards{{display:flex;gap:12px;margin-bottom:20px}}
.card{{background:#f9fafb;padding:16px;border-radius:8px;text-align:center;flex:1}}
.card .val{{font-size:1.5rem;font-weight:700}} .card .lbl{{font-size:0.7rem;color:#6b7280;text-transform:uppercase}}
table{{width:100%;border-collapse:collapse;font-size:0.83rem}}
th{{background:#f3f4f6;padding:10px 12px;text-align:left;font-size:0.75rem;text-transform:uppercase;color:#6b7280}}
td{{padding:8px 12px;border-top:1px solid #e5e7eb}} tr:hover{{background:#f9fafb}}
.sev{{padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600}}
.sev.critical{{background:#fef2f2;color:#dc2626}} .sev.high{{background:#fef2f2;color:#ef4444}}
.sev.medium{{background:#fffbeb;color:#b45309}} .sev.low{{background:#fefce8;color:#92400e}} .sev.info{{background:#eff6ff;color:#3b82f6}}
code{{background:#f3f4f6;padding:2px 4px;border-radius:3px;font-size:0.8rem}}
.footer{{padding:16px 24px;background:#f9fafb;font-size:0.75rem;color:#9ca3af;text-align:center}}
@media print{{body{{background:white;padding:0}} .container{{box-shadow:none}}}}
</style></head><body>
<div class="container">
<div class="header"><h1>🛡️ Security Scan Results<span class="tool-badge">KICS</span></h1>
<p>Scanned {datetime.now().strftime('%Y-%m-%d %H:%M')} — {failed} issues found</p></div>
<div class="content">
<div class="cards">
<div class="card"><div class="val">{total}</div><div class="lbl">Total Checks</div></div>
<div class="card"><div class="val" style="color:#10b981">{passed}</div><div class="lbl">Passed</div></div>
<div class="card"><div class="val" style="color:#ef4444">{failed}</div><div class="lbl">Failed</div></div>
<div class="card"><div class="val" style="color:#667eea">{rate}%</div><div class="lbl">Success Rate</div></div>
</div>
{'<table><thead><tr><th>Severity</th><th>Rule</th><th>Title</th><th>File</th><th>Resource</th></tr></thead><tbody>' + rows + '</tbody></table>' if findings else '<p style="color:#10b981;font-weight:600">✅ No misconfigurations found</p>'}
</div>
<div class="footer">Generated by ThothCTL</div>
</div></body></html>"""

        with open(os.path.join(html_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
