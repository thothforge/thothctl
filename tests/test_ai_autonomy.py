"""Unit tests for the agent autonomy model (Phase 2.5.1)."""

import pytest

from thothctl.services.ai_review.config.autonomy import (
    ACTION_MIN_LEVEL,
    AutonomyConfig,
    AutonomyLevel,
)
from thothctl.services.ai_review.config.decision_rules import SafetyConfig
from thothctl.services.ai_review.safety.safety_guard import SafetyGuard


@pytest.fixture
def default_config():
    return AutonomyConfig.default()


class TestDefaults:
    def test_default_has_four_levels(self, default_config):
        assert set(default_config.levels.keys()) == {1, 2, 3, 4}

    def test_default_level_is_one(self, default_config):
        assert default_config.default_level == 1

    def test_level_one_is_read_only(self, default_config):
        lvl = default_config.levels[1]
        assert lvl.name == "suggest"
        assert lvl.is_tool_allowed("scan") is True
        assert lvl.is_tool_allowed("write-file") is False


class TestLevelResolution:
    def test_resolve_by_name(self, default_config):
        assert default_config.resolve_level("draft").level == 2

    def test_resolve_by_number(self, default_config):
        assert default_config.resolve_level(3).level == 3

    def test_resolve_by_numeric_string(self, default_config):
        assert default_config.resolve_level("4").level == 4

    def test_resolve_none_uses_default(self, default_config):
        assert default_config.resolve_level(None).level == 1

    def test_resolve_unknown_falls_back_to_default(self, default_config):
        assert default_config.resolve_level("bogus").level == 1

    def test_resolve_out_of_range_falls_back(self, default_config):
        assert default_config.resolve_level(9).level == 1


class TestToolAllowDeny:
    def test_explicit_allow(self):
        lvl = AutonomyLevel(level=2, name="draft", allowed_tools=["write-file"])
        assert lvl.is_tool_allowed("write-file") is True

    def test_not_in_allow_list(self):
        lvl = AutonomyLevel(level=2, name="draft", allowed_tools=["write-file"])
        assert lvl.is_tool_allowed("terraform-apply") is False

    def test_wildcard_allows_all(self):
        lvl = AutonomyLevel(level=3, name="validate", allowed_tools=["*"])
        assert lvl.is_tool_allowed("anything") is True

    def test_deny_beats_allow_explicit(self):
        lvl = AutonomyLevel(
            level=2,
            name="draft",
            allowed_tools=["terraform-apply"],
            denied_tools=["terraform-apply"],
        )
        assert lvl.is_tool_allowed("terraform-apply") is False

    def test_deny_beats_wildcard(self):
        lvl = AutonomyLevel(
            level=3,
            name="validate",
            allowed_tools=["*"],
            denied_tools=["terraform-destroy"],
        )
        assert lvl.is_tool_allowed("terraform-destroy") is False
        assert lvl.is_tool_allowed("scan") is True


class TestActionGating:
    def test_readonly_allowed_at_level_one(self, default_config):
        lvl = default_config.levels[1]
        ok, _ = default_config.is_action_allowed("analyze", lvl)
        assert ok is True

    def test_approve_blocked_at_level_one(self, default_config):
        lvl = default_config.levels[1]
        ok, reason = default_config.is_action_allowed("approve", lvl)
        assert ok is False
        assert "requires autonomy level 2" in reason

    def test_approve_allowed_at_level_two(self, default_config):
        lvl = default_config.levels[2]
        ok, _ = default_config.is_action_allowed("approve", lvl)
        assert ok is True

    def test_apply_blocked_below_level_four(self, default_config):
        for n in (1, 2, 3):
            ok, _ = default_config.is_action_allowed("apply", default_config.levels[n])
            assert ok is False
        ok, _ = default_config.is_action_allowed("apply", default_config.levels[4])
        assert ok is True

    def test_unknown_action_requires_highest_level(self, default_config):
        assert "mystery" not in ACTION_MIN_LEVEL
        ok, _ = default_config.is_action_allowed("mystery", default_config.levels[3])
        assert ok is False
        ok, _ = default_config.is_action_allowed("mystery", default_config.levels[4])
        assert ok is True


class TestConfigLoading:
    def test_missing_file_uses_defaults(self, tmp_path):
        cfg = AutonomyConfig.load(str(tmp_path))
        assert cfg.default_level == 1
        assert set(cfg.levels.keys()) == {1, 2, 3, 4}

    def test_load_custom_config(self, tmp_path):
        (tmp_path / ".thothcf.toml").write_text(
            "[agent.autonomy]\n"
            "default_level = 2\n"
            "[agent.autonomy.levels.2]\n"
            'allowed_tools = ["read-file", "write-file"]\n'
            'denied_tools = ["terraform-apply"]\n'
        )
        cfg = AutonomyConfig.load(str(tmp_path))
        assert cfg.default_level == 2
        lvl2 = cfg.levels[2]
        assert lvl2.is_tool_allowed("write-file") is True
        assert lvl2.is_tool_allowed("terraform-apply") is False

    def test_malformed_toml_falls_back_safe(self, tmp_path):
        (tmp_path / ".thothcf.toml").write_text("this is = = not valid toml [[[")
        cfg = AutonomyConfig.load(str(tmp_path))
        # No escalation: default level stays 1
        assert cfg.default_level == 1
        assert set(cfg.levels.keys()) == {1, 2, 3, 4}

    def test_invalid_default_level_falls_back_to_one(self, tmp_path):
        (tmp_path / ".thothcf.toml").write_text(
            "[agent.autonomy]\ndefault_level = 99\n"
        )
        cfg = AutonomyConfig.load(str(tmp_path))
        assert cfg.default_level == 1


class TestSafetyGuardIntegration:
    @pytest.fixture(autouse=True)
    def _isolate_logs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "thothctl.services.ai_review.safety.safety_guard.ACTIONS_LOG_DIR",
            str(tmp_path / "ai_decisions"),
        )

    def test_no_autonomy_is_backward_compatible(self):
        guard = SafetyGuard(SafetyConfig())
        ok, reason = guard.check_autonomy("approve")
        assert ok is True
        assert "No autonomy restriction" in reason

    def test_level_one_blocks_approve(self):
        cfg = AutonomyConfig.default()
        guard = SafetyGuard(SafetyConfig(), autonomy_level=cfg.levels[1])
        ok, reason = guard.can_take_action("approve", 0.99, "test/repo")
        assert ok is False
        assert "requires autonomy level 2" in reason

    def test_level_two_passes_autonomy_gate(self):
        cfg = AutonomyConfig.default()
        guard = SafetyGuard(SafetyConfig(), autonomy_level=cfg.levels[2])
        # Autonomy gate passes; then normal checks apply (high confidence, fresh repo)
        ok, reason = guard.can_take_action("approve", 0.99, "fresh/repo")
        assert ok is True
        assert "All safety checks passed" in reason

    def test_autonomy_gate_runs_before_confidence(self):
        # At level 1, even a perfectly confident approve is blocked by autonomy,
        # and the reason is the autonomy reason, not a confidence reason.
        cfg = AutonomyConfig.default()
        guard = SafetyGuard(SafetyConfig(), autonomy_level=cfg.levels[1])
        ok, reason = guard.can_take_action("approve", 1.0, "test/repo")
        assert ok is False
        assert "autonomy level" in reason
