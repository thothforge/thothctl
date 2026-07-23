"""Workflow orchestrator — executes SDLC phases in sequence."""
import logging
from typing import Dict, List, Optional

from .models import Phase, WorkflowResult
from .phases.base import PhaseExecutor
from .phases.plan import PlanPhaseExecutor
from .phases.develop import DevelopPhaseExecutor
from .phases.build import BuildPhaseExecutor
from .phases.test import TestPhaseExecutor
from .phases.secure import SecurePhaseExecutor
from .phases.deploy import DeployPhaseExecutor
from .phases.monitor import MonitorPhaseExecutor

logger = logging.getLogger(__name__)


# Phase execution order
PHASE_ORDER = [
    Phase.PLAN, Phase.DEVELOP, Phase.BUILD, Phase.TEST,
    Phase.SECURE, Phase.DEPLOY, Phase.MONITOR,
]

# Composite phase mappings
COMPOSITE_PHASES = {
    Phase.PRE_DEPLOY: [Phase.TEST, Phase.SECURE],
    Phase.ALL: PHASE_ORDER,
}


class WorkflowService:
    """Orchestrates DevSecOps SDLC phases."""

    def __init__(self):
        self._executors: Dict[Phase, PhaseExecutor] = {
            Phase.PLAN: PlanPhaseExecutor(),
            Phase.DEVELOP: DevelopPhaseExecutor(),
            Phase.BUILD: BuildPhaseExecutor(),
            Phase.TEST: TestPhaseExecutor(),
            Phase.SECURE: SecurePhaseExecutor(),
            Phase.DEPLOY: DeployPhaseExecutor(),
            Phase.MONITOR: MonitorPhaseExecutor(),
        }

    def execute(
        self,
        phases: List[Phase],
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        enforcement: str = "soft",
    ) -> WorkflowResult:
        """Execute one or more SDLC phases in order."""
        options = options or {}
        options["enforcement"] = enforcement
        result = WorkflowResult(enforcement=enforcement)

        # Resolve composite phases
        resolved = []
        for phase in phases:
            if phase in COMPOSITE_PHASES:
                resolved.extend(COMPOSITE_PHASES[phase])
            else:
                resolved.append(phase)

        # Deduplicate preserving order
        seen = set()
        ordered = []
        for p in resolved:
            if p not in seen:
                seen.add(p)
                ordered.append(p)

        # Execute phases in sequence
        for phase in ordered:
            executor = self._executors.get(phase)
            if not executor:
                logger.info(f"No executor for phase: {phase.value} — skipping")
                continue

            logger.info(f"Executing: {executor.description}")
            phase_result = executor.execute(directory, reports_dir, options)
            result.phases.append(phase_result)

            # Stop on hard enforcement failure
            if enforcement == "hard" and phase_result.gate_blocked:
                result.stopped_at = phase
                logger.warning(f"Pipeline blocked at phase: {phase.value}")
                break

        return result
