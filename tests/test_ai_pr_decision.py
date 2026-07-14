"""Unit tests for PRDecisionPublisher and format_decision_comment."""

import os
import pytest
from unittest.mock import patch, Mock

from thothctl.services.ai_review.pr_decision_publisher import (
    PRDecisionPublisher, format_decision_comment,
)
from thothctl.services.ai_review.decision_engine import Decision, DecisionResult


def _make_result(decision=Decision.APPROVE, confidence=0.95, risk_score=10,
                 reason="low risk", findings=None):
    return DecisionResult(
        decision=decision,
        confidence=confidence,
        risk_score=risk_score,
        reason=reason,
        findings_summary=findings or {"critical": 0, "high": 0, "medium": 0, "low": 0},
        recommendations=["No issues found."],
    )


class TestFormatDecisionComment:
    def test_approve_comment(self):
        result = _make_result(Decision.APPROVE)
        comment = format_decision_comment(result, {})
        assert "APPROVE" in comment
        assert "✅" in comment
        assert "95%" in comment

    def test_reject_comment(self):
        result = _make_result(Decision.REJECT, confidence=0.90, risk_score=90,
                              reason="critical issues",
                              findings={"critical": 2, "high": 3, "medium": 0, "low": 0})
        comment = format_decision_comment(result, {})
        assert "REJECT" in comment
        assert "🚫" in comment
        assert "Critical" in comment

    def test_request_changes_comment(self):
        result = _make_result(Decision.REQUEST_CHANGES, reason="medium risk")
        comment = format_decision_comment(result, {})
        assert "REQUEST_CHANGES" in comment
        assert "🔄" in comment

    def test_comment_includes_recommendations(self):
        result = _make_result()
        result.recommendations = ["Enable encryption", "Add logging"]
        comment = format_decision_comment(result, {})
        assert "Enable encryption" in comment
        assert "Add logging" in comment

    def test_safety_blocked_comment(self):
        result = _make_result()
        result.blocked_by_safety = True
        result.safety_reason = "Rate limit exceeded"
        comment = format_decision_comment(result, {})
        assert "Safety" in comment or "Rate limit" in comment

    def test_comment_has_thothctl_footer(self):
        result = _make_result()
        comment = format_decision_comment(result, {})
        assert "ThothCTL" in comment


class TestPRDecisionPublisher:
    def test_auto_detect_github(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_TOKEN": "fake"}, clear=False):
            env = os.environ.copy()
            env.pop("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI", None)
            with patch.dict(os.environ, env, clear=True):
                with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_TOKEN": "fake"}):
                    pub = PRDecisionPublisher(platform="auto")
                    assert pub.platform == "github"

    def test_explicit_platform(self):
        pub = PRDecisionPublisher(platform="github")
        assert pub.platform == "github"

    def test_publish_without_token_returns_error(self):
        pub = PRDecisionPublisher(platform="github")
        pub._github_token = None
        result = _make_result()
        response = pub.publish(result, {}, "owner/repo", "1")
        assert "error" in response
