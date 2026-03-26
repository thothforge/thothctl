"""Drift detection service using terraform/tofu plan."""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    DriftedResource,
    DriftResult,
    DriftSeverity,
    DriftSummary,
    DriftType,
)

logger = logging.getLogger(__name__)

# Resource types considered stateful / high-value
_CRITICAL_TYPES = {
    "aws_db_instance", "aws_rds_cluster", "aws_dynamodb_table",
    "aws_s3_bucket", "aws_efs_file_system", "aws_elasticache_cluster",
    "aws_redshift_cluster", "aws_kms_key", "aws_secretsmanager_secret",
    "google_sql_database_instance", "google_storage_bucket",
    "azurerm_mssql_database", "azurerm_storage_account",
}

_HIGH_TYPES = {
    "aws_eks_cluster", "aws_ecs_cluster", "aws_lambda_function",
    "aws_iam_role", "aws_iam_policy", "aws_vpc", "aws_subnet",
    "aws_security_group", "aws_lb", "aws_autoscaling_group",
    "google_container_cluster", "google_compute_instance",
    "azurerm_kubernetes_cluster", "azurerm_virtual_machine",
}


class DriftDetectionService:
    """Detect infrastructure drift via terraform/tofu plan."""

    def __init__(self, tftool: str = "tofu"):
        self.tftool = tftool

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_drift_from_plan(self, plan_path: str) -> DriftResult:
        """Parse an existing tfplan.json and classify drift."""
        directory = str(Path(plan_path).parent)
        try:
            with open(plan_path, "r") as f:
                plan_data = json.load(f)
            return self._analyse_plan(plan_data, directory)
        except Exception as e:
            logger.error(f"Failed to parse plan {plan_path}: {e}")
            return DriftResult(directory=directory, error=str(e))

    def detect_drift_live(self, directory: str) -> DriftResult:
        """Run terraform/tofu plan -detailed-exitcode and analyse output."""
        plan_data, err = self._run_plan(directory)
        if err:
            return DriftResult(directory=directory, error=err)
        return self._analyse_plan(plan_data, directory)

    def detect_drift(
        self,
        directory: str,
        recursive: bool = False,
        plan_files: Optional[List[str]] = None,
        filter_tags: Optional[Dict[str, str]] = None,
    ) -> DriftSummary:
        """High-level entry point. Uses existing plan files if available, else runs live plan.

        Args:
            filter_tags: Only include resources matching ALL given tags.
                         e.g. {"env": "prod", "team": "platform"}
        """
        summary = DriftSummary()

        if plan_files:
            for pf in plan_files:
                summary.results.append(self.detect_drift_from_plan(pf))
        elif recursive:
            for root, _, files in os.walk(directory):
                if "tfplan.json" in files:
                    summary.results.append(
                        self.detect_drift_from_plan(os.path.join(root, "tfplan.json"))
                    )
                elif self._is_tf_root(root):
                    summary.results.append(self.detect_drift_live(root))
        else:
            plan_json = os.path.join(directory, "tfplan.json")
            if os.path.exists(plan_json):
                summary.results.append(self.detect_drift_from_plan(plan_json))
            else:
                summary.results.append(self.detect_drift_live(directory))

        if filter_tags:
            self._apply_tag_filter(summary, filter_tags)

        return summary

    # ------------------------------------------------------------------
    # Ignore support
    # ------------------------------------------------------------------

    def _load_driftignore(self, directory: str) -> List[str]:
        """Load .driftignore patterns from directory."""
        ignore_path = os.path.join(directory, ".driftignore")
        if not os.path.exists(ignore_path):
            return []
        with open(ignore_path, "r") as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

    def _is_ignored(self, address: str, patterns: List[str]) -> bool:
        import fnmatch
        return any(fnmatch.fnmatch(address, p) for p in patterns)

    # ------------------------------------------------------------------
    # Plan execution
    # ------------------------------------------------------------------

    def _run_plan(self, directory: str) -> tuple:
        """Run terraform/tofu plan and return (json_data, error)."""
        try:
            # Init first
            subprocess.run(
                [self.tftool, "init", "-input=false"],
                cwd=directory, capture_output=True, timeout=300,
            )
            result = subprocess.run(
                [self.tftool, "plan", "-detailed-exitcode", "-json", "-out=tfplan.tmp"],
                cwd=directory, capture_output=True, text=True, timeout=600,
            )
            # exit 0 = no changes, 1 = error, 2 = changes (drift)
            if result.returncode == 1:
                return None, f"Plan failed: {result.stderr[:500]}"

            show = subprocess.run(
                [self.tftool, "show", "-json", "tfplan.tmp"],
                cwd=directory, capture_output=True, text=True, timeout=120,
            )
            # Cleanup temp plan
            tmp = os.path.join(directory, "tfplan.tmp")
            if os.path.exists(tmp):
                os.remove(tmp)

            return json.loads(show.stdout), None
        except subprocess.TimeoutExpired:
            return None, "Plan timed out"
        except Exception as e:
            return None, str(e)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def _analyse_plan(self, plan_data: dict, directory: str) -> DriftResult:
        """Classify resource_changes from a plan JSON as drift."""
        ignore_patterns = self._load_driftignore(directory)
        resource_changes = plan_data.get("resource_changes", [])

        total = 0
        drifted: List[DriftedResource] = []

        for rc in resource_changes:
            actions = rc.get("change", {}).get("actions", [])
            # "no-op" / "read" are not drift
            if actions == ["no-op"] or actions == ["read"]:
                total += 1
                continue

            address = rc.get("address", "")
            if self._is_ignored(address, ignore_patterns):
                total += 1
                continue

            rtype = rc.get("type", "")
            total += 1

            drift_type = self._classify_drift_type(actions)
            if drift_type is None:
                continue

            changed_attrs = self._extract_changed_attrs(rc.get("change", {}))
            severity = self._assess_severity(rtype, drift_type, actions, changed_attrs)

            drifted.append(DriftedResource(
                address=address,
                resource_type=rtype,
                drift_type=drift_type,
                severity=severity,
                changed_attributes=changed_attrs,
                actions=actions,
                detail=self._build_detail(actions, changed_attrs),
                tags=self._extract_tags(rc),
            ))

        coverage = round(((total - len(drifted)) / total) * 100, 1) if total else 100.0

        return DriftResult(
            directory=directory,
            total_resources=total,
            drifted_resources=drifted,
            coverage_pct=coverage,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_drift_type(actions: List[str]) -> Optional[DriftType]:
        if "delete" in actions and "create" in actions:
            return DriftType.CHANGED  # replace = recreate
        if "delete" in actions:
            return DriftType.DELETED
        if "update" in actions:
            return DriftType.CHANGED
        if "create" in actions:
            return DriftType.UNMANAGED
        return None

    @staticmethod
    def _extract_changed_attrs(change: dict) -> List[str]:
        before = change.get("before") or {}
        after = change.get("after") or {}
        if not isinstance(before, dict) or not isinstance(after, dict):
            return []
        return [k for k in set(list(before.keys()) + list(after.keys()))
                if before.get(k) != after.get(k)]

    @staticmethod
    def _assess_severity(
        rtype: str,
        drift_type: DriftType,
        actions: List[str],
        changed_attrs: List[str],
    ) -> DriftSeverity:
        # Destructive on stateful = critical
        if rtype in _CRITICAL_TYPES and drift_type in (DriftType.DELETED, DriftType.CHANGED):
            if "delete" in actions:
                return DriftSeverity.CRITICAL
            return DriftSeverity.HIGH

        if rtype in _HIGH_TYPES:
            if "delete" in actions:
                return DriftSeverity.HIGH
            return DriftSeverity.MEDIUM

        if drift_type == DriftType.DELETED:
            return DriftSeverity.MEDIUM

        return DriftSeverity.LOW

    @staticmethod
    def _build_detail(actions: List[str], changed_attrs: List[str]) -> str:
        parts = [f"actions={actions}"]
        if changed_attrs:
            parts.append(f"changed={changed_attrs[:5]}")
        return "; ".join(parts)

    @staticmethod
    def _is_tf_root(path: str) -> bool:
        """Check if directory looks like a terraform root module."""
        for ext in ("*.tf", "*.tf.json"):
            import glob
            if glob.glob(os.path.join(path, ext)):
                return True
        return False

    @staticmethod
    def _extract_tags(resource_change: dict) -> dict:
        """Extract tags from a resource_change entry.

        Tags can appear in:
        - change.before.tags / change.after.tags
        - change.before.tags_all / change.after.tags_all
        """
        change = resource_change.get("change", {})
        # Prefer 'after' (current cloud state), fall back to 'before'
        for state_key in ("after", "before"):
            state = change.get(state_key)
            if not isinstance(state, dict):
                continue
            for tag_key in ("tags", "tags_all"):
                tags = state.get(tag_key)
                if isinstance(tags, dict) and tags:
                    return {str(k): str(v) for k, v in tags.items()}
        return {}

    @staticmethod
    def _apply_tag_filter(summary: DriftSummary, filter_tags: dict) -> None:
        """Remove drifted resources that don't match ALL filter tags.

        Resources with no tags are excluded when a filter is active.
        Total resource counts are adjusted to reflect the filtered scope.
        """
        for result in summary.results:
            filtered = []
            for r in result.drifted_resources:
                if _matches_tags(r.tags, filter_tags):
                    filtered.append(r)
            excluded = len(result.drifted_resources) - len(filtered)
            result.drifted_resources = filtered
            if excluded and result.total_resources > 0:
                result.total_resources = max(result.total_resources - excluded, len(filtered))
            # Recalculate coverage
            total = result.total_resources
            drifted = len(result.drifted_resources)
            result.coverage_pct = round(((total - drifted) / total) * 100, 1) if total else 100.0


def _matches_tags(resource_tags: dict, filter_tags: dict) -> bool:
    """Return True if resource_tags contain ALL filter_tags (key=value).

    Supports:
      - Exact match:  env=prod
      - Wildcard value: env=*  (key must exist, any value)
      - Key-only: team (key must exist, shorthand for team=*)
    """
    if not filter_tags:
        return True
    if not resource_tags:
        return False
    for key, value in filter_tags.items():
        if key not in resource_tags:
            return False
        if value not in ("*", ""):
            if resource_tags[key] != value:
                return False
    return True
