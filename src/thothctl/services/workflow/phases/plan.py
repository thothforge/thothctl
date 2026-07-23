"""Plan phase: cost estimation, blast radius, risk assessment."""
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from ..models import Phase, PhaseResult, StepResult, StepStatus
from .base import PhaseExecutor

logger = logging.getLogger(__name__)


class PlanPhaseExecutor(PhaseExecutor):
    """Phase 1: Cost estimation and risk assessment from tfplan."""

    @property
    def phase(self) -> Phase:
        return Phase.PLAN

    @property
    def description(self) -> str:
        return "\U0001f4cb Plan — Cost estimation, blast radius, risk assessment"

    def execute(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
    ) -> PhaseResult:
        options = options or {}
        result = PhaseResult(phase=self.phase)

        # Find tfplan files
        plan_files = self._find_plan_files(directory)

        if not plan_files:
            result.steps.append(StepResult(
                name="plan-check",
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

        # Step 1: Cost analysis
        result.steps.append(self._run_cost_analysis(directory))

        # Step 2: Blast radius
        result.steps.append(self._run_blast_radius(directory))

        # Phase passes if no steps failed
        result.passed = not any(
            s.status == StepStatus.FAILED for s in result.steps
        )
        return result

    def _find_plan_files(self, directory: str) -> List[str]:
        """Find tfplan.json files in the project."""
        plans = []
        for root, _, files in os.walk(directory):
            # Skip hidden dirs and Reports
            if any(part.startswith(".") for part in Path(root).parts):
                continue
            if "Reports" in root:
                continue
            for f in files:
                if f == "tfplan.json":
                    plans.append(os.path.join(root, f))
        return plans

    def _run_cost_analysis(self, directory: str) -> StepResult:
        """Run thothctl check iac -type cost-analysis."""
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                ["thothctl", "check", "iac", "-type", "cost-analysis", "--recursive"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=directory,
            )
            duration = time.perf_counter() - start
            status = StepStatus.PASSED if proc.returncode == 0 else StepStatus.WARNING
            return StepResult(
                name="cost-analysis",
                status=status,
                command="thothctl check iac -type cost-analysis --recursive",
                duration_seconds=duration,
                summary="Cost estimation completed" if status == StepStatus.PASSED else "Cost analysis had warnings",
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                name="cost-analysis",
                status=StepStatus.SKIPPED,
                command="thothctl check iac -type cost-analysis",
                duration_seconds=time.perf_counter() - start,
                summary="Timed out after 120s",
            )
        except Exception as e:
            return StepResult(
                name="cost-analysis",
                status=StepStatus.SKIPPED,
                command="thothctl check iac -type cost-analysis",
                duration_seconds=time.perf_counter() - start,
                summary=f"Skipped: {e}",
            )

    def _run_blast_radius(self, directory: str) -> StepResult:
        """Run thothctl check iac -type blast-radius."""
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                ["thothctl", "check", "iac", "-type", "blast-radius", "--recursive"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=directory,
            )
            duration = time.perf_counter() - start
            status = StepStatus.PASSED if proc.returncode == 0 else StepStatus.WARNING
            return StepResult(
                name="blast-radius",
                status=status,
                command="thothctl check iac -type blast-radius --recursive",
                duration_seconds=duration,
                summary="Blast radius assessed" if status == StepStatus.PASSED else "Blast radius warnings",
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                name="blast-radius",
                status=StepStatus.SKIPPED,
                command="thothctl check iac -type blast-radius",
                duration_seconds=time.perf_counter() - start,
                summary="Timed out after 120s",
            )
        except Exception as e:
            return StepResult(
                name="blast-radius",
                status=StepStatus.SKIPPED,
                command="thothctl check iac -type blast-radius",
                duration_seconds=time.perf_counter() - start,
                summary=f"Skipped: {e}",
            )
