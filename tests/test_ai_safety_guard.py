"""Unit tests for SafetyGuard — confidence, rate limits, overrides."""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch

from thothctl.services.ai_review.safety.safety_guard import SafetyGuard, ActionRecord
from thothctl.services.ai_review.config.decision_rules import SafetyConfig


@pytest.fixture
def safety(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "thothctl.services.ai_review.safety.safety_guard.ACTIONS_LOG_DIR",
        str(tmp_path / "ai_decisions"),
    )
    return SafetyGuard(SafetyConfig())


class TestConfidence:
    def test_approve_meets_threshold(self, safety):
        ok, _ = safety.check_confidence("approve", 0.92)
        assert ok is True

    def test_approve_below_threshold(self, safety):
        ok, reason = safety.check_confidence("approve", 0.80)
        assert ok is False
        assert "below threshold" in reason

    def test_reject_meets_threshold(self, safety):
        ok, _ = safety.check_confidence("reject", 0.87)
        assert ok is True

    def test_reject_below_threshold(self, safety):
        ok, _ = safety.check_confidence("reject", 0.70)
        assert ok is False

    def test_unknown_action_high_threshold(self, safety):
        ok, _ = safety.check_confidence("unknown_action", 0.94)
        assert ok is False  # requires 0.95


class TestRateLimit:
    def test_within_limits(self, safety):
        ok, _ = safety.check_rate_limit("approve", "test/repo")
        assert ok is True

    def test_cooldown_enforced(self, safety):
        safety.record_action("approve", "test/repo", "1", 0.95, "test")
        ok, reason = safety.check_rate_limit("approve", "test/repo")
        assert ok is False
        assert "Cooldown" in reason


class TestOverride:
    def test_emergency_label(self, safety):
        overridden, reason = safety.check_override({"labels": ["emergency"]})
        assert overridden is True
        assert "Emergency" in reason

    def test_hotfix_label(self, safety):
        overridden, _ = safety.check_override({"labels": ["hotfix"]})
        assert overridden is True

    def test_trusted_bot(self, safety):
        overridden, reason = safety.check_override({"author": "dependabot"})
        assert overridden is True
        assert "Trusted bot" in reason

    def test_no_override(self, safety):
        overridden, _ = safety.check_override({"labels": [], "author": "human"})
        assert overridden is False

    def test_bypass_approver(self, safety):
        config = SafetyConfig(bypass_approvers=["admin-user"])
        guard = SafetyGuard(config)
        overridden, _ = guard.check_override({"approvers": ["admin-user"]})
        assert overridden is True


class TestCanTakeAction:
    def test_all_checks_pass(self, safety):
        ok, reason = safety.can_take_action("approve", 0.95, "test/repo")
        assert ok is True
        assert "All safety checks passed" in reason

    def test_low_confidence_blocks(self, safety):
        ok, reason = safety.can_take_action("approve", 0.50, "test/repo")
        assert ok is False
        assert "below threshold" in reason

    def test_override_blocks(self, safety):
        ok, reason = safety.can_take_action(
            "approve", 0.95, "test/repo",
            pr_context={"labels": ["emergency"]},
        )
        assert ok is False
        assert "Override active" in reason


class TestPersistence:
    def test_record_and_stats(self, safety):
        safety.record_action("approve", "test/repo", "42", 0.95, "low risk")
        stats = safety.get_today_stats()
        assert stats["total"] == 1
        assert stats["actions"]["approve"] == 1

    def test_records_persist_to_file(self, safety, tmp_path):
        safety.record_action("reject", "test/repo", "99", 0.90, "high risk")
        from datetime import date
        log_file = tmp_path / "ai_decisions" / f"{date.today().isoformat()}.jsonl"
        assert log_file.exists()
        record = json.loads(log_file.read_text().strip())
        assert record["action"] == "reject"
        assert record["pr_id"] == "99"
