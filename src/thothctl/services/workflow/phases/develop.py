"""Develop phase: environment validation, structure enforcement, documentation."""
import logging
import subprocess
import time
from typing import Dict, Optional

from ..models import Phase, PhaseResult, StepResult, StepStatus
from .base import PhaseExecutor

logger = logging.getLogger(__name__)


class DevelopPhaseExecutor(PhaseExecutor):
    """Phase 2: Environment setup, project structure, documentation."""

    @property
    def phase(self) -> Phase:
        return Phase.DEVELOP

    @property
    def description(self) -> str:
        return "\U0001f4bb Develop — Environment validation, structure enforcement, documentation"

    def execute(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
    ) -> PhaseResult:
        options = options or {}
        result = PhaseResult(phase=self.phase)

        # Step 1: Check environment
        result.steps.append(self._check_environment())

        # Step 2: Check project structure
        result.steps.append(self._check_project(directory))

        # Step 3: Generate documentation
        result.steps.append(self._document_iac(directory))

        # Phase passes if no steps failed
        result.passed = not any(
            s.status == StepStatus.FAILED for s in result.steps
        )
        return result

    def _check_environment(self) -> StepResult:
        """Run thothctl check environment."""
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                ["thothctl", "check", "environment"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            duration = time.perf_counter() - start
            status = StepStatus.PASSED if proc.returncode == 0 else StepStatus.WARNING
            return StepResult(
                name="check-environment",
                status=status,
                command="thothctl check environment",
                duration_seconds=duration,
                summary="Environment tools verified" if status == StepStatus.PASSED else "Some tools missing",
            )
        except Exception as e:
            return StepResult(
                name="check-environment",
                status=StepStatus.FAILED,
                command="thothctl check environment",
                duration_seconds=time.perf_counter() - start,
                summary=str(e),
            )

    def _check_project(self, directory: str) -> StepResult:
        """Run thothctl check project iac."""
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                ["thothctl", "check", "project", "iac"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=directory,
            )
            duration = time.perf_counter() - start
            status = StepStatus.PASSED if proc.returncode == 0 else StepStatus.WARNING
            return StepResult(
                name="check-project",
                status=status,
                command="thothctl check project iac",
                duration_seconds=duration,
                summary="Project structure valid" if status == StepStatus.PASSED else "Structure issues found",
            )
        except Exception as e:
            return StepResult(
                name="check-project",
                status=StepStatus.FAILED,
                command="thothctl check project iac",
                duration_seconds=time.perf_counter() - start,
                summary=str(e),
            )

    def _document_iac(self, directory: str) -> StepResult:
        """Run thothctl document iac."""
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                ["thothctl", "document", "iac"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=directory,
            )
            duration = time.perf_counter() - start
            status = StepStatus.PASSED if proc.returncode == 0 else StepStatus.SKIPPED
            return StepResult(
                name="document-iac",
                status=status,
                command="thothctl document iac",
                duration_seconds=duration,
                summary="Documentation generated" if status == StepStatus.PASSED else "Documentation skipped",
            )
        except Exception as e:
            return StepResult(
                name="document-iac",
                status=StepStatus.SKIPPED,
                command="thothctl document iac",
                duration_seconds=time.perf_counter() - start,
                summary=f"Skipped: {e}",
            )
