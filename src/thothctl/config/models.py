from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


class ScanStatus(Enum):
    """Enumeration of possible scan statuses."""

    COMPLETE = "COMPLETE"
    RUNNING = "RUNNING"
    FAIL = "FAIL"
    SKIP = "SKIP"
    UNKNOWN = "UNKNOWN"


@dataclass
class ScanResult:
    """Data class representing a scan result."""

    status: ScanStatus
    report_path: Optional[Path] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the scan result to a dictionary."""
        return {
            "status": self.status.value,
            "report_path": str(self.report_path) if self.report_path else None,
            "error": self.error,
            "details": self.details,
        }

    @classmethod
    def success(
        cls, report_path: Path, details: Optional[Dict[str, Any]] = None
    ) -> "ScanResult":
        """Create a successful scan result."""
        return cls(status=ScanStatus.COMPLETE, report_path=report_path, details=details)

    @classmethod
    def failure(
        cls, error: str, details: Optional[Dict[str, Any]] = None
    ) -> "ScanResult":
        """Create a failed scan result."""
        return cls(status=ScanStatus.FAIL, error=error, details=details)

    @classmethod
    def skipped(cls, reason: str) -> "ScanResult":
        """Create a skipped scan result."""
        return cls(status=ScanStatus.SKIP, error=reason)


@dataclass
class ScanOptions:
    """Data class representing scanner options."""

    severity: Optional[str] = None
    format: Optional[str] = None
    additional_args: Optional[list] = None
    output_file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the options to a dictionary."""
        return {key: value for key, value in self.__dict__.items() if value is not None}

    @classmethod
    def from_dict(cls, options_dict: Dict[str, Any]) -> "ScanOptions":
        """Create ScanOptions from a dictionary."""
        return cls(
            **{k: v for k, v in options_dict.items() if k in cls.__dataclass_fields__}
        )


class ScanSeverity(Enum):
    """Enumeration of possible vulnerability severities."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


@dataclass
class Vulnerability:
    """Data class representing a vulnerability finding."""

    id: str
    severity: ScanSeverity
    title: str
    description: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    fix_suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the vulnerability to a dictionary."""
        return {
            "id": self.id,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "fix_suggestion": self.fix_suggestion,
        }


@dataclass
class ScanSummary:
    """Data class representing a scan summary."""

    total_issues: int
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    unknown_count: int = 0
    scan_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert the summary to a dictionary."""
        return {
            "total_issues": self.total_issues,
            "by_severity": {
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
                "low": self.low_count,
                "unknown": self.unknown_count,
            },
            "scan_duration": self.scan_duration,
        }

    def has_issues(self, min_severity: ScanSeverity = ScanSeverity.LOW) -> bool:
        """Check if there are issues at or above the specified severity level."""
        severity_counts = {
            ScanSeverity.CRITICAL: self.critical_count,
            ScanSeverity.HIGH: self.high_count,
            ScanSeverity.MEDIUM: self.medium_count,
            ScanSeverity.LOW: self.low_count,
        }

        return any(
            count > 0
            for sev, count in severity_counts.items()
            if sev.value >= min_severity.value
        )
