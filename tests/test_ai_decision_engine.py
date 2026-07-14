"""Unit tests for DecisionEngine, DecisionRules, and Decision types."""

import pytest
from thothctl.services.ai_review.decision_engine import (
    DecisionEngine, Decision, DecisionResult,
)
from thothctl.services.ai_review.config.decision_rules import (
    DecisionRules, ApproveThresholds, RejectThresholds,
    RequestChangesThresholds, SafetyConfig,
)


class TestDecision:
    def test_enum_values(self):
        assert Decision.APPROVE.value == "approve"
        assert Decision.REJECT.value == "reject"
        assert Decision.REQUEST_CHANGES.value == "request_changes"
        assert Decision.COMMENT.value == "comment"


class TestDecisionRules:
    def test_defaults(self):
        rules = DecisionRules()
        assert rules.enabled is False
        assert rules.approve.risk_score_max == 20
        assert rules.reject.risk_score_min == 85
        assert rules.reject.critical_issues_min == 1

    def test_load_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rules = DecisionRules.load()
        assert isinstance(rules, DecisionRules)
        assert rules.enabled is False

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rules = DecisionRules()
        rules.enabled = True
        rules.approve.risk_score_max = 30
        rules.save()
        loaded = DecisionRules.load()
        assert loaded.enabled is True
        assert loaded.approve.risk_score_max == 30


class TestDecisionEngine:
    def _make_analysis(self, risk_score=0, critical=0, high=0, medium=0, low=0,
                       findings=None, recommendations=None):
        return {
            "risk_score": risk_score,
            "summary": {"critical": critical, "high": high, "medium": medium, "low": low},
            "findings": findings or [],
            "recommendations": recommendations or [],
        }

    def test_approve_low_risk(self):
        engine = DecisionEngine()
        result = engine.evaluate(self._make_analysis(risk_score=5))
        assert result.decision == Decision.APPROVE
        assert result.confidence >= 0.85
        assert result.risk_score == 5

    def test_approve_zero_findings(self):
        engine = DecisionEngine()
        result = engine.evaluate(self._make_analysis(risk_score=0))
        assert result.decision == Decision.APPROVE

    def test_reject_high_risk(self):
        engine = DecisionEngine()
        result = engine.evaluate(self._make_analysis(risk_score=90, critical=2, high=5))
        assert result.decision == Decision.REJECT
        assert result.confidence >= 0.85

    def test_reject_critical_issues(self):
        engine = DecisionEngine()
        result = engine.evaluate(self._make_analysis(risk_score=50, critical=1))
        assert result.decision == Decision.REJECT

    def test_request_changes_medium_risk(self):
        engine = DecisionEngine()
        findings = [{"remediation": "fix it"}, {"remediation": "fix that"}]
        result = engine.evaluate(self._make_analysis(
            risk_score=50, high=2, medium=5, findings=findings,
        ))
        assert result.decision == Decision.REQUEST_CHANGES

    def test_blocking_pattern_triggers_reject(self):
        engine = DecisionEngine()
        findings = [{"title": "hardcoded secrets detected", "id": "CKV_SECRET_1"}]
        result = engine.evaluate(self._make_analysis(
            risk_score=30, findings=findings,
        ))
        assert result.decision == Decision.REJECT

    def test_decision_result_fields(self):
        engine = DecisionEngine()
        result = engine.evaluate(self._make_analysis(risk_score=10))
        assert isinstance(result, DecisionResult)
        assert isinstance(result.findings_summary, dict)
        assert "critical" in result.findings_summary
        assert isinstance(result.reason, str)
        assert result.blocked_by_safety is False

    def test_custom_rules(self):
        rules = DecisionRules()
        rules.approve.risk_score_max = 50  # Very permissive
        engine = DecisionEngine(rules)
        result = engine.evaluate(self._make_analysis(risk_score=40, high=0))
        assert result.decision == Decision.APPROVE

    def test_safety_blocks_action_when_override(self):
        engine = DecisionEngine()
        pr_context = {"labels": ["emergency"]}
        result = engine.evaluate(
            self._make_analysis(risk_score=10),
            repository="test/repo", pr_id="1", pr_context=pr_context,
        )
        # Emergency label → override → falls back to COMMENT
        assert result.decision == Decision.COMMENT
        assert result.blocked_by_safety is True
