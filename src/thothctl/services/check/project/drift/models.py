"""Data models for drift detection."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DriftSeverity(Enum):
    """Severity of a drifted resource."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DriftType(Enum):
    """Type of drift detected."""
    CHANGED = "changed"       # Resource exists but attributes differ
    DELETED = "deleted"       # In state but missing from cloud
    UNMANAGED = "unmanaged"   # In cloud but not in state (create action in reverse)


@dataclass
class DriftedResource:
    """A single resource that has drifted."""
    address: str
    resource_type: str
    drift_type: DriftType
    severity: DriftSeverity
    changed_attributes: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    detail: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "resource_type": self.resource_type,
            "drift_type": self.drift_type.value,
            "severity": self.severity.value,
            "changed_attributes": self.changed_attributes,
            "actions": self.actions,
            "detail": self.detail,
            "tags": self.tags,
        }


@dataclass
class DriftResult:
    """Result of a drift detection run for a single stack."""
    directory: str
    total_resources: int = 0
    drifted_resources: List[DriftedResource] = field(default_factory=list)
    coverage_pct: float = 100.0
    error: Optional[str] = None

    @property
    def has_drift(self) -> bool:
        return len(self.drifted_resources) > 0

    @property
    def severity_counts(self) -> Dict[str, int]:
        counts = {s.value: 0 for s in DriftSeverity}
        for r in self.drifted_resources:
            counts[r.severity.value] += 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "directory": self.directory,
            "total_resources": self.total_resources,
            "drifted_resources": [r.to_dict() for r in self.drifted_resources],
            "coverage_pct": self.coverage_pct,
            "has_drift": self.has_drift,
            "severity_counts": self.severity_counts,
            "error": self.error,
        }


@dataclass
class DriftSummary:
    """Aggregated drift results across multiple stacks."""
    results: List[DriftResult] = field(default_factory=list)

    @property
    def total_drifted(self) -> int:
        return sum(len(r.drifted_resources) for r in self.results)

    @property
    def total_resources(self) -> int:
        return sum(r.total_resources for r in self.results)

    @property
    def overall_coverage(self) -> float:
        if self.total_resources == 0:
            return 100.0
        managed = self.total_resources - self.total_drifted
        return round((managed / self.total_resources) * 100, 1)

    @property
    def has_drift(self) -> bool:
        return any(r.has_drift for r in self.results)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_stacks": len(self.results),
            "total_resources": self.total_resources,
            "total_drifted": self.total_drifted,
            "overall_coverage": self.overall_coverage,
            "has_drift": self.has_drift,
            "results": [r.to_dict() for r in self.results],
        }
