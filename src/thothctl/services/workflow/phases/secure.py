"""Secure phase: security scanning, compliance, vulnerability detection."""
import logging
import time
from typing import Dict, List, Optional

from ..models import Phase, PhaseResult, StepResult, StepStatus
from .base import PhaseExecutor

logger = logging.getLogger(__name__)


class SecurePhaseExecutor(PhaseExecutor):
    """Phase 5: Security scanning with multi-tool pipeline."""

    @property
    def phase(self) -> Phase:
        return Phase.SECURE

    @property
    def description(self) -> str:
        return "\U0001f512 Secure — Security scanning, compliance, vulnerability detection"

    def execute(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
    ) -> PhaseResult:
        options = options or {}
        result = PhaseResult(phase=self.phase)

        tools = options.get("tools", ["checkov", "trivy", "opa"])
        if isinstance(tools, tuple):
            tools = list(tools)
        enforcement = options.get("enforcement", "soft")
        policy_dir = options.get("policy_dir")

        scan_options: Dict = {}
        if policy_dir:
            scan_options["policy_dir"] = policy_dir

        try:
            from ....services.scan.scan_service import ScanService

            scan_service = ScanService()
            start = time.perf_counter()

            scan_results = scan_service.execute_scans(
                directory=directory,
                reports_dir=reports_dir,
                selected_tools=tools,
                options=scan_options,
            )

            duration = time.perf_counter() - start
            tool_count = max(len(tools), 1)

            for tool_name, tool_result in scan_results.items():
                if tool_name == "summary" or not isinstance(tool_result, dict):
                    continue
                rd = tool_result.get("report_data", {})
                failed = rd.get("failed_count", 0) + rd.get("error_count", 0)
                passed_count = rd.get("passed_count", 0)
                warnings = rd.get("warning_count", 0)
                status = StepStatus.PASSED if failed == 0 else StepStatus.FAILED
                if failed == 0 and warnings > 0:
                    status = StepStatus.WARNING

                result.steps.append(StepResult(
                    name=f"scan-{tool_name}",
                    status=status,
                    command=f"thothctl scan iac -t {tool_name}",
                    duration_seconds=duration / tool_count,
                    summary=f"{passed_count} passed, {failed} failed, {warnings} warnings",
                    report_path=tool_result.get("report_path"),
                    findings_count=failed,
                    details=rd,
                ))

            # Gate logic
            total_failures = sum(s.findings_count for s in result.steps)
            if total_failures > 0:
                result.passed = False
            if enforcement == "hard" and total_failures > 0:
                result.gate_blocked = True

        except Exception as e:
            logger.error(f"Secure phase failed: {e}")
            result.steps.append(StepResult(
                name="scan-error",
                status=StepStatus.FAILED,
                command="thothctl scan iac",
                summary=str(e),
                findings_count=1,
            ))
            result.passed = False

        return result
