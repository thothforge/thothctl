"""OPA/Conftest scanner for IaC policy evaluation.

Supports two modes:
- conftest: Static analysis of .tf/.yaml files using Rego policies (default)
- opa: Plan-based evaluation using `opa exec` against tfplan.json files

Both modes use the same Rego policy language and can share policies.
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
        # Add data files if specified
        if options.get("data_dir"):
            cmd_json.extend(["--data", options["data_dir"]])

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
            report_data = self._parse_conftest_json(result_json.stdout)

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
                }

            self.ui.show_success()
            return {
                "status": "COMPLETE",
                "report_path": report_dir,
                "report_data": report_data,
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

            report_data = self._parse_opa_json(result.stdout)

            if result.returncode != 0 and not result.stdout:
                self.ui.show_error(f"OPA error: {result.stderr}")
                return {
                    "status": "FAIL",
                    "error": result.stderr,
                    "report_path": report_dir,
                    "report_data": report_data,
                }

            self.ui.show_success()
            return {
                "status": "COMPLETE",
                "report_path": report_dir,
                "report_data": report_data,
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

    def _parse_conftest_json(self, stdout: str) -> Dict:
        """Parse conftest JSON output into report_data format.

        Conftest JSON structure:
        [{"filename": "...", "successes": N,
          "failures": [{"msg": "..."}], "warnings": [{"msg": "..."}]}]
        """
        try:
            results = json.loads(stdout) if stdout else []
        except json.JSONDecodeError:
            return self._empty_report_data()

        passed = sum(r.get("successes", 0) for r in results)
        failed = sum(len(r.get("failures", [])) for r in results)
        warnings = sum(len(r.get("warnings", [])) for r in results)
        exceptions = sum(len(r.get("exceptions", [])) for r in results)

        return {
            "passed_count": passed,
            "failed_count": failed,
            "skipped_count": exceptions,
            "error_count": 0,
            "warning_count": warnings,
        }

    def _parse_opa_json(self, stdout: str) -> Dict:
        """Parse opa exec JSON output.

        OPA exec structure:
        {"result": [{"path": "file.json", "result": true/false/<value>}]}
        """
        try:
            data = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            return self._empty_report_data()

        results = data.get("result", [])
        passed = sum(1 for r in results if r.get("result") is True)
        failed = sum(1 for r in results if r.get("result") is False)
        # Results that are neither true nor false (e.g. score values)
        other = len(results) - passed - failed

        return {
            "passed_count": passed,
            "failed_count": failed,
            "skipped_count": other,
            "error_count": 0,
        }

    @staticmethod
    def _empty_report_data() -> Dict:
        return {
            "passed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "error_count": 0,
        }

    # ── Helpers ─────────────────────────────────────────────────────────

    def _resolve_policy_dir(self, base_dir: str, policy_dir: str) -> Optional[str]:
        """Resolve policy directory — check relative to project, then absolute."""
        candidate = os.path.join(base_dir, policy_dir)
        if os.path.isdir(candidate):
            return candidate
        if os.path.isabs(policy_dir) and os.path.isdir(policy_dir):
            return policy_dir
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
