"""Core decision engine — determines approve/reject/request-changes/comment."""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional

from .config.decision_rules import DecisionRules, BLOCKING_PATTERNS
from .safety.safety_guard import SafetyGuard

logger = logging.getLogger(__name__)


class Decision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    COMMENT = "comment"


@dataclass
class DecisionResult:
    decision: Decision
    confidence: float
    reason: str
    risk_score: float
    findings_summary: Dict[str, int]
    recommendations: List[str]
    blocked_by_safety: bool = False
    safety_reason: str = ""


class DecisionEngine:
    """Evaluates AI analysis results and determines the PR action."""

    def __init__(self, rules: Optional[DecisionRules] = None):
        self.rules = rules or DecisionRules.load()
        self.safety = SafetyGuard(self.rules.safety)

    def evaluate(self, analysis: Dict[str, Any],
                 repository: str = "", pr_id: str = "",
                 pr_context: Optional[Dict] = None) -> DecisionResult:
        """Evaluate analysis results and return a decision."""
        summary = analysis.get("summary", {})
        risk_score = float(analysis.get("risk_score", 50))
        findings = analysis.get("findings", [])
        recommendations = analysis.get("recommendations", [])

        critical = summary.get("critical", 0)
        high = summary.get("high", 0)
        medium = summary.get("medium", 0)
        low = summary.get("low", 0)

        findings_summary = {"critical": critical, "high": high, "medium": medium, "low": low}

        # Check for blocking patterns in findings
        has_blocking = self._has_blocking_patterns(findings)

        # Determine raw decision
        decision, confidence, reason = self._compute_decision(
            risk_score, critical, high, medium, has_blocking, findings,
        )

        # Safety gate
        if decision != Decision.COMMENT and repository:
            allowed, safety_reason = self.safety.can_take_action(
                decision.value, confidence, repository, pr_context,
            )
            if not allowed:
                return DecisionResult(
                    decision=Decision.COMMENT,
                    confidence=confidence,
                    reason=reason,
                    risk_score=risk_score,
                    findings_summary=findings_summary,
                    recommendations=recommendations,
                    blocked_by_safety=True,
                    safety_reason=safety_reason,
                )

        # Record if taking action
        if decision != Decision.COMMENT and repository:
            self.safety.record_action(
                action=decision.value, repository=repository,
                pr_id=pr_id, confidence=confidence, reason=reason,
            )

        return DecisionResult(
            decision=decision,
            confidence=confidence,
            reason=reason,
            risk_score=risk_score,
            findings_summary=findings_summary,
            recommendations=recommendations,
        )

    def _compute_decision(self, risk_score: float, critical: int, high: int,
                          medium: int, has_blocking: bool,
                          findings: List[Dict]) -> tuple:
        """Pure decision logic without safety checks."""
        r = self.rules

        # Auto-reject
        if (risk_score >= r.reject.risk_score_min
                or critical >= r.reject.critical_issues_min
                or has_blocking):
            confidence = min(0.99, 0.80 + (risk_score / 500) + (critical * 0.05))
            reasons = []
            if risk_score >= r.reject.risk_score_min:
                reasons.append(f"risk score {risk_score:.0f} ≥ {r.reject.risk_score_min}")
            if critical >= r.reject.critical_issues_min:
                reasons.append(f"{critical} critical issue(s)")
            if has_blocking:
                reasons.append("blocking security pattern detected")
            return Decision.REJECT, confidence, "; ".join(reasons)

        # Auto-approve
        if (risk_score <= r.approve.risk_score_max
                and critical <= r.approve.critical_issues_max
                and high <= r.approve.high_issues_max
                and medium <= r.approve.medium_issues_max):
            confidence = min(0.99, 0.85 + ((r.approve.risk_score_max - risk_score) / 200))
            return Decision.APPROVE, confidence, f"risk score {risk_score:.0f} ≤ {r.approve.risk_score_max}, no critical/high issues"

        # Request changes (middle ground)
        total_fixable = sum(1 for f in findings if f.get("remediation"))
        total = len(findings) or 1
        fixable_ratio = total_fixable / total

        confidence = min(0.95, 0.75 + (fixable_ratio * 0.15))
        reason = (f"risk score {risk_score:.0f} (range {r.approve.risk_score_max+1}-{r.reject.risk_score_min-1}), "
                  f"{high} high, {medium} medium, {fixable_ratio:.0%} fixable")
        return Decision.REQUEST_CHANGES, confidence, reason

    def _has_blocking_patterns(self, findings: List[Dict]) -> bool:
        """Check if any finding matches a blocking pattern."""
        for f in findings:
            title = (f.get("title", "") + " " + f.get("id", "")).lower()
            for pattern in self.rules.blocking_patterns:
                if pattern.replace("_", " ") in title or pattern.replace("_", "") in title:
                    return True
        return False
