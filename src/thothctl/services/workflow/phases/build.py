"""Build phase: inventory creation, dependency tracking, version management."""
import logging
import subprocess
import time
from typing import Dict, Optional

from ..models import Phase, PhaseResult, StepResult, StepStatus
from .base import PhaseExecutor

logger = logging.getLogger(__name__)


class BuildPhaseExecutor(PhaseExecutor):
    """Phase 3: Infrastructure inventory, SBOM, version tracking."""

    @property
    def phase(self) -> Phase:
        return Phase.BUILD

    @property
    def description(self) -> str:
        return "\U0001f528 Build — Inventory creation, dependency tracking, version management"

    def execute(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
    ) -> PhaseResult:
        options = options or {}
        result = PhaseResult(phase=self.phase)

        # Step 1: Inventory with version checks
        result.steps.append(self._run_inventory(directory, options))

        # Phase passes if no steps failed
        result.passed = not any(
            s.status == StepStatus.FAILED for s in result.steps
        )
        return result

    def _run_inventory(self, directory: str, options: Dict) -> StepResult:
        """Run thothctl inventory iac --check-versions --check-provider-versions."""
        start = time.perf_counter()
        try:
            cmd = [
                "thothctl", "inventory", "iac",
                "--check-versions",
                "--check-provider-versions",
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                cwd=directory,
            )
            duration = time.perf_counter() - start
            status = StepStatus.PASSED if proc.returncode == 0 else StepStatus.WARNING
            return StepResult(
                name="inventory",
                status=status,
                command="thothctl inventory iac --check-versions --check-provider-versions",
                duration_seconds=duration,
                summary="Inventory created with version analysis" if status == StepStatus.PASSED else "Inventory completed with warnings",
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                name="inventory",
                status=StepStatus.SKIPPED,
                command="thothctl inventory iac --check-versions",
                duration_seconds=time.perf_counter() - start,
                summary="Timed out after 180s",
            )
        except Exception as e:
            return StepResult(
                name="inventory",
                status=StepStatus.FAILED,
                command="thothctl inventory iac --check-versions",
                duration_seconds=time.perf_counter() - start,
                summary=str(e),
                findings_count=1,
            )
