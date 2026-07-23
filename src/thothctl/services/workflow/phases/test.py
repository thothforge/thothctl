"""Test phase: plan validation, change impact analysis."""
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from ..models import Phase, PhaseResult, StepResult, StepStatus
from .base import PhaseExecutor

logger = logging.getLogger(__name__)


class TestPhaseExecutor(PhaseExecutor):
    """Phase 4: Terraform plan validation and impact analysis."""

    @property
    def phase(self) -> Phase:
        return Phase.TEST

    @property
    def description(self) -> str:
        return "\u2705 Test — Plan validation, change impact analysis"

    def execute(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
    ) -> PhaseResult:
        options = options or {}
        result = PhaseResult(phase=self.phase)

        # Check if tfplan exists
        plan_files = self._find_plan_files(directory)

        if not plan_files:
            result.steps.append(StepResult(
                name="tfplan-check",
                status=StepStatus.SKIPPED,
                command="(requires tfplan.json)",
                summary=(
                    "No tfplan.json found. Generate plans first:\n"
                    "  Terragrunt: terragrunt run-all plan --out-dir tfplan --json-out-dir tfplan\n"
                    "  Terraform:  terraform plan -out=tfplan.binary && "
                    "terraform show -json tfplan.binary > tfplan.json"
                ),
            ))
            return result

        # Step 1: Validate tfplan
        result.steps.append(self._validate_tfplan(directory))

        # Phase passes if no steps failed
        result.passed = not any(
            s.status == StepStatus.FAILED for s in result.steps
        )
        return result

    def _find_plan_files(self, directory: str) -> List[str]:
        """Find tfplan.json files in the project."""
        plans = []
        for root, _, files in os.walk(directory):
            if any(part.startswith(".") for part in Path(root).parts):
                continue
            if "Reports" in root:
                continue
            for f in files:
                if f == "tfplan.json":
                    plans.append(os.path.join(root, f))
        return plans

    def _validate_tfplan(self, directory: str) -> StepResult:
        """Run thothctl check iac -type tfplan."""
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                ["thothctl", "check", "iac", "-type", "tfplan", "--recursive"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=directory,
            )
            duration = time.perf_counter() - start
            status = StepStatus.PASSED if proc.returncode == 0 else StepStatus.WARNING
            return StepResult(
                name="tfplan-validation",
                status=status,
                command="thothctl check iac -type tfplan --recursive",
                duration_seconds=duration,
                summary="Plan validation passed" if status == StepStatus.PASSED else "Plan has changes to review",
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                name="tfplan-validation",
                status=StepStatus.SKIPPED,
                command="thothctl check iac -type tfplan",
                duration_seconds=time.perf_counter() - start,
                summary="Timed out after 120s",
            )
        except Exception as e:
            return StepResult(
                name="tfplan-validation",
                status=StepStatus.FAILED,
                command="thothctl check iac -type tfplan",
                duration_seconds=time.perf_counter() - start,
                summary=str(e),
                findings_count=1,
            )
