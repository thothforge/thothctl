"""Policy-based drift response engine.

Reads `.driftpolicy` YAML files to codify per-resource drift tolerance:

```yaml
# .driftpolicy
coverage_threshold: 90.0

rules:
  - resource: "aws_security_group.*"
    severity_override: critical
    action: block_deploy

  - resource: "aws_instance.*"
    attribute: "tags.*"
    action: auto_accept

  - resource: "aws_db_instance.*"
    action: alert

  - resource: "aws_cloudwatch_log_group.*"
    action: ignore
```

Actions:
  block_deploy  — fail CI, prevent deployment until drift is resolved
  alert         — warn but allow deployment
  auto_accept   — silently accept the drift (e.g. tag-only changes)
  ignore        — remove from report entirely
"""
import fnmatch
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DriftAction(Enum):
    BLOCK_DEPLOY = "block_deploy"
    ALERT = "alert"
    AUTO_ACCEPT = "auto_accept"
    IGNORE = "ignore"


@dataclass
class PolicyRule:
    resource: str  # glob pattern
    action: DriftAction
    attribute: Optional[str] = None  # optional attribute glob
    severity_override: Optional[str] = None


@dataclass
class DriftPolicy:
    coverage_threshold: float = 90.0
    rules: List[PolicyRule] = field(default_factory=list)


@dataclass
class PolicyVerdict:
    """Result of evaluating a single drifted resource against policy."""
    address: str
    action: DriftAction
    matched_rule: Optional[str] = None
    severity_override: Optional[str] = None


@dataclass
class PolicyEvaluation:
    """Result of evaluating an entire drift summary against policy."""
    verdicts: List[PolicyVerdict] = field(default_factory=list)
    blocked: bool = False
    coverage_violation: bool = False
    coverage_pct: float = 100.0
    coverage_threshold: float = 90.0

    @property
    def block_reasons(self) -> List[str]:
        reasons = []
        if self.coverage_violation:
            reasons.append(
                f"IaC coverage ({self.coverage_pct}%) below threshold ({self.coverage_threshold}%)"
            )
        for v in self.verdicts:
            if v.action == DriftAction.BLOCK_DEPLOY:
                reasons.append(f"Policy blocks deployment for: {v.address} (rule: {v.matched_rule})")
        return reasons

    @property
    def ignored_addresses(self) -> List[str]:
        return [v.address for v in self.verdicts if v.action == DriftAction.IGNORE]

    @property
    def accepted_addresses(self) -> List[str]:
        return [v.address for v in self.verdicts if v.action == DriftAction.AUTO_ACCEPT]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blocked": self.blocked,
            "block_reasons": self.block_reasons,
            "coverage_violation": self.coverage_violation,
            "coverage_pct": self.coverage_pct,
            "coverage_threshold": self.coverage_threshold,
            "ignored": self.ignored_addresses,
            "auto_accepted": self.accepted_addresses,
            "verdicts": [
                {"address": v.address, "action": v.action.value, "rule": v.matched_rule}
                for v in self.verdicts
            ],
        }


class DriftPolicyEngine:
    """Evaluate drift results against a .driftpolicy file."""

    def __init__(self, policy: DriftPolicy = None):
        self.policy = policy or DriftPolicy()

    @classmethod
    def load(cls, directory: str) -> "DriftPolicyEngine":
        """Load .driftpolicy from directory. Returns engine with defaults if not found."""
        policy_path = Path(directory) / ".driftpolicy"
        if not policy_path.exists():
            return cls()
        try:
            import yaml
            data = yaml.safe_load(policy_path.read_text()) or {}
        except ImportError:
            # Fallback: try JSON
            import json
            try:
                data = json.loads(policy_path.read_text())
            except Exception:
                logger.warning(f"Cannot parse {policy_path} (install PyYAML for YAML support)")
                return cls()
        except Exception as e:
            logger.warning(f"Failed to load {policy_path}: {e}")
            return cls()

        policy = DriftPolicy(
            coverage_threshold=data.get("coverage_threshold", 90.0),
        )
        for rule_data in data.get("rules", []):
            try:
                policy.rules.append(PolicyRule(
                    resource=rule_data["resource"],
                    action=DriftAction(rule_data.get("action", "alert")),
                    attribute=rule_data.get("attribute"),
                    severity_override=rule_data.get("severity_override"),
                ))
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping invalid policy rule: {e}")
        return cls(policy)

    def evaluate(self, summary_dict: Dict[str, Any]) -> PolicyEvaluation:
        """Evaluate a DriftSummary.to_dict() against the loaded policy."""
        evaluation = PolicyEvaluation(
            coverage_pct=summary_dict.get("overall_coverage", 100.0),
            coverage_threshold=self.policy.coverage_threshold,
        )

        # Coverage check
        if evaluation.coverage_pct < self.policy.coverage_threshold:
            evaluation.coverage_violation = True
            evaluation.blocked = True

        # Per-resource evaluation
        for result in summary_dict.get("results", []):
            for resource in result.get("drifted_resources", []):
                verdict = self._evaluate_resource(resource)
                evaluation.verdicts.append(verdict)
                if verdict.action == DriftAction.BLOCK_DEPLOY:
                    evaluation.blocked = True

        return evaluation

    def _evaluate_resource(self, resource: Dict[str, Any]) -> PolicyVerdict:
        """Match a drifted resource against policy rules. First match wins."""
        address = resource.get("address", "")
        changed_attrs = resource.get("changed_attributes", [])

        for rule in self.policy.rules:
            if not fnmatch.fnmatch(address, rule.resource):
                continue

            # If rule has attribute filter, check it
            if rule.attribute:
                if not any(fnmatch.fnmatch(a, rule.attribute) for a in changed_attrs):
                    continue

            return PolicyVerdict(
                address=address,
                action=rule.action,
                matched_rule=rule.resource,
                severity_override=rule.severity_override,
            )

        # Default: alert
        return PolicyVerdict(address=address, action=DriftAction.ALERT)
