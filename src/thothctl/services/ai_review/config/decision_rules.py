"""Configurable decision rules for auto-approve/reject/request-changes."""
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILE = ".thothctl/ai_decision_config.yaml"


@dataclass
class ApproveThresholds:
    risk_score_max: int = 20
    confidence_min: float = 0.90
    critical_issues_max: int = 0
    high_issues_max: int = 0
    medium_issues_max: int = 2
    compliance_violations_max: int = 0


@dataclass
class RejectThresholds:
    risk_score_min: int = 85
    confidence_min: float = 0.85
    critical_issues_min: int = 1


@dataclass
class RequestChangesThresholds:
    confidence_min: float = 0.80
    fixable_ratio_min: float = 0.8


@dataclass
class SafetyConfig:
    max_auto_approvals_per_day: int = 50
    max_auto_rejections_per_day: int = 20
    cooldown_between_actions: int = 300
    emergency_labels: List[str] = field(default_factory=lambda: ["emergency", "hotfix", "security-patch"])
    trusted_bots: List[str] = field(default_factory=lambda: ["dependabot", "renovate"])
    bypass_approvers: List[str] = field(default_factory=list)


BLOCKING_PATTERNS = [
    "hardcoded_secrets",
    "public_s3_buckets",
    "unrestricted_security_groups",
    "admin_access_keys",
    "unencrypted_databases",
]


@dataclass
class DecisionRules:
    """Complete decision rules configuration."""
    enabled: bool = False
    approve: ApproveThresholds = field(default_factory=ApproveThresholds)
    reject: RejectThresholds = field(default_factory=RejectThresholds)
    request_changes: RequestChangesThresholds = field(default_factory=RequestChangesThresholds)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    blocking_patterns: List[str] = field(default_factory=lambda: list(BLOCKING_PATTERNS))

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "DecisionRules":
        rules = cls()
        path = Path(config_path) if config_path else Path(DEFAULT_CONFIG_FILE)

        if path.exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                d = data.get("ai_decision", data)
                rules.enabled = d.get("enabled", False)

                t = d.get("thresholds", {})
                if "auto_approve" in t:
                    rules.approve = ApproveThresholds(**t["auto_approve"])
                if "auto_reject" in t:
                    rules.reject = RejectThresholds(**t["auto_reject"])
                if "request_changes" in t:
                    rules.request_changes = RequestChangesThresholds(**t["request_changes"])

                s = d.get("safety", {}).get("rate_limits", {})
                o = d.get("safety", {}).get("overrides", {})
                if s or o:
                    rules.safety = SafetyConfig(**{**s, **o})
            except Exception as e:
                logger.warning(f"Error loading decision config from {path}: {e}")

        return rules

    def save(self, config_path: Optional[str] = None) -> None:
        path = Path(config_path) if config_path else Path(DEFAULT_CONFIG_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "ai_decision": {
                "enabled": self.enabled,
                "thresholds": {
                    "auto_approve": vars(self.approve),
                    "auto_reject": vars(self.reject),
                    "request_changes": vars(self.request_changes),
                },
                "safety": {
                    "rate_limits": {
                        "max_auto_approvals_per_day": self.safety.max_auto_approvals_per_day,
                        "max_auto_rejections_per_day": self.safety.max_auto_rejections_per_day,
                        "cooldown_between_actions": self.safety.cooldown_between_actions,
                    },
                    "overrides": {
                        "emergency_labels": self.safety.emergency_labels,
                        "trusted_bots": self.safety.trusted_bots,
                        "bypass_approvers": self.safety.bypass_approvers,
                    },
                },
            }
        }
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
