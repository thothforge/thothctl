"""Unit tests for drift detection feature."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from thothctl.services.check.project.drift.models import (
    DriftedResource,
    DriftResult,
    DriftSeverity,
    DriftSummary,
    DriftType,
)
from thothctl.services.check.project.drift.drift_service import (
    DriftDetectionService,
    _matches_tags,
)
from thothctl.services.check.project.drift.drift_report import DriftReportGenerator
from thothctl.services.check.project.drift.drift_history import DriftHistory
from thothctl.services.check.project.drift.drift_policy import (
    DriftAction,
    DriftPolicy,
    DriftPolicyEngine,
    PolicyRule,
)
from thothctl.services.check.project.drift.drift_ai import (
    format_drift_for_ai,
    _offline_drift_analysis,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PLAN = {
    "resource_changes": [
        {
            "address": "aws_s3_bucket.data",
            "type": "aws_s3_bucket",
            "change": {
                "actions": ["update"],
                "before": {"tags": {"env": "prod", "team": "data"}, "acl": "private"},
                "after": {"tags": {"env": "prod", "team": "data"}, "acl": "public-read"},
            },
        },
        {
            "address": "aws_instance.web",
            "type": "aws_instance",
            "change": {"actions": ["no-op"], "before": {}, "after": {}},
        },
        {
            "address": "aws_db_instance.main",
            "type": "aws_db_instance",
            "change": {
                "actions": ["delete", "create"],
                "before": {"tags": {"env": "prod"}, "instance_class": "db.t3.medium"},
                "after": {"tags": {"env": "prod"}, "instance_class": "db.t3.large"},
            },
        },
        {
            "address": "aws_security_group.web",
            "type": "aws_security_group",
            "change": {
                "actions": ["update"],
                "before": {"tags": {"env": "staging"}, "ingress": []},
                "after": {"tags": {"env": "staging"}, "ingress": [{"port": 443}]},
            },
        },
        {
            "address": "aws_cloudwatch_log_group.app",
            "type": "aws_cloudwatch_log_group",
            "change": {
                "actions": ["update"],
                "before": {"retention": 7},
                "after": {"retention": 14},
            },
        },
    ]
}


@pytest.fixture
def tmp_stack(tmp_path):
    """Create a temp directory with a tfplan.json."""
    plan_path = tmp_path / "tfplan.json"
    plan_path.write_text(json.dumps(SAMPLE_PLAN))
    return tmp_path


@pytest.fixture
def service():
    return DriftDetectionService()


@pytest.fixture
def reporter():
    return DriftReportGenerator()


# ===========================================================================
# Models
# ===========================================================================


class TestModels:
    def test_drift_severity_values(self):
        assert DriftSeverity.CRITICAL.value == "critical"
        assert DriftSeverity.LOW.value == "low"

    def test_drift_type_values(self):
        assert DriftType.CHANGED.value == "changed"
        assert DriftType.DELETED.value == "deleted"
        assert DriftType.UNMANAGED.value == "unmanaged"

    def test_drifted_resource_to_dict(self):
        r = DriftedResource(
            address="aws_s3_bucket.test",
            resource_type="aws_s3_bucket",
            drift_type=DriftType.CHANGED,
            severity=DriftSeverity.HIGH,
            changed_attributes=["acl"],
            actions=["update"],
            tags={"env": "prod"},
        )
        d = r.to_dict()
        assert d["address"] == "aws_s3_bucket.test"
        assert d["drift_type"] == "changed"
        assert d["severity"] == "high"
        assert d["tags"] == {"env": "prod"}

    def test_drift_result_properties(self):
        r = DriftResult(
            directory="/tmp/test",
            total_resources=10,
            drifted_resources=[
                DriftedResource("a", "t", DriftType.CHANGED, DriftSeverity.CRITICAL),
                DriftedResource("b", "t", DriftType.CHANGED, DriftSeverity.LOW),
            ],
            coverage_pct=80.0,
        )
        assert r.has_drift is True
        assert r.severity_counts["critical"] == 1
        assert r.severity_counts["low"] == 1

    def test_drift_result_no_drift(self):
        r = DriftResult(directory="/tmp", total_resources=5)
        assert r.has_drift is False
        assert r.coverage_pct == 100.0

    def test_drift_summary_aggregation(self):
        s = DriftSummary(results=[
            DriftResult("/a", 10, [DriftedResource("x", "t", DriftType.CHANGED, DriftSeverity.LOW)], 90.0),
            DriftResult("/b", 10, [], 100.0),
        ])
        assert s.total_resources == 20
        assert s.total_drifted == 1
        assert s.has_drift is True
        assert s.overall_coverage == 95.0

    def test_drift_summary_empty(self):
        s = DriftSummary()
        assert s.total_drifted == 0
        assert s.overall_coverage == 100.0
        assert s.has_drift is False

    def test_drift_summary_to_dict(self):
        s = DriftSummary(results=[DriftResult("/a", 5)])
        d = s.to_dict()
        assert "total_stacks" in d
        assert "results" in d
        assert d["total_stacks"] == 1


# ===========================================================================
# Drift Service
# ===========================================================================


class TestDriftService:
    def test_detect_drift_from_plan(self, tmp_stack, service):
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        assert result.total_resources == 5
        assert len(result.drifted_resources) == 4  # web is no-op
        assert result.has_drift is True

    def test_no_op_excluded(self, tmp_stack, service):
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        addresses = [r.address for r in result.drifted_resources]
        assert "aws_instance.web" not in addresses

    def test_severity_critical_stateful(self, tmp_stack, service):
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        db = next(r for r in result.drifted_resources if r.address == "aws_db_instance.main")
        assert db.severity == DriftSeverity.CRITICAL

    def test_severity_high_s3(self, tmp_stack, service):
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        s3 = next(r for r in result.drifted_resources if r.address == "aws_s3_bucket.data")
        assert s3.severity == DriftSeverity.HIGH

    def test_severity_medium_sg(self, tmp_stack, service):
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        sg = next(r for r in result.drifted_resources if r.address == "aws_security_group.web")
        assert sg.severity == DriftSeverity.MEDIUM

    def test_severity_low_cloudwatch(self, tmp_stack, service):
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        cw = next(r for r in result.drifted_resources if r.address == "aws_cloudwatch_log_group.app")
        assert cw.severity == DriftSeverity.LOW

    def test_changed_attributes_extracted(self, tmp_stack, service):
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        s3 = next(r for r in result.drifted_resources if r.address == "aws_s3_bucket.data")
        assert "acl" in s3.changed_attributes

    def test_tags_extracted(self, tmp_stack, service):
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        s3 = next(r for r in result.drifted_resources if r.address == "aws_s3_bucket.data")
        assert s3.tags == {"env": "prod", "team": "data"}

    def test_tags_empty_when_absent(self, tmp_stack, service):
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        cw = next(r for r in result.drifted_resources if r.address == "aws_cloudwatch_log_group.app")
        assert cw.tags == {}

    def test_detect_drift_recursive(self, tmp_path, service):
        for name in ("stack_a", "stack_b"):
            d = tmp_path / name
            d.mkdir()
            (d / "tfplan.json").write_text(json.dumps(SAMPLE_PLAN))
        summary = service.detect_drift(str(tmp_path), recursive=True)
        assert len(summary.results) == 2

    def test_detect_drift_nonexistent_plan(self, tmp_path, service):
        result = service.detect_drift_from_plan(str(tmp_path / "missing.json"))
        assert result.error is not None

    def test_coverage_calculation(self, tmp_stack, service):
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        expected = round(((5 - 4) / 5) * 100, 1)
        assert result.coverage_pct == expected

    def test_driftignore(self, tmp_stack, service):
        (tmp_stack / ".driftignore").write_text("aws_s3_bucket.*\naws_cloudwatch_*\n")
        result = service.detect_drift_from_plan(str(tmp_stack / "tfplan.json"))
        addresses = [r.address for r in result.drifted_resources]
        assert "aws_s3_bucket.data" not in addresses
        assert "aws_cloudwatch_log_group.app" not in addresses

    def test_classify_delete(self):
        assert DriftDetectionService._classify_drift_type(["delete"]) == DriftType.DELETED

    def test_classify_update(self):
        assert DriftDetectionService._classify_drift_type(["update"]) == DriftType.CHANGED

    def test_classify_create(self):
        assert DriftDetectionService._classify_drift_type(["create"]) == DriftType.UNMANAGED

    def test_classify_replace(self):
        assert DriftDetectionService._classify_drift_type(["delete", "create"]) == DriftType.CHANGED

    def test_classify_noop(self):
        assert DriftDetectionService._classify_drift_type(["no-op"]) is None


# ===========================================================================
# Tag Filtering
# ===========================================================================


class TestTagFiltering:
    def test_exact_match(self):
        assert _matches_tags({"env": "prod"}, {"env": "prod"}) is True

    def test_exact_mismatch(self):
        assert _matches_tags({"env": "prod"}, {"env": "staging"}) is False

    def test_wildcard_value(self):
        assert _matches_tags({"env": "prod"}, {"env": "*"}) is True

    def test_empty_string_as_wildcard(self):
        assert _matches_tags({"env": "prod"}, {"env": ""}) is True

    def test_key_missing(self):
        assert _matches_tags({"env": "prod"}, {"team": "platform"}) is False

    def test_no_tags_on_resource(self):
        assert _matches_tags({}, {"env": "prod"}) is False

    def test_no_filter(self):
        assert _matches_tags({"env": "prod"}, {}) is True

    def test_multiple_tags_all_match(self):
        assert _matches_tags({"env": "prod", "team": "data"}, {"env": "prod", "team": "data"}) is True

    def test_multiple_tags_partial_match(self):
        assert _matches_tags({"env": "prod", "team": "data"}, {"env": "prod", "team": "ops"}) is False

    def test_filter_applied_to_summary(self, tmp_stack, service):
        summary = service.detect_drift(str(tmp_stack), filter_tags={"env": "prod"})
        addresses = [r.address for res in summary.results for r in res.drifted_resources]
        assert "aws_s3_bucket.data" in addresses
        assert "aws_db_instance.main" in addresses
        assert "aws_security_group.web" not in addresses  # staging
        assert "aws_cloudwatch_log_group.app" not in addresses  # no tags

    def test_filter_wildcard_env(self, tmp_stack, service):
        summary = service.detect_drift(str(tmp_stack), filter_tags={"env": "*"})
        addresses = [r.address for res in summary.results for r in res.drifted_resources]
        assert len(addresses) == 3  # prod, prod, staging — not cloudwatch (no tags)

    def test_filter_recalculates_coverage(self, tmp_stack, service):
        summary = service.detect_drift(str(tmp_stack), filter_tags={"env": "prod"})
        for result in summary.results:
            assert result.coverage_pct >= 0


# ===========================================================================
# Reports
# ===========================================================================


class TestReports:
    def _make_summary(self):
        return DriftSummary(results=[
            DriftResult("/test", 10, [
                DriftedResource("aws_s3_bucket.x", "aws_s3_bucket", DriftType.CHANGED, DriftSeverity.HIGH, ["acl"]),
            ], 90.0),
        ])

    def test_markdown_contains_status(self, reporter):
        md = reporter.generate_markdown(self._make_summary())
        assert "DRIFT DETECTED" in md
        assert "aws_s3_bucket.x" in md

    def test_markdown_no_drift(self, reporter):
        s = DriftSummary(results=[DriftResult("/ok", 5)])
        md = reporter.generate_markdown(s)
        assert "NO DRIFT" in md

    def test_json_report(self, reporter, tmp_path):
        path = str(tmp_path / "report.json")
        content = reporter.generate_json(self._make_summary(), path)
        data = json.loads(content)
        assert data["has_drift"] is True
        assert data["total_drifted"] == 1
        assert os.path.exists(path)

    def test_html_report(self, reporter, tmp_path):
        path = str(tmp_path / "report.html")
        reporter.generate_html(self._make_summary(), path)
        assert os.path.exists(path)
        html = Path(path).read_text()
        assert "aws_s3_bucket.x" in html
        assert "DRIFT DETECTED" in html

    def test_html_no_drift(self, reporter, tmp_path):
        path = str(tmp_path / "no_drift.html")
        reporter.generate_html(DriftSummary(results=[DriftResult("/ok", 5)]), path)
        html = Path(path).read_text()
        assert "No drift detected" in html


# ===========================================================================
# History / Trending
# ===========================================================================


class TestDriftHistory:
    def test_save_and_get_trend(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        for cov in [95.0, 93.0, 90.0]:
            history.save_snapshot("proj", {
                "total_resources": 100, "total_drifted": int(100 - cov),
                "overall_coverage": cov, "total_stacks": 1, "results": [],
            })
        trend = history.get_trend("proj")
        assert trend["snapshots"] == 3
        assert trend["trend"] == "degrading"
        assert trend["coverage_delta"] == -5.0
        assert trend["current_coverage"] == 90.0

    def test_trend_improving(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        for cov in [85.0, 90.0, 95.0]:
            history.save_snapshot("proj", {
                "total_resources": 100, "total_drifted": int(100 - cov),
                "overall_coverage": cov, "total_stacks": 1, "results": [],
            })
        trend = history.get_trend("proj")
        assert trend["trend"] == "improving"

    def test_trend_stable(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        for cov in [95.0, 95.0, 95.0]:
            history.save_snapshot("proj", {
                "total_resources": 100, "total_drifted": 5,
                "overall_coverage": cov, "total_stacks": 1, "results": [],
            })
        trend = history.get_trend("proj")
        assert trend["trend"] == "stable"

    def test_trend_no_data(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        trend = history.get_trend("nonexistent")
        assert trend["trend"] == "no_data"

    def test_threshold_warning(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        history.save_snapshot("proj", {
            "total_resources": 100, "total_drifted": 15,
            "overall_coverage": 85.0, "total_stacks": 1, "results": [],
        })
        warning = history.check_threshold("proj", min_coverage=90.0)
        assert warning is not None
        assert "85.0%" in warning

    def test_threshold_ok(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        history.save_snapshot("proj", {
            "total_resources": 100, "total_drifted": 2,
            "overall_coverage": 98.0, "total_stacks": 1, "results": [],
        })
        assert history.check_threshold("proj", min_coverage=90.0) is None

    def test_history_limit_365(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        for i in range(400):
            history.save_snapshot("proj", {
                "total_resources": 10, "total_drifted": 1,
                "overall_coverage": 90.0, "total_stacks": 1, "results": [],
            })
        raw = json.loads((tmp_path / "proj.json").read_text())
        assert len(raw) == 365

    def test_trend_history_entries(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        for cov in [90.0, 92.0]:
            history.save_snapshot("proj", {
                "total_resources": 100, "total_drifted": int(100 - cov),
                "overall_coverage": cov, "total_stacks": 1, "results": [],
            })
        trend = history.get_trend("proj")
        assert len(trend["history"]) == 2
        assert "date" in trend["history"][0]
        assert "coverage" in trend["history"][0]


# ===========================================================================
# Policy Engine
# ===========================================================================


class TestDriftPolicy:
    def test_default_policy(self):
        engine = DriftPolicyEngine()
        assert engine.policy.coverage_threshold == 90.0
        assert engine.policy.rules == []

    def test_block_deploy_on_resource(self):
        policy = DriftPolicy(rules=[
            PolicyRule(resource="aws_security_group.*", action=DriftAction.BLOCK_DEPLOY),
        ])
        engine = DriftPolicyEngine(policy)
        summary = DriftSummary(results=[
            DriftResult("/t", 10, [
                DriftedResource("aws_security_group.web", "aws_security_group",
                                DriftType.CHANGED, DriftSeverity.MEDIUM),
            ], 90.0),
        ]).to_dict()
        evaluation = engine.evaluate(summary)
        assert evaluation.blocked is True
        assert any("aws_security_group.web" in r for r in evaluation.block_reasons)

    def test_ignore_action(self):
        policy = DriftPolicy(rules=[
            PolicyRule(resource="aws_cloudwatch_*", action=DriftAction.IGNORE),
        ])
        engine = DriftPolicyEngine(policy)
        summary = DriftSummary(results=[
            DriftResult("/t", 10, [
                DriftedResource("aws_cloudwatch_log_group.app", "aws_cloudwatch_log_group",
                                DriftType.CHANGED, DriftSeverity.LOW),
            ], 90.0),
        ]).to_dict()
        evaluation = engine.evaluate(summary)
        assert "aws_cloudwatch_log_group.app" in evaluation.ignored_addresses
        assert evaluation.blocked is False

    def test_auto_accept_action(self):
        policy = DriftPolicy(rules=[
            PolicyRule(resource="aws_instance.*", attribute="tags*", action=DriftAction.AUTO_ACCEPT),
        ])
        engine = DriftPolicyEngine(policy)
        summary = DriftSummary(results=[
            DriftResult("/t", 10, [
                DriftedResource("aws_instance.web", "aws_instance",
                                DriftType.CHANGED, DriftSeverity.LOW,
                                changed_attributes=["tags"]),
            ], 90.0),
        ]).to_dict()
        evaluation = engine.evaluate(summary)
        assert "aws_instance.web" in evaluation.accepted_addresses

    def test_attribute_filter_no_match(self):
        policy = DriftPolicy(rules=[
            PolicyRule(resource="aws_instance.*", attribute="tags.*", action=DriftAction.AUTO_ACCEPT),
        ])
        engine = DriftPolicyEngine(policy)
        summary = DriftSummary(results=[
            DriftResult("/t", 10, [
                DriftedResource("aws_instance.web", "aws_instance",
                                DriftType.CHANGED, DriftSeverity.LOW,
                                changed_attributes=["instance_type"]),
            ], 90.0),
        ]).to_dict()
        evaluation = engine.evaluate(summary)
        assert "aws_instance.web" not in evaluation.accepted_addresses

    def test_coverage_threshold_violation(self):
        policy = DriftPolicy(coverage_threshold=95.0)
        engine = DriftPolicyEngine(policy)
        summary = {"overall_coverage": 88.0, "results": []}
        evaluation = engine.evaluate(summary)
        assert evaluation.blocked is True
        assert evaluation.coverage_violation is True

    def test_coverage_threshold_ok(self):
        engine = DriftPolicyEngine(DriftPolicy(coverage_threshold=80.0))
        evaluation = engine.evaluate({"overall_coverage": 90.0, "results": []})
        assert evaluation.blocked is False

    def test_severity_override(self):
        policy = DriftPolicy(rules=[
            PolicyRule(resource="aws_security_group.*", action=DriftAction.BLOCK_DEPLOY,
                       severity_override="critical"),
        ])
        engine = DriftPolicyEngine(policy)
        summary = DriftSummary(results=[
            DriftResult("/t", 10, [
                DriftedResource("aws_security_group.web", "aws_security_group",
                                DriftType.CHANGED, DriftSeverity.MEDIUM),
            ], 90.0),
        ]).to_dict()
        evaluation = engine.evaluate(summary)
        verdict = evaluation.verdicts[0]
        assert verdict.severity_override == "critical"

    def test_first_match_wins(self):
        policy = DriftPolicy(rules=[
            PolicyRule(resource="aws_s3_bucket.*", action=DriftAction.IGNORE),
            PolicyRule(resource="aws_s3_bucket.*", action=DriftAction.BLOCK_DEPLOY),
        ])
        engine = DriftPolicyEngine(policy)
        summary = DriftSummary(results=[
            DriftResult("/t", 10, [
                DriftedResource("aws_s3_bucket.x", "aws_s3_bucket",
                                DriftType.CHANGED, DriftSeverity.LOW),
            ], 90.0),
        ]).to_dict()
        evaluation = engine.evaluate(summary)
        assert evaluation.verdicts[0].action == DriftAction.IGNORE
        assert evaluation.blocked is False

    def test_default_action_is_alert(self):
        engine = DriftPolicyEngine(DriftPolicy())
        summary = DriftSummary(results=[
            DriftResult("/t", 10, [
                DriftedResource("aws_instance.x", "aws_instance",
                                DriftType.CHANGED, DriftSeverity.LOW),
            ], 90.0),
        ]).to_dict()
        evaluation = engine.evaluate(summary)
        assert evaluation.verdicts[0].action == DriftAction.ALERT

    def test_load_yaml_policy(self, tmp_path):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        (tmp_path / ".driftpolicy").write_text(
            "coverage_threshold: 85.0\nrules:\n  - resource: 'aws_s3_*'\n    action: ignore\n"
        )
        engine = DriftPolicyEngine.load(str(tmp_path))
        assert engine.policy.coverage_threshold == 85.0
        assert len(engine.policy.rules) == 1

    def test_load_missing_policy(self, tmp_path):
        engine = DriftPolicyEngine.load(str(tmp_path))
        assert engine.policy.coverage_threshold == 90.0
        assert engine.policy.rules == []

    def test_evaluation_to_dict(self):
        engine = DriftPolicyEngine(DriftPolicy(coverage_threshold=95.0))
        evaluation = engine.evaluate({"overall_coverage": 80.0, "results": []})
        d = evaluation.to_dict()
        assert d["blocked"] is True
        assert d["coverage_violation"] is True
        assert len(d["block_reasons"]) > 0


# ===========================================================================
# AI Analysis
# ===========================================================================


class TestDriftAI:
    def _make_summary_dict(self):
        return DriftSummary(results=[
            DriftResult("/test", 10, [
                DriftedResource("aws_security_group.web", "aws_security_group",
                                DriftType.CHANGED, DriftSeverity.MEDIUM,
                                changed_attributes=["ingress"], actions=["update"]),
                DriftedResource("aws_s3_bucket.data", "aws_s3_bucket",
                                DriftType.CHANGED, DriftSeverity.HIGH,
                                changed_attributes=["acl"], actions=["update"]),
            ], 80.0),
        ]).to_dict()

    def test_format_drift_for_ai(self):
        ctx = format_drift_for_ai(self._make_summary_dict())
        assert "Drift Analysis Request" in ctx
        assert "aws_security_group.web" in ctx
        assert "80" in ctx  # coverage

    def test_format_with_trend(self):
        trend = {"snapshots": 5, "trend": "degrading", "coverage_delta": -3.0,
                 "min_coverage": 80.0, "max_coverage": 95.0, "peak_drifted": 8}
        ctx = format_drift_for_ai(self._make_summary_dict(), trend=trend)
        assert "degrading" in ctx
        assert "Coverage Trend" in ctx

    def test_offline_analysis_risk_score(self):
        result = _offline_drift_analysis(self._make_summary_dict())
        assert "summary" in result
        assert result["summary"]["risk_score"] > 0
        assert result["summary"]["total_analyzed"] == 2

    def test_offline_detects_security_resources(self):
        result = _offline_drift_analysis(self._make_summary_dict())
        assert result["summary"]["security_risks"] >= 1  # security_group

    def test_offline_recommendations(self):
        result = _offline_drift_analysis(self._make_summary_dict())
        assert len(result["recommendations"]) > 0

    def test_offline_block_on_security_drift(self):
        result = _offline_drift_analysis(self._make_summary_dict())
        assert result["summary"]["should_block_deploy"] is True

    def test_offline_no_block_when_clean(self):
        clean = {"total_drifted": 0, "overall_coverage": 100, "results": []}
        result = _offline_drift_analysis(clean)
        assert result["summary"]["should_block_deploy"] is False
        assert result["summary"]["risk_score"] == 0

    def test_offline_findings_sorted_by_priority(self):
        result = _offline_drift_analysis(self._make_summary_dict())
        priorities = [f["priority"] for f in result["findings"]]
        assert priorities == sorted(priorities)


# ===========================================================================
# Additional coverage tests
# ===========================================================================


class TestReportConsoleDisplay:
    """Cover drift_report.display_console (lines 29-78)."""

    def test_display_console_with_drift(self, reporter):
        from unittest.mock import MagicMock
        console = MagicMock()
        summary = DriftSummary(results=[
            DriftResult("/test", 10, [
                DriftedResource("aws_s3_bucket.x", "aws_s3_bucket",
                                DriftType.CHANGED, DriftSeverity.HIGH, ["acl"]),
                DriftedResource("aws_db_instance.y", "aws_db_instance",
                                DriftType.DELETED, DriftSeverity.CRITICAL),
            ], 80.0),
        ])
        reporter.display_console(summary, console)
        assert console.print.called

    def test_display_console_no_drift(self, reporter):
        from unittest.mock import MagicMock
        console = MagicMock()
        summary = DriftSummary(results=[DriftResult("/ok", 5)])
        reporter.display_console(summary, console)
        assert console.print.called

    def test_display_console_with_error(self, reporter):
        from unittest.mock import MagicMock
        console = MagicMock()
        summary = DriftSummary(results=[DriftResult("/err", error="plan failed")])
        reporter.display_console(summary, console)
        assert console.print.called

    def test_display_console_empty(self, reporter):
        from unittest.mock import MagicMock
        console = MagicMock()
        reporter.display_console(DriftSummary(), console)
        assert console.print.called


class TestDriftServiceEdgeCases:
    """Cover drift_service edge cases."""

    def test_detect_drift_live_no_tf_files(self, tmp_path, service):
        """detect_drift_live on a dir with no terraform — should error."""
        result = service.detect_drift_live(str(tmp_path))
        assert result.error is not None

    def test_extract_tags_from_tags_all(self):
        """Tags extracted from tags_all when tags is absent."""
        rc = {"change": {"after": {"tags_all": {"env": "prod"}}, "before": {}}}
        tags = DriftDetectionService._extract_tags(rc)
        assert tags == {"env": "prod"}

    def test_extract_tags_prefers_after(self):
        """After state is preferred over before."""
        rc = {"change": {
            "before": {"tags": {"env": "old"}},
            "after": {"tags": {"env": "new"}},
        }}
        tags = DriftDetectionService._extract_tags(rc)
        assert tags["env"] == "new"

    def test_extract_tags_falls_back_to_before(self):
        """Falls back to before when after has no tags."""
        rc = {"change": {"before": {"tags": {"env": "prod"}}, "after": {}}}
        tags = DriftDetectionService._extract_tags(rc)
        assert tags == {"env": "prod"}

    def test_extract_tags_empty(self):
        rc = {"change": {"before": {}, "after": {}}}
        assert DriftDetectionService._extract_tags(rc) == {}

    def test_is_tf_root_true(self, tmp_path):
        (tmp_path / "main.tf").write_text("")
        assert DriftDetectionService._is_tf_root(str(tmp_path)) is True

    def test_is_tf_root_false(self, tmp_path):
        assert DriftDetectionService._is_tf_root(str(tmp_path)) is False

    def test_empty_plan(self, tmp_path, service):
        (tmp_path / "tfplan.json").write_text(json.dumps({"resource_changes": []}))
        result = service.detect_drift_from_plan(str(tmp_path / "tfplan.json"))
        assert result.has_drift is False
        assert result.total_resources == 0

    def test_plan_with_read_action(self, tmp_path, service):
        plan = {"resource_changes": [
            {"address": "data.aws_ami.latest", "type": "aws_ami",
             "change": {"actions": ["read"], "before": {}, "after": {}}},
        ]}
        (tmp_path / "tfplan.json").write_text(json.dumps(plan))
        result = service.detect_drift_from_plan(str(tmp_path / "tfplan.json"))
        assert result.has_drift is False
        assert result.total_resources == 1


class TestPolicyEdgeCases:
    """Cover drift_policy edge cases."""

    def test_load_json_fallback(self, tmp_path):
        """When PyYAML fails, JSON fallback is used."""
        policy_json = {"coverage_threshold": 80.0, "rules": [
            {"resource": "aws_s3_*", "action": "ignore"},
        ]}
        (tmp_path / ".driftpolicy").write_text(json.dumps(policy_json))
        # Force JSON path by writing valid JSON
        engine = DriftPolicyEngine.load(str(tmp_path))
        assert engine.policy.coverage_threshold == 80.0
        assert len(engine.policy.rules) == 1

    def test_invalid_rule_skipped(self, tmp_path):
        """Rules with invalid action are skipped."""
        try:
            import yaml
            (tmp_path / ".driftpolicy").write_text(
                "rules:\n  - resource: 'x'\n    action: invalid_action\n"
            )
        except ImportError:
            (tmp_path / ".driftpolicy").write_text(
                json.dumps({"rules": [{"resource": "x", "action": "invalid_action"}]})
            )
        engine = DriftPolicyEngine.load(str(tmp_path))
        assert len(engine.policy.rules) == 0

    def test_rule_missing_resource_skipped(self, tmp_path):
        try:
            import yaml
            (tmp_path / ".driftpolicy").write_text(
                "rules:\n  - action: ignore\n"
            )
        except ImportError:
            (tmp_path / ".driftpolicy").write_text(
                json.dumps({"rules": [{"action": "ignore"}]})
            )
        engine = DriftPolicyEngine.load(str(tmp_path))
        assert len(engine.policy.rules) == 0


class TestDriftAIEdgeCases:
    """Cover drift_ai edge cases."""

    def test_format_empty_summary(self):
        ctx = format_drift_for_ai({"total_stacks": 0, "total_resources": 0,
                                    "total_drifted": 0, "overall_coverage": 100, "results": []})
        assert "Drift Analysis Request" in ctx

    def test_format_with_error_result(self):
        summary = {"total_stacks": 1, "total_resources": 0, "total_drifted": 0,
                   "overall_coverage": 100, "results": [{"directory": "/err", "error": "boom",
                   "drifted_resources": []}]}
        ctx = format_drift_for_ai(summary)
        assert "ERROR" in ctx

    def test_offline_low_coverage_recommendation(self):
        summary = {"total_drifted": 25, "overall_coverage": 75.0, "results": [
            {"drifted_resources": [
                {"address": f"aws_instance.i{i}", "resource_type": "aws_instance",
                 "severity": "low", "changed_attributes": [], "actions": ["update"]}
                for i in range(25)
            ]}
        ]}
        result = _offline_drift_analysis(summary)
        assert any("critically low" in r for r in result["recommendations"])
        assert any("High drift count" in r for r in result["recommendations"])


class TestDriftHistoryEdgeCases:
    """Cover drift_history edge cases."""

    def test_corrupted_history_file(self, tmp_path):
        history = DriftHistory(storage_dir=str(tmp_path))
        (tmp_path / "proj.json").write_text("not json")
        trend = history.get_trend("proj")
        assert trend["trend"] == "no_data"

    def test_aggregate_severities(self):
        summary = {"results": [
            {"severity_counts": {"critical": 1, "high": 2, "medium": 0, "low": 3}},
            {"severity_counts": {"critical": 0, "high": 1, "medium": 1, "low": 0}},
        ]}
        counts = DriftHistory._aggregate_severities(summary)
        assert counts["critical"] == 1
        assert counts["high"] == 3
        assert counts["low"] == 3
