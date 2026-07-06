"""OPA/Conftest scanner for IaC policy evaluation.

Supports two modes:
- conftest: Static analysis of .tf/.yaml files using Rego policies (default)
- opa: Plan-based evaluation using `opa exec` against tfplan.json files

Both modes use the same Rego policy language and can share policies.

Data files (params.yaml / params.json) in the policy directory are automatically
loaded into OPA's data namespace, enabling externalized policy parameters.
YAML files are converted to JSON at scan time for OPA compatibility.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from ....core.cli_ui import ScannerUI
from ....utils.platform_utils import find_executable
from .scanners import ScannerPort


class OPAScanner(ScannerPort):
    """OPA/Conftest scanner supporting both static HCL and plan-based evaluation."""

    def __init__(self):
        self.ui = ScannerUI("OPA")
        self.logger = logging.getLogger(__name__)
        self.reports_path = "security-scan"

    def scan(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        tftool: str = "tofu",
    ) -> Dict[str, str]:
        """Execute OPA scan. Delegates to conftest or opa exec based on options.

        Options:
            mode: "conftest" (default) or "opa"
            policy_dir: path to Rego policies (default: "policy")
            decision: OPA decision path (opa mode only)
            namespace: Rego namespace (conftest mode only)
            data_dir: additional data directory (conftest mode only)
        """
        options = options or {}
        mode = options.get("mode", "conftest")
        policy_dir = options.get("policy_dir", "policy")

        if mode == "opa":
            return self._scan_with_opa(directory, reports_dir, policy_dir, options)
        return self._scan_with_conftest(directory, reports_dir, policy_dir, options)

    # ── Conftest mode ──────────────────────────────────────────────────

    def _prepare_data_files(self, policy_dir: str) -> None:
        """Convert YAML data files to JSON in the policy directory.

        OPA/Conftest natively load .json files into the data namespace but not YAML.
        This method finds *.yaml/*.yml data files (excluding .rego test data) in the
        policy directory and generates corresponding .json files so that Rego policies
        can reference them via data.<filename>.<key>.

        This enables teams to manage policy parameters in human-readable YAML while
        keeping OPA compatibility transparent.
        """
        policy_path = Path(policy_dir)
        if not policy_path.is_dir():
            return

        yaml_files = list(policy_path.glob("*.yaml")) + list(policy_path.glob("*.yml"))

        # Filter: only convert files that look like data/param files
        # (skip files that are test fixtures, conftest config, etc.)
        skip_prefixes = ("conftest", "opa", ".")
        data_files = [
            f for f in yaml_files
            if not f.name.startswith(skip_prefixes)
        ]

        if not data_files:
            return

        try:
            import yaml
        except ImportError:
            self.logger.warning(
                "PyYAML not installed — cannot convert YAML data files to JSON. "
                "Install with: pip install pyyaml"
            )
            return

        for yaml_file in data_files:
            json_file = yaml_file.with_suffix(".json")
            # Only regenerate if YAML is newer than JSON (or JSON doesn't exist)
            if json_file.exists() and json_file.stat().st_mtime >= yaml_file.stat().st_mtime:
                continue
            try:
                with open(yaml_file, "r", encoding="utf-8") as yf:
                    data = yaml.safe_load(yf)
                with open(json_file, "w", encoding="utf-8") as jf:
                    json.dump(data, jf, indent=2, ensure_ascii=False)
                self.logger.info(f"Converted {yaml_file.name} → {json_file.name}")
                self.ui.show_info(f"📄 Data file: {yaml_file.name} → {json_file.name}")
            except Exception as e:
                self.logger.warning(f"Failed to convert {yaml_file}: {e}")

    def _scan_with_conftest(
        self, directory: str, reports_dir: str, policy_dir: str, options: Dict
    ) -> Dict[str, str]:
        """Static HCL/YAML analysis via conftest."""
        conftest = find_executable("conftest")
        if not conftest:
            raise FileNotFoundError(
                "conftest not found in PATH. "
                "Install: https://www.conftest.dev/install/"
            )

        abs_dir = os.path.abspath(directory)
        abs_policy = self._resolve_policy_dir(abs_dir, policy_dir)

        if not abs_policy:
            self.ui.show_warning(
                f"No policy directory found at '{policy_dir}'. "
                "Skipping OPA/Conftest scan."
            )
            return {"status": "SKIPPED", "error": "No policy directory found"}

        # Convert YAML data files to JSON for OPA data namespace
        self._prepare_data_files(abs_policy)

        # Collect scannable files
        scan_files = self._find_scannable_files(abs_dir)
        if not scan_files:
            self.ui.show_warning(f"No scannable files found in {abs_dir}")
            return {"status": "SKIPPED", "error": "No scannable files"}

        # Prepare reports directory
        report_dir = self._prepare_reports_dir(reports_dir)
        json_report = os.path.join(report_dir, "conftest_results.json")
        junit_report = os.path.join(report_dir, "results_junitxml.xml")

        # Run conftest with JSON output for parsing
        cmd_json = [
            conftest, "test",
            "--policy", abs_policy,
            "--output", "json",
            "--all-namespaces",
        ]
        # Add namespace if specified
        if options.get("namespace"):
            cmd_json = [
                conftest, "test",
                "--policy", abs_policy,
                "--output", "json",
                "--namespace", options["namespace"],
            ]
        # Add data files if specified (explicit option)
        if options.get("data_dir"):
            cmd_json.extend(["--data", options["data_dir"]])

        # Auto-detect JSON data files in the policy directory
        # conftest requires explicit --data to load JSON into data namespace
        policy_data_files = list(Path(abs_policy).glob("*.json"))
        for data_file in policy_data_files:
            cmd_json.extend(["--data", str(data_file)])

        cmd_json.extend(scan_files)

        self.ui.start_scan_message(abs_dir)
        self.logger.info(f"Running conftest: {' '.join(cmd_json)}")

        try:
            result_json = subprocess.run(
                cmd_json,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=abs_dir,
            )

            # Save raw JSON report
            with open(json_report, "w") as f:
                f.write(result_json.stdout or "[]")

            # Run again with JUnit output for the HTML report pipeline
            cmd_junit = cmd_json.copy()
            cmd_junit[cmd_junit.index("json")] = "junit"

            result_junit = subprocess.run(
                cmd_junit,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=abs_dir,
            )

            with open(junit_report, "w") as f:
                f.write(result_junit.stdout or "")

            # Parse JSON results
            report_data, findings = self._parse_conftest_json(result_json.stdout)

            # Generate HTML report (unified style)
            self._generate_html_report(report_dir, report_data, findings, "Conftest")

            # conftest exit codes: 0=pass, 1=failure/violation, 2=error
            if result_json.returncode == 2:
                self.ui.show_error(
                    f"Conftest error: {result_json.stderr}"
                )
                return {
                    "status": "FAIL",
                    "error": result_json.stderr,
                    "report_path": report_dir,
                    "report_data": report_data,
                    "findings": findings,
                }

            self.ui.show_success()
            return {
                "status": "COMPLETE",
                "report_path": report_dir,
                "report_data": report_data,
                "findings": findings,
                "issues_count": report_data.get("failed_count", 0),
            }

        except subprocess.TimeoutExpired:
            self.ui.show_error("Conftest scan timed out after 300 seconds")
            return {"status": "TIMEOUT", "error": "Scan timed out"}
        except Exception as e:
            self.logger.error(f"Conftest scan failed: {e}", exc_info=True)
            self.ui.show_error(f"Conftest scan failed: {e}")
            return {"status": "FAIL", "error": str(e)}

    # ── OPA exec mode ──────────────────────────────────────────────────

    def _scan_with_opa(
        self, directory: str, reports_dir: str, policy_dir: str, options: Dict
    ) -> Dict[str, str]:
        """Plan-based evaluation via opa exec against tfplan.json."""
        opa = find_executable("opa")
        if not opa:
            raise FileNotFoundError(
                "opa not found in PATH. "
                "Install: https://www.openpolicyagent.org/docs/latest/#running-opa"
            )

        abs_dir = os.path.abspath(directory)
        abs_policy = self._resolve_policy_dir(abs_dir, policy_dir)

        if not abs_policy:
            self.ui.show_warning(
                f"No policy directory found at '{policy_dir}'. "
                "Skipping OPA scan."
            )
            return {"status": "SKIPPED", "error": "No policy directory found"}

        # Convert YAML data files to JSON for OPA data namespace
        self._prepare_data_files(abs_policy)

        # Find tfplan.json files
        plan_files = self._find_plan_files(abs_dir)
        if not plan_files:
            self.ui.show_warning(
                f"No tfplan.json files found in {abs_dir}. "
                "OPA mode requires plan files. Use mode=conftest for static analysis."
            )
            return {"status": "SKIPPED", "error": "No tfplan.json files found"}

        report_dir = self._prepare_reports_dir(reports_dir)
        json_report = os.path.join(report_dir, "opa_results.json")

        # Build opa exec command
        decision = options.get("decision", "terraform/analysis/authz")
        cmd = [
            opa, "exec",
            "--decision", decision,
            "--bundle", abs_policy,
        ]
        cmd.extend(plan_files)

        self.ui.start_scan_message(abs_dir)
        self.logger.info(f"Running opa exec: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=abs_dir,
            )

            # Save raw output
            with open(json_report, "w") as f:
                f.write(result.stdout or "{}")

            report_data, findings = self._parse_opa_json(result.stdout)

            if result.returncode != 0 and not result.stdout:
                self.ui.show_error(f"OPA error: {result.stderr}")
                return {
                    "status": "FAIL",
                    "error": result.stderr,
                    "report_path": report_dir,
                    "report_data": report_data,
                    "findings": findings,
                }

            # Generate HTML report (unified style)
            self._generate_html_report(report_dir, report_data, findings, "OPA")

            self.ui.show_success()
            return {
                "status": "COMPLETE",
                "report_path": report_dir,
                "report_data": report_data,
                "findings": findings,
                "issues_count": report_data.get("failed_count", 0),
            }

        except subprocess.TimeoutExpired:
            self.ui.show_error("OPA scan timed out after 300 seconds")
            return {"status": "TIMEOUT", "error": "Scan timed out"}
        except Exception as e:
            self.logger.error(f"OPA scan failed: {e}", exc_info=True)
            self.ui.show_error(f"OPA scan failed: {e}")
            return {"status": "FAIL", "error": str(e)}

    # ── Parsing ────────────────────────────────────────────────────────

    def _parse_conftest_json(self, stdout: str) -> tuple:
        """Parse conftest JSON output into report_data and findings list.

        Conftest JSON structure:
        [{"filename": "...", "successes": N,
          "failures": [{"msg": "..."}], "warnings": [{"msg": "..."}]}]

        Returns:
            Tuple of (report_data dict, findings list)
        """
        try:
            results = json.loads(stdout) if stdout else []
        except json.JSONDecodeError:
            return self._empty_report_data(), []

        passed = sum(r.get("successes", 0) for r in results)
        failed = sum(len(r.get("failures", [])) for r in results)
        warnings = sum(len(r.get("warnings", [])) for r in results)
        exceptions = sum(len(r.get("exceptions", [])) for r in results)

        # Build structured findings
        findings = []
        for r in results:
            filename = r.get("filename", "unknown")
            for failure in r.get("failures", []):
                findings.append({
                    "id": "OPA",
                    "severity": "HIGH",
                    "title": failure.get("msg", "Policy violation"),
                    "resource": failure.get("metadata", {}).get("resource", ""),
                    "file": filename,
                    "line": failure.get("metadata", {}).get("line", 0),
                    "namespace": r.get("namespace", ""),
                })
            for warning in r.get("warnings", []):
                findings.append({
                    "id": "OPA",
                    "severity": "MEDIUM",
                    "title": warning.get("msg", "Policy warning"),
                    "resource": warning.get("metadata", {}).get("resource", ""),
                    "file": filename,
                    "line": warning.get("metadata", {}).get("line", 0),
                    "namespace": r.get("namespace", ""),
                })

        report_data = {
            "passed_count": passed,
            "failed_count": failed,
            "skipped_count": exceptions,
            "error_count": 0,
            "warning_count": warnings,
        }

        return report_data, findings

    def _parse_opa_json(self, stdout: str) -> tuple:
        """Parse opa exec JSON output.

        OPA exec structure:
        {"result": [{"path": "file.json", "result": true/false/<value>}]}

        Returns:
            Tuple of (report_data dict, findings list)
        """
        try:
            data = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            return self._empty_report_data(), []

        results = data.get("result", [])
        passed = sum(1 for r in results if r.get("result") is True)
        failed = sum(1 for r in results if r.get("result") is False)
        # Results that are neither true nor false (e.g. score values)
        other = len(results) - passed - failed

        findings = []
        for r in results:
            if r.get("result") is False:
                findings.append({
                    "id": "OPA",
                    "severity": "HIGH",
                    "title": f"Policy denied: {Path(r.get('path', 'unknown')).name}",
                    "resource": "",
                    "file": r.get("path", "unknown"),
                    "line": 0,
                    "namespace": "",
                })

        report_data = {
            "passed_count": passed,
            "failed_count": failed,
            "skipped_count": other,
            "error_count": 0,
            "warning_count": 0,
        }

        return report_data, findings

    @staticmethod
    def _empty_report_data() -> Dict:
        return {
            "passed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "warning_count": 0,
        }

    def _generate_html_report(
        self, report_dir: str, report_data: Dict, findings: List[Dict], tool_name: str
    ) -> None:
        """Generate HTML report in unified ThothCTL style (matches KICS/TF-compliance)."""
        from datetime import datetime

        html_dir = os.path.join(report_dir, "html_reports")
        os.makedirs(html_dir, exist_ok=True)

        passed = report_data.get("passed_count", 0)
        failed = report_data.get("failed_count", 0)
        warnings = report_data.get("warning_count", 0)
        total = passed + failed + warnings
        rate = round(passed / total * 100, 1) if total > 0 else 100.0

        # Build findings table rows
        rows = ""
        for f in findings:
            sev = f.get("severity", "MEDIUM").lower()
            ns = f.get("namespace", "")
            ns_badge = f' <span class="ns">{ns}</span>' if ns else ""
            rows += f"""<tr>
                <td><span class="sev {sev}">{f.get('severity', '')}</span></td>
                <td><code>{f.get('id', '')}</code></td>
                <td>{f.get('title', '')}{ns_badge}</td>
                <td>{f.get('file', '')}{(':' + str(f['line'])) if f.get('line') else ''}</td>
                <td>{f.get('resource', '') or '—'}</td>
            </tr>"""

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>{tool_name} Scan Results</title>
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
.ns{{background:#eff6ff;color:#3b82f6;padding:2px 6px;border-radius:8px;font-size:0.7rem;margin-left:4px}}
.footer{{padding:16px 24px;background:#f9fafb;font-size:0.75rem;color:#9ca3af;text-align:center}}
@media print{{body{{background:white;padding:0}} .container{{box-shadow:none}}}}
</style></head><body>
<div class="container">
<div class="header"><h1>🛡️ Security Scan Results<span class="tool-badge">{tool_name}</span></h1>
<p>Scanned {datetime.now().strftime('%Y-%m-%d %H:%M')} — {failed} violation{'s' if failed != 1 else ''} found</p></div>
<div class="content">
<div class="cards">
<div class="card"><div class="val">{total}</div><div class="lbl">Total Checks</div></div>
<div class="card"><div class="val" style="color:#10b981">{passed}</div><div class="lbl">Passed</div></div>
<div class="card"><div class="val" style="color:#ef4444">{failed}</div><div class="lbl">Failed</div></div>
<div class="card"><div class="val" style="color:#f59e0b">{warnings}</div><div class="lbl">Warnings</div></div>
<div class="card"><div class="val" style="color:#667eea">{rate}%</div><div class="lbl">Success Rate</div></div>
</div>
{'<table><thead><tr><th>Severity</th><th>Rule</th><th>Policy Violation</th><th>File</th><th>Resource</th></tr></thead><tbody>' + rows + '</tbody></table>' if findings else '<p style="color:#10b981;font-weight:600">✅ All policies passed — no violations found</p>'}
</div>
<div class="footer">Generated by ThothCTL</div>
</div></body></html>"""

        with open(os.path.join(html_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

    # ── Helpers ─────────────────────────────────────────────────────────

    def _resolve_policy_dir(self, base_dir: str, policy_dir: str) -> Optional[str]:
        """Resolve policy directory — check Git URL, relative, absolute, or org repo.

        Resolution order:
        1. Git URL: clone to cache and use
        2. Relative to project: <base_dir>/<policy_dir>
        3. Absolute path: <policy_dir> as-is
        4. Organization policy repo (THOTH_POLICY_REPO env):
           - If policy_dir contains '/' resolve within org repo
           - Otherwise check <org_repo>/shared/policy
        """
        # 1. Git URL
        if self._is_git_url(policy_dir):
            return self._clone_policy_repo(policy_dir)

        # 2. Relative to project
        candidate = os.path.join(base_dir, policy_dir)
        if os.path.isdir(candidate):
            return candidate

        # 3. Absolute path
        if os.path.isabs(policy_dir) and os.path.isdir(policy_dir):
            return policy_dir

        # 4. Organization policy repo
        org_repo = os.environ.get("THOTH_POLICY_REPO")
        if org_repo and os.path.isdir(org_repo):
            # Try policy_dir as a path within the org repo
            org_candidate = os.path.join(org_repo, policy_dir)
            if os.path.isdir(org_candidate):
                return org_candidate
            # Fallback to shared/policy in org repo
            shared = os.path.join(org_repo, "shared", "policy")
            if os.path.isdir(shared):
                return shared

        # 5. THOTH_ORG_POLICY env → <cached_repo>/policy/
        org_policy_url = os.environ.get("THOTH_ORG_POLICY")
        if org_policy_url:
            from .....services.check.org_policy_loader import get_org_policy_path, resolve_policy_dir as _resolve_org_policy
            org_path = get_org_policy_path(org_policy_url)
            if org_path:
                org_policy_dir = _resolve_org_policy(org_path)
                if org_policy_dir:
                    return org_policy_dir

        return None

    def _is_git_url(self, value: str) -> bool:
        """Check if value is a Git URL."""
        return value.startswith(("https://", "git@", "ssh://", "git://"))

    def _clone_policy_repo(self, repo_url: str) -> Optional[str]:
        """Clone a policy Git repository to local cache. Returns path or None."""
        import hashlib

        try:
            import git
        except ImportError:
            self.ui.show_error("GitPython required for Git policy repos. Install: pip install gitpython")
            return None

        # Parse optional ref (url@branch or url@tag)
        ref = None
        if "@" in repo_url and not repo_url.startswith("git@"):
            repo_url, ref = repo_url.rsplit("@", 1)
        elif repo_url.startswith("git@") and repo_url.count("@") > 1:
            repo_url, ref = repo_url.rsplit("@", 1)

        # Cache in ~/.thothcf/.policy_cache/<hash>
        url_hash = hashlib.sha256(repo_url.encode()).hexdigest()[:12]
        cache_dir = Path.home() / ".thothcf" / ".policy_cache" / url_hash
        cache_dir.mkdir(parents=True, exist_ok=True)

        try:
            if (cache_dir / ".git").exists():
                # Pull latest
                self.logger.info(f"Updating cached policy repo: {repo_url}")
                repo = git.Repo(cache_dir)
                repo.remotes.origin.fetch()
                if ref:
                    repo.git.checkout(ref)
                else:
                    repo.remotes.origin.pull()
            else:
                # Fresh clone
                self.logger.info(f"Cloning policy repo: {repo_url}")
                self.ui.show_info(f"📥 Cloning policy repo: {repo_url}")
                kwargs = {"depth": 1} if not ref else {}
                repo = git.Repo.clone_from(repo_url, cache_dir, **kwargs)
                if ref:
                    repo.git.checkout(ref)

            return str(cache_dir)

        except Exception as e:
            self.logger.error(f"Failed to clone policy repo: {e}")
            self.ui.show_error(f"Failed to clone policy repo: {e}")
            return None

    def _find_scannable_files(self, directory: str) -> List[str]:
        """Find .tf, .yaml, .yml, .json files for conftest."""
        extensions = {".tf", ".yaml", ".yml", ".json", ".hcl"}
        exclude_dirs = {".terraform", ".git", "node_modules", ".terragrunt-cache"}
        files = []
        for root, dirs, filenames in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for f in filenames:
                if Path(f).suffix in extensions:
                    files.append(os.path.join(root, f))
        return files

    def _find_plan_files(self, directory: str) -> List[str]:
        """Find tfplan.json files for opa exec mode."""
        plans = []
        for root, _, files in os.walk(directory):
            for f in files:
                if f == "tfplan.json":
                    plans.append(os.path.join(root, f))
        return plans

    def _prepare_reports_dir(self, reports_dir: str) -> str:
        """Create and return the OPA reports directory."""
        report_dir = os.path.join(os.path.abspath(reports_dir), "opa")
        os.makedirs(report_dir, exist_ok=True)
        return report_dir
