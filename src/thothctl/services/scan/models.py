"""Scan report models — canonical data structures for all scan tools."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Finding:
    """A single security finding from a scan tool."""

    id: str
    severity: str = "MEDIUM"  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    title: str = ""
    resource: str = ""
    file: str = ""
    line: int = 0


@dataclass
class ToolReport:
    """Results from a single scan tool."""

    tool: str
    status: str = "COMPLETE"  # COMPLETE, FAIL, SKIPPED, TIMEOUT
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    warnings: int = 0
    errors: int = 0
    findings: List[Finding] = field(default_factory=list)
    report_path: str = ""
    duration_seconds: float = 0.0
    error_message: str = ""
    # Per-stack/module breakdown
    detailed: Dict[str, Dict] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.warnings + self.errors

    @property
    def success_rate(self) -> float:
        return (self.passed / self.total * 100) if self.total > 0 else 0.0

    @property
    def issues_count(self) -> int:
        return self.failed + self.errors

    def to_report_data(self) -> Dict:
        """Convert to legacy report_data dict for backward compatibility."""
        return {
            "passed_count": self.passed,
            "failed_count": self.failed,
            "skipped_count": self.skipped,
            "error_count": self.errors,
            "warning_count": self.warnings,
        }


@dataclass
class ScanReport:
    """Consolidated report across all scan tools."""

    tools: List[ToolReport] = field(default_factory=list)
    directory: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def total_findings(self) -> int:
        return sum(t.issues_count for t in self.tools)

    @property
    def severity_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for t in self.tools:
            for f in t.findings:
                counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts

    def get_tool(self, name: str) -> Optional[ToolReport]:
        for t in self.tools:
            if t.tool == name:
                return t
        return None
