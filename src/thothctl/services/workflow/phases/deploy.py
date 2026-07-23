"""Deploy phase: pre-deployment validation and enforcement gates."""
import logging
import time
from typing import Dict, Optional

from ..models import Phase, PhaseResult, StepResult, StepStatus
from .base import PhaseExecutor

logger = logging.getLogger(__name__)


class DeployPhaseExecutor(PhaseExecutor):
    """Phase 6: Pre-deployment checks and approval gates."""

    @property
    def phase(self) -> Phase:
        return Phase.DEPLOY

    @property
    def description(self) -> str:
        return "\U0001f680 Deploy — Pre-deployment validation, enforcement gates"

    def execute(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
    ) -> PhaseResult:
        options = options or {}
        result = PhaseResult(phase=self.phase)
        enforcement = options.get("enforcement", "soft")

        # Step 1: Run security scan with hard enforcement
        # This reuses the secure phase but forces hard enforcement
        from .secure import SecurePhaseExecutor

        secure_executor = SecurePhaseExecutor()
        deploy_options = dict(options)
        deploy_options["enforcement"] = "hard"

        start = time.perf_counter()
        secure_result = secure_executor.execute(directory, reports_dir, deploy_options)
        duration = time.perf_counter() - start

        # Translate secure results into deploy gate
        total_failures = secure_result.total_findings
        if total_failures == 0:
            result.steps.append(StepResult(
                name="deploy-gate",
                status=StepStatus.PASSED,
                command="thothctl scan iac --enforcement hard",
                duration_seconds=duration,
                summary="All security gates passed — safe to deploy",
            ))
        else:
            result.steps.append(StepResult(
                name="deploy-gate",
                status=StepStatus.FAILED,
                command="thothctl scan iac --enforcement hard",
                duration_seconds=duration,
                summary=f"Deployment blocked: {total_failures} violation(s) must be resolved",
                findings_count=total_failures,
            ))
            result.passed = False
            if enforcement == "hard":
                result.gate_blocked = True

        return result
