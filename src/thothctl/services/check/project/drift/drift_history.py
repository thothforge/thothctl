"""Drift history tracking and coverage trending over time."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_DIR = ".thothctl/drift_history"


class DriftHistory:
    """Stores drift snapshots and provides trend analysis."""

    def __init__(self, storage_dir: str = DEFAULT_HISTORY_DIR):
        self.base = Path(storage_dir)

    def save_snapshot(self, project: str, summary_dict: Dict[str, Any]) -> None:
        """Append a timestamped drift snapshot for a project."""
        path = self._project_path(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        history = self._load_raw(path)
        history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_resources": summary_dict.get("total_resources", 0),
            "total_drifted": summary_dict.get("total_drifted", 0),
            "coverage_pct": summary_dict.get("overall_coverage", 100.0),
            "stacks": summary_dict.get("total_stacks", 0),
            "severity_counts": self._aggregate_severities(summary_dict),
        })
        # Keep last 365 snapshots
        history = history[-365:]
        path.write_text(json.dumps(history, indent=2, default=str))

    def get_trend(self, project: str, last_n: int = 30) -> Dict[str, Any]:
        """Get coverage trend for a project over last N snapshots."""
        history = self._load_raw(self._project_path(project))
        if not history:
            return {"snapshots": 0, "trend": "no_data"}

        recent = history[-last_n:]
        coverages = [s["coverage_pct"] for s in recent]
        drifted_counts = [s["total_drifted"] for s in recent]

        first_cov = coverages[0]
        last_cov = coverages[-1]
        delta = round(last_cov - first_cov, 1)

        if delta > 1:
            trend = "improving"
        elif delta < -1:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "snapshots": len(recent),
            "trend": trend,
            "coverage_delta": delta,
            "current_coverage": last_cov,
            "min_coverage": round(min(coverages), 1),
            "max_coverage": round(max(coverages), 1),
            "avg_coverage": round(sum(coverages) / len(coverages), 1),
            "current_drifted": drifted_counts[-1],
            "peak_drifted": max(drifted_counts),
            "first_snapshot": recent[0]["timestamp"],
            "last_snapshot": recent[-1]["timestamp"],
            "history": [
                {"date": s["timestamp"][:10], "coverage": s["coverage_pct"], "drifted": s["total_drifted"]}
                for s in recent
            ],
        }

    def check_threshold(self, project: str, min_coverage: float = 90.0) -> Optional[str]:
        """Return a warning message if coverage is below threshold, else None."""
        history = self._load_raw(self._project_path(project))
        if not history:
            return None
        latest = history[-1]
        cov = latest["coverage_pct"]
        if cov < min_coverage:
            return (
                f"⚠️ IaC coverage ({cov}%) is below threshold ({min_coverage}%). "
                f"Drifted resources: {latest['total_drifted']}"
            )
        return None

    # -- internals --

    def _project_path(self, project: str) -> Path:
        safe = project.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return self.base / f"{safe}.json"

    def _load_raw(self, path: Path) -> List[Dict]:
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return []

    @staticmethod
    def _aggregate_severities(summary: Dict) -> Dict[str, int]:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for result in summary.get("results", []):
            for sev, n in result.get("severity_counts", {}).items():
                counts[sev] = counts.get(sev, 0) + n
        return counts
