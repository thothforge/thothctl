"""Abstract base for phase executors."""
from abc import ABC, abstractmethod
from typing import Dict, Optional

from ..models import Phase, PhaseResult


class PhaseExecutor(ABC):
    """Base class for SDLC phase executors."""

    @property
    @abstractmethod
    def phase(self) -> Phase:
        """Which phase this executor handles."""
        ...

    @abstractmethod
    def execute(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
    ) -> PhaseResult:
        """Run all steps in this phase. Returns PhaseResult."""
        ...

    @property
    def description(self) -> str:
        """Human-readable phase description for UI."""
        return f"Phase: {self.phase.value}"
