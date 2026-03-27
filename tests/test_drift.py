"""Tests for drift detection feature."""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from thothctl.services.check.project.drift.models import (
    DriftedResource, DriftResult, DriftSeverity, DriftSummary, DriftType,
)
from thothctl.services.check.project.drift.drift_service import (
    DriftDetectionService, _matches_tags,
)
from thothctl.services.check.project.drift.drift_policy import (
    DriftAction, DriftPolicy, DriftPolicyEngine, PolicyRule,
)
from thothctl.services.check.project.drift.drift_history import DriftHistory
from thothctl.services.check.project.drift.drift_report import DriftReportGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_plan(resource_changes):
    """Build a minimal tfplan.json dict."""
    return {"resource_changes": resource_changes}


def _rc(address, rtype, actions, before=None, after=None, tags=None):
    """Shorthand to build a resource_change entry."""
    change = {"actions": actions, "before": before or {}, "after": after or {}}
    if tags:
        change["after"]["tags"] = tags
    return {"address": address, "type": rtype, "change": change}


@pytest.fixture
def service():
    return DriftDetectionService(tftool="tofu")


@pytest.fixture
def plan_no_drift():
    return _make_plan([
        _rc("aws_s3_bucket.a", "aws_s3_bucket", ["no-op"]),
        _rc("aws_instance.b", "aws_instance", ["no-op"]),
    ])


@pytest.fixture
def plan_with_drift():
    return _make_plan([
        _rc("aws_s3_bucket.main", "aws_s3_bucket", ["no-op"]),
        _rc("aws_instance.web", "aws_instance", ["update"],
            before={"instance_type": "t3.micro"}, after={"instance_type": "t3.large"}),
        _rc("aws_db_instance.primary", "aws_db_instance", ["delete", "create"],
            before={"engine": "mysql"}, after={"engine": "postgres"}),
        _rc("aws_security_group.allow_ssh", "aws_security_group", ["update"],
            before={"ingress": []}, after={"ingress": ["0.0.0.0/0"]},
            tags={"env": "prod", "team": "platform"}),
        _rc("aws_cloudwatch_log_group.logs", "aws_cloudwatch_log_group", ["create"]),
    ])


@pytest.fixture
def summary_dict_with_drift():
    """Pre-built summary dict as returned by DriftSummary.to_dict()."""
    return {
        "total_stacks": 1,
        "total_resources": 5,
        "total_drifted": 4,
        "overall_coverage": 20.0,
        "has_drift": True,
        "results": [{
            "directory": "/tmp/tf",
            "total_resources": 5,
            "drifted_resources": [
                {"address": "aws_instance.web", "resource_type": "aws_instance",
                 "drift_type": "changed", "severity": "low",
                 "changed_attributes": ["instance_type"], "actions": ["update"],
                 "detail": "", "tags": {}},
                {"address": "aws_db_instance.primary", "resource_type": "aws_db_instance",
                 "drift_type": "changed", "severity": "critical",
                 "changed_attributes": ["engine"], "actions": ["delete", "create"],
                 "detail": "", "tags": {}},
                {"address": "aws_security_group.allow_ssh", "resource_type": "aws_security_group",
                 "drift_type": "changed", "severity": "medium",
                 "changed_attributes": ["ingress"], "actions": ["update"],
                 "detail": "", "tags": {"env": "prod"}},
                {"address": "aws_cloudwatch_log_group.logs", "resource_type": "aws_cloudwatch_log_group",
                 "drift_type": "unmanaged", "severity": "low",
                 "changed_attributes": [], "actions": ["create"],
                 "detail": "", "tags": {}},
            ],
            "coverage_pct": 20.0,
            "has_drift": True,
            "severity_counts": {"critical": 1, "high": 0, "medium": 1, "low": 2},
            "error": None,
        }],
    }


# ===================================================================
# Models
# ===================================================================

class TestModels:
    def test_drift_result_no_drift(self):
        r = DriftResult(directory="/tmp")
        assert not r.has_drift
        assert r.coverage_pct == 100.0
        assert r.severity_counts == {"critical": 0, "high": 0, "medium": 0, "low": 0}

    def test_drift_result_with_drift(self):
        r = DriftResult(
            directory="/tmp", total_resources=3,
            drifted_resources=[
                DriftedResource("a.b", "aws_instance", DriftType.CHANGED, DriftSeverity.LOW),
                DriftedResource("c.d", "aws_s3_bucket", DriftType.DELETED, DriftSeverity.CRITICAL),
            ],
            coverage_pct=33.3,
        )
        assert r.has_drift
        assert r.severity_counts["critical"] == 1
        assert r.severity_counts["low"] == 1

    def test_drift_result_to_dict(self):
        r = DriftResult(directory="/tmp", total_resources=1)
        d = r.to_dict()
        assert d["directory"] == "/tmp"
        assert d["has_drift"] is False

    def test_drift_summary_aggregation(self):
        s = DriftSummary(results=[
            DriftResult(directory="/a", total_resources=10, drifted_resources=[
                DriftedResource("x", "t", DriftType.CHANGED, DriftSeverity.LOW),
            ]),
            DriftResult(directory="/b", total_resources=5),
        ])
        assert s.total_resources == 15
        assert s.total_drifted == 1
        assert s.has_drift
        assert s.overall_coverage == 93.3

    def test_drift_summary_no_drift(self):
        s = DriftSummary(results=[DriftResult(directory="/a", total_resources=10)])
        assert not s.has_drift
        assert s.overall_coverage == 100.0

    def test_drift_summary_empty(self):
        s = DriftSummary()
        assert s.overall_coverage == 100.0
        assert s.total_resources == 0

    def test_drifted_resource_to_dict(self):
        r = DriftedResource("a.b", "aws_instance", DriftType.CHANGED, DriftSeverity.HIGH,
                            tags={"env": "prod"})
        d = r.to_dict()
        assert d["drift_type"] == "changed"
        assert d["severity"] == "high"
        assert d["tags"] == {"env": "prod"}


# ===================================================================
# DriftDetectionService — classify / severity / helpers
# ===================================================================

class TestClassifyDriftType:
    def test_update(self):
        assert DriftDetectionService._classify_drift_type(["update"]) == DriftType.CHANGED

    def test_delete_create_is_replace(self):
        assert DriftDetectionService._classify_drift_type(["delete", "create"]) == DriftType.CHANGED

    def test_delete(self):
        assert DriftDetectionService._classify_drift_type(["delete"]) == DriftType.DELETED

    def test_create(self):
        assert DriftDetectionService._classify_drift_type(["create"]) == DriftType.UNMANAGED

    def test_noop_returns_none(self):
        assert DriftDetectionService._classify_drift_type(["no-op"]) is None

    def test_read_returns_none(self):
        assert DriftDetectionService._classify_drift_type(["read"]) is None


class TestAssessSeverity:
    def test_critical_type_delete(self):
        sev = DriftDetectionService._assess_severity(
            "aws_db_instance", DriftType.DELETED, ["delete"], [])
        assert sev == DriftSeverity.CRITICAL

    def test_critical_type_update(self):
        sev = DriftDetectionService._assess_severity(
            "aws_s3_bucket", DriftType.CHANGED, ["update"], ["versioning"])
        assert sev == DriftSeverity.HIGH

    def test_high_type_delete(self):
        sev = DriftDetectionService._assess_severity(
            "aws_security_group", DriftType.DELETED, ["delete"], [])
        assert sev == DriftSeverity.HIGH

    def test_high_type_update(self):
        sev = DriftDetectionService._assess_severity(
            "aws_lambda_function", DriftType.CHANGED, ["update"], ["runtime"])
        assert sev == DriftSeverity.MEDIUM

    def test_generic_delete(self):
        sev = DriftDetectionService._assess_severity(
            "aws_route53_record", DriftType.DELETED, ["delete"], [])
        assert sev == DriftSeverity.MEDIUM

    def test_generic_update(self):
        sev = DriftDetectionService._assess_severity(
            "aws_route53_record", DriftType.CHANGED, ["update"], ["ttl"])
        assert sev == DriftSeverity.LOW


class TestExtractChangedAttrs:
    def test_diff(self):
        attrs = DriftDetectionService._extract_changed_attrs({
            "before": {"a": 1, "b": 2},
            "after": {"a": 1, "b": 3, "c": 4},
        })
        assert sorted(attrs) == ["b", "c"]

    def test_no_before(self):
        # before=None is treated as {}, so all 'after' keys are changed
        assert DriftDetectionService._extract_changed_attrs({"before": None, "after": {"a": 1}}) == ["a"]

    def test_empty(self):
        assert DriftDetectionService._extract_changed_attrs({}) == []


class TestExtractTags:
    def test_tags_from_after(self):
        tags = DriftDetectionService._extract_tags({
            "change": {"after": {"tags": {"env": "prod"}}, "before": {"tags": {"env": "dev"}}}
        })
        assert tags == {"env": "prod"}

    def test_tags_from_before_fallback(self):
        tags = DriftDetectionService._extract_tags({
            "change": {"after": {}, "before": {"tags": {"env": "dev"}}}
        })
        assert tags == {"env": "dev"}

    def test_tags_all(self):
        tags = DriftDetectionService._extract_tags({
            "change": {"after": {"tags_all": {"env": "staging"}}}
        })
        assert tags == {"env": "staging"}

    def test_no_tags(self):
        assert DriftDetectionService._extract_tags({"change": {"after": {}}}) == {}


class TestMatchesTags:
    def test_no_filter(self):
        assert _matches_tags({"env": "prod"}, {}) is True

    def test_no_resource_tags(self):
        assert _matches_tags({}, {"env": "prod"}) is False

    def test_exact_match(self):
        assert _matches_tags({"env": "prod"}, {"env": "prod"}) is True

    def test_exact_mismatch(self):
        assert _matches_tags({"env": "dev"}, {"env": "prod"}) is False

    def test_wildcard(self):
        assert _matches_tags({"env": "anything"}, {"env": "*"}) is True

    def test_missing_key(self):
        assert _matches_tags({"env": "prod"}, {"team": "platform"}) is False

    def test_multiple_filters(self):
        assert _matches_tags({"env": "prod", "team": "x"}, {"env": "prod", "team": "*"}) is True


# ===================================================================
# DriftDetectionService — plan analysis
# ===================================================================

class TestAnalysePlan:
    def test_no_drift(self, service, plan_no_drift):
        result = service._analyse_plan(plan_no_drift, "/tmp")
        assert not result.has_drift
        assert result.total_resources == 2
        assert result.coverage_pct == 100.0

    def test_with_drift(self, service, plan_with_drift):
        result = service._analyse_plan(plan_with_drift, "/tmp")
        assert result.has_drift
        assert result.total_resources == 5
        assert len(result.drifted_resources) == 4
        # db_instance replace → CRITICAL
        db = next(r for r in result.drifted_resources if "db_instance" in r.address)
        assert db.severity == DriftSeverity.CRITICAL
        assert db.drift_type == DriftType.CHANGED
        # security_group update → MEDIUM (high type, no delete)
        sg = next(r for r in result.drifted_resources if "security_group" in r.address)
        assert sg.severity == DriftSeverity.MEDIUM
        assert sg.tags == {"env": "prod", "team": "platform"}

    def test_driftignore(self, service, plan_with_drift, tmp_path):
        (tmp_path / ".driftignore").write_text("aws_instance.*\n# comment\naws_cloudwatch_*\n")
        result = service._analyse_plan(plan_with_drift, str(tmp_path))
        addresses = [r.address for r in result.drifted_resources]
        assert "aws_instance.web" not in addresses
        assert "aws_cloudwatch_log_group.logs" not in addresses
        assert "aws_db_instance.primary" in addresses

    def test_empty_plan(self, service):
        result = service._analyse_plan({"resource_changes": []}, "/tmp")
        assert not result.has_drift
        assert result.coverage_pct == 100.0


class TestDetectDriftFromPlan:
    def test_valid_plan_file(self, service, plan_with_drift, tmp_path):
        plan_path = tmp_path / "tfplan.json"
        plan_path.write_text(json.dumps(plan_with_drift))
        result = service.detect_drift_from_plan(str(plan_path))
        assert result.has_drift
        assert result.directory == str(tmp_path)

    def test_invalid_plan_file(self, service, tmp_path):
        bad = tmp_path / "tfplan.json"
        bad.write_text("not json")
        result = service.detect_drift_from_plan(str(bad))
        assert result.error is not None

    def test_missing_file(self, service):
        result = service.detect_drift_from_plan("/nonexistent/tfplan.json")
        assert result.error is not None


class TestDetectDrift:
    def test_with_plan_files(self, service, plan_no_drift, tmp_path):
        p = tmp_path / "tfplan.json"
        p.write_text(json.dumps(plan_no_drift))
        summary = service.detect_drift(str(tmp_path), plan_files=[str(p)])
        assert len(summary.results) == 1
        assert not summary.has_drift

    def test_tag_filter(self, service, plan_with_drift, tmp_path):
        p = tmp_path / "tfplan.json"
        p.write_text(json.dumps(plan_with_drift))
        summary = service.detect_drift(str(tmp_path), plan_files=[str(p)],
                                       filter_tags={"env": "prod"})
        # Only the security_group has env=prod tag
        for result in summary.results:
            for r in result.drifted_resources:
                assert r.tags.get("env") == "prod"


# ===================================================================
# DriftPolicyEngine
# ===================================================================

class TestDriftPolicy:
    def test_default_policy(self):
        engine = DriftPolicyEngine()
        assert engine.policy.coverage_threshold == 90.0
        assert engine.policy.rules == []

    def test_load_missing_file(self, tmp_path):
        engine = DriftPolicyEngine.load(str(tmp_path))
        assert engine.policy.coverage_threshold == 90.0

    def test_load_yaml(self, tmp_path):
        (tmp_path / ".driftpolicy").write_text(
            "coverage_threshold: 80.0\n"
            "rules:\n"
            "  - resource: 'aws_security_group.*'\n"
            "    action: block_deploy\n"
            "  - resource: 'aws_instance.*'\n"
            "    attribute: 'tags.*'\n"
            "    action: ignore\n"
        )
        engine = DriftPolicyEngine.load(str(tmp_path))
        assert engine.policy.coverage_threshold == 80.0
        assert len(engine.policy.rules) == 2
        assert engine.policy.rules[0].action == DriftAction.BLOCK_DEPLOY

    def test_load_json_fallback(self, tmp_path):
        (tmp_path / ".driftpolicy").write_text(json.dumps({
            "coverage_threshold": 95.0,
            "rules": [{"resource": "aws_s3_bucket.*", "action": "alert"}],
        }))
        # Simulate yaml not available
        with patch.dict("sys.modules", {"yaml": None}):
            engine = DriftPolicyEngine.load(str(tmp_path))
        assert engine.policy.coverage_threshold == 95.0

    def test_evaluate_coverage_violation(self, summary_dict_with_drift):
        engine = DriftPolicyEngine(DriftPolicy(coverage_threshold=90.0))
        ev = engine.evaluate(summary_dict_with_drift)
        assert ev.coverage_violation
        assert ev.blocked

    def test_evaluate_block_deploy_rule(self, summary_dict_with_drift):
        policy = DriftPolicy(coverage_threshold=0.0, rules=[
            PolicyRule(resource="aws_db_instance.*", action=DriftAction.BLOCK_DEPLOY),
        ])
        ev = DriftPolicyEngine(policy).evaluate(summary_dict_with_drift)
        assert ev.blocked
        assert any("aws_db_instance" in r for r in ev.block_reasons)

    def test_evaluate_ignore_rule(self, summary_dict_with_drift):
        policy = DriftPolicy(coverage_threshold=0.0, rules=[
            PolicyRule(resource="aws_cloudwatch_log_group.*", action=DriftAction.IGNORE),
        ])
        ev = DriftPolicyEngine(policy).evaluate(summary_dict_with_drift)
        assert "aws_cloudwatch_log_group.logs" in ev.ignored_addresses

    def test_evaluate_auto_accept(self, summary_dict_with_drift):
        policy = DriftPolicy(coverage_threshold=0.0, rules=[
            PolicyRule(resource="aws_instance.*", action=DriftAction.AUTO_ACCEPT),
        ])
        ev = DriftPolicyEngine(policy).evaluate(summary_dict_with_drift)
        assert "aws_instance.web" in ev.accepted_addresses

    def test_evaluate_attribute_filter(self, summary_dict_with_drift):
        policy = DriftPolicy(coverage_threshold=0.0, rules=[
            PolicyRule(resource="aws_instance.*", attribute="instance_type",
                       action=DriftAction.BLOCK_DEPLOY),
        ])
        ev = DriftPolicyEngine(policy).evaluate(summary_dict_with_drift)
        assert ev.blocked

    def test_severity_override(self, summary_dict_with_drift):
        policy = DriftPolicy(coverage_threshold=0.0, rules=[
            PolicyRule(resource="aws_instance.*", action=DriftAction.ALERT,
                       severity_override="critical"),
        ])
        ev = DriftPolicyEngine(policy).evaluate(summary_dict_with_drift)
        verdict = next(v for v in ev.verdicts if v.address == "aws_instance.web")
        assert verdict.severity_override == "critical"

    def test_evaluation_to_dict(self, summary_dict_with_drift):
        ev = DriftPolicyEngine().evaluate(summary_dict_with_drift)
        d = ev.to_dict()
        assert "blocked" in d
        assert "verdicts" in d


# ===================================================================
# DriftHistory
# ===================================================================

class TestDriftHistory:
    def test_save_and_get_trend(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        for cov in [85.0, 88.0, 92.0]:
            history.save_snapshot("myproject", {
                "total_resources": 100,
                "total_drifted": int(100 - cov),
                "overall_coverage": cov,
                "total_stacks": 1,
                "results": [],
            })
        trend = history.get_trend("myproject")
        assert trend["snapshots"] == 3
        assert trend["trend"] == "improving"
        assert trend["current_coverage"] == 92.0
        assert trend["coverage_delta"] == 7.0

    def test_no_data(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        trend = history.get_trend("nonexistent")
        assert trend["snapshots"] == 0
        assert trend["trend"] == "no_data"

    def test_stable_trend(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        for _ in range(3):
            history.save_snapshot("proj", {
                "total_resources": 10, "total_drifted": 1,
                "overall_coverage": 90.0, "total_stacks": 1, "results": [],
            })
        assert history.get_trend("proj")["trend"] == "stable"

    def test_degrading_trend(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        for cov in [95.0, 90.0, 80.0]:
            history.save_snapshot("proj", {
                "total_resources": 100, "total_drifted": int(100 - cov),
                "overall_coverage": cov, "total_stacks": 1, "results": [],
            })
        assert history.get_trend("proj")["trend"] == "degrading"

    def test_threshold_warning(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        history.save_snapshot("proj", {
            "total_resources": 10, "total_drifted": 3,
            "overall_coverage": 70.0, "total_stacks": 1, "results": [],
        })
        assert history.check_threshold("proj", min_coverage=90.0) is not None

    def test_threshold_ok(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        history.save_snapshot("proj", {
            "total_resources": 10, "total_drifted": 0,
            "overall_coverage": 100.0, "total_stacks": 1, "results": [],
        })
        assert history.check_threshold("proj") is None

    def test_max_snapshots_capped(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        for i in range(400):
            history.save_snapshot("proj", {
                "total_resources": 10, "total_drifted": 0,
                "overall_coverage": 100.0, "total_stacks": 1, "results": [],
            })
        raw = json.loads((tmp_path / "proj.json").read_text())
        assert len(raw) == 365


# ===================================================================
# DriftReportGenerator
# ===================================================================

class TestDriftReportGenerator:
    @pytest.fixture
    def summary_with_drift(self):
        return DriftSummary(results=[
            DriftResult(
                directory="/tmp/tf", total_resources=3,
                drifted_resources=[
                    DriftedResource("aws_instance.web", "aws_instance",
                                    DriftType.CHANGED, DriftSeverity.LOW,
                                    changed_attributes=["instance_type"]),
                    DriftedResource("aws_db_instance.db", "aws_db_instance",
                                    DriftType.DELETED, DriftSeverity.CRITICAL),
                ],
                coverage_pct=33.3,
            ),
        ])

    @pytest.fixture
    def summary_no_drift(self):
        return DriftSummary(results=[
            DriftResult(directory="/tmp/tf", total_resources=5, coverage_pct=100.0),
        ])

    def test_generate_json(self, summary_with_drift, tmp_path):
        reporter = DriftReportGenerator()
        out = tmp_path / "report.json"
        content = reporter.generate_json(summary_with_drift, str(out))
        assert out.exists()
        data = json.loads(content)
        assert data["has_drift"] is True
        assert "generated_at" in data

    def test_generate_html(self, summary_with_drift, tmp_path):
        reporter = DriftReportGenerator()
        out = tmp_path / "report.html"
        reporter.generate_html(summary_with_drift, str(out))
        assert out.exists()
        html = out.read_text()
        assert "DRIFT DETECTED" in html
        assert "aws_instance.web" in html

    def test_generate_html_no_drift(self, summary_no_drift, tmp_path):
        reporter = DriftReportGenerator()
        out = tmp_path / "report.html"
        reporter.generate_html(summary_no_drift, str(out))
        assert "NO DRIFT" in out.read_text()

    def test_generate_markdown(self, summary_with_drift):
        reporter = DriftReportGenerator()
        md = reporter.generate_markdown(summary_with_drift)
        assert "DRIFT DETECTED" in md
        assert "aws_instance.web" in md
        assert "ThothCTL" in md

    def test_generate_markdown_no_drift(self, summary_no_drift):
        md = DriftReportGenerator().generate_markdown(summary_no_drift)
        assert "NO DRIFT" in md

    def test_display_console(self, summary_with_drift):
        console = MagicMock()
        DriftReportGenerator().display_console(summary_with_drift, console)
        assert console.print.called

    def test_display_console_empty(self):
        console = MagicMock()
        DriftReportGenerator().display_console(DriftSummary(), console)
        assert console.print.called


# ===================================================================
# DriftAI (offline fallback)
# ===================================================================

class TestDriftAI:
    def test_offline_analysis(self, summary_dict_with_drift):
        from thothctl.services.check.project.drift.drift_ai import _offline_drift_analysis
        result = _offline_drift_analysis(summary_dict_with_drift)
        assert "summary" in result
        assert "findings" in result
        assert "recommendations" in result
        assert result["summary"]["risk_score"] > 0
        # security_group is security-sensitive
        assert result["summary"]["security_risks"] >= 1

    def test_format_drift_for_ai(self, summary_dict_with_drift):
        from thothctl.services.check.project.drift.drift_ai import format_drift_for_ai
        text = format_drift_for_ai(summary_dict_with_drift)
        assert "Drift Analysis Request" in text
        assert "aws_db_instance.primary" in text

    def test_format_drift_with_trend(self, summary_dict_with_drift):
        from thothctl.services.check.project.drift.drift_ai import format_drift_for_ai
        trend = {"snapshots": 5, "trend": "degrading", "coverage_delta": -3.0,
                 "min_coverage": 80.0, "max_coverage": 95.0, "peak_drifted": 8}
        text = format_drift_for_ai(summary_dict_with_drift, trend=trend)
        assert "Coverage Trend" in text
        assert "degrading" in text

    def test_analyze_drift_with_ai_fallback(self, summary_dict_with_drift):
        from thothctl.services.check.project.drift.drift_ai import analyze_drift_with_ai
        # No AI provider configured → should fall back to offline
        result = analyze_drift_with_ai(summary_dict_with_drift, provider=None)
        assert "_note" in result
        assert "Offline" in result["_note"]
