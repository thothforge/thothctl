"""Data models for the DevSecOps workflow engine."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Phase(Enum):
    """DevSecOps SDLC phases."""
    PLAN = "plan"
    DEVELOP = "develop"
    BUILD = "build"
    TEST = "test"
    SECURE = "secure"
    DEPLOY = "deploy"
    MONITOR = "monitor"
    ALL = "all"
    PRE_DEPLOY = "pre-deploy"


class StepStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class StepResult:
    """Result of a single step within a phase."""
    name: str
    status: StepStatus
    command: str
    duration_seconds: float = 0.0
    summary: str = ""
    report_path: Optional[str] = None
    findings_count: int = 0
    details: Dict = field(default_factory=dict)


@dataclass
class PhaseResult:
    """Result of executing an entire phase."""
    phase: Phase
    steps: List[StepResult] = field(default_factory=list)
    passed: bool = True
    gate_blocked: bool = False

    @property
    def total_findings(self) -> int:
        return sum(s.findings_count for s in self.steps)

    @property
    def duration_seconds(self) -> float:
        return sum(s.duration_seconds for s in self.steps)


@dataclass
class WorkflowResult:
    """Complete workflow execution result."""
    phases: List[PhaseResult] = field(default_factory=list)
    enforcement: str = "soft"
    stopped_at: Optional[Phase] = None

    @property
    def passed(self) -> bool:
        return all(p.passed for p in self.phases)

    @property
    def total_findings(self) -> int:
        return sum(p.total_findings for p in self.phases)
