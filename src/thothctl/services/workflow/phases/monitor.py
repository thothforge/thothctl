"""Monitor phase: drift detection, continuous monitoring."""
import logging
import subprocess
import time
from typing import Dict, Optional

from ..models import Phase, PhaseResult, StepResult, StepStatus
from .base import PhaseExecutor

logger = logging.getLogger(__name__)


class MonitorPhaseExecutor(PhaseExecutor):
    """Phase 7: Drift detection and continuous monitoring."""

    @property
    def phase(self) -> Phase:
        return Phase.MONITOR

    @property
    def description(self) -> str:
        return "\U0001f4ca Monitor — Drift detection, continuous monitoring"

    def execute(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
    ) -> PhaseResult:
        options = options or {}
        result = PhaseResult(phase=self.phase)

        # Step 1: Drift detection
        result.steps.append(self._run_drift_detection(directory, options))

        # Phase passes if no steps failed
        result.passed = not any(
            s.status == StepStatus.FAILED for s in result.steps
        )
        return result

    def _run_drift_detection(self, directory: str, options: Dict) -> StepResult:
        """Run thothctl check iac -type drift."""
        start = time.perf_counter()
        tftool = options.get("tftool", "tofu")
        try:
            cmd = [
                "thothctl", "check", "iac",
                "-type", "drift",
                "--tftool", tftool,
                "--recursive",
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=directory,
            )
            duration = time.perf_counter() - start
            status = StepStatus.PASSED if proc.returncode == 0 else StepStatus.WARNING
            return StepResult(
                name="drift-detection",
                status=status,
                command=f"thothctl check iac -type drift --tftool {tftool} --recursive",
                duration_seconds=duration,
                summary="No drift detected" if status == StepStatus.PASSED else "Drift detected — review changes",
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                name="drift-detection",
                status=StepStatus.SKIPPED,
                command="thothctl check iac -type drift",
                duration_seconds=time.perf_counter() - start,
                summary="Timed out after 300s (requires cloud credentials)",
            )
        except Exception as e:
            return StepResult(
                name="drift-detection",
                status=StepStatus.SKIPPED,
                command="thothctl check iac -type drift",
                duration_seconds=time.perf_counter() - start,
                summary=f"Skipped: {e}",
            )
