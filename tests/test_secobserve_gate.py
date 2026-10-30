"""Tests for SecObserve publishing and security gate enforcement in scan iac."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from click.testing import CliRunner

from thothctl.commands.scan.commands.iac import RestoredIaCScanCommand
from thothctl.commands.scan.commands.iac import cli as scan_iac_cli
from thothctl.services.inventory.secobserve_publisher import (
    SecObserveConfig,
    SecObserveGateResult,
    SecObservePublisher,
)
from thothctl.services.scan.sarif_output import build_sarif

BASE = "https://so.example"
SEVERITIES = ("critical", "high", "medium", "low", "none", "unknown")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(str(status))
    else:
        resp.raise_for_status.return_value = None
    return resp


def _counts(**overrides):
    counts = {f"open_{s}_observation_count": 0 for s in SEVERITIES}
    for sev, value in overrides.items():
        counts[f"open_{sev}_observation_count"] = value
    return counts


def _thresholds(**overrides):
    return {
        f"security_gate_threshold_{s}": overrides.get(s) for s in SEVERITIES
    }


def _product(**fields):
    product = {
        "id": 3,
        "name": "infra",
        "product_group": None,
        "repository_default_branch": None,
        "security_gate_active": None,
        "security_gate_passed": None,
        **_thresholds(),
        **_counts(),
    }
    product.update(fields)
    return product


class FakeSession:
    """Minimal stand-in for requests.Session routing GETs/POSTs by URL path."""

    def __init__(self, routes, post_routes=None):
        self.routes = routes  # path -> payload | (payload, status) | Exception
        self.post_routes = post_routes or {}  # path -> (payload, status)
        self.posts = []  # (path, json) for every POST
        self.headers = {}

    def post(self, url, json=None, data=None, files=None, timeout=None):
        path = url.replace(BASE, "")
        self.posts.append((path, json if json is not None else data))
        payload, status = self.post_routes.get(path, ({"detail": "not found"}, 404))
        resp = _response(payload, status)
        resp.text = str(payload)
        return resp

    def get(self, url, params=None, timeout=None):
        path = url.replace(BASE, "")
        route = self.routes.get(path)
        if route is None:
            return _response({"detail": "not found"}, 404)
        if isinstance(route, Exception):
            raise route
        if isinstance(route, tuple):
            return _response(*route)
        if callable(route):
            return _response(route(params or {}))
        return _response(route)


def _publisher(routes, branch_name=None, post_routes=None, product_group=None,
               auto_create=True, origin_service=None):
    config = SecObserveConfig(
        url=BASE,
        api_token="token",
        product_name="infra",
        branch_name=branch_name,
        product_group=product_group,
        auto_create_product=auto_create,
        origin_service=origin_service,
    )
    pub = SecObservePublisher(config)
    pub._session = FakeSession(routes, post_routes)
    pub._api_base = BASE
    return pub


def _products_route(*products):
    return {"/api/products/": {"results": list(products)}}


# ── Gate: server-computed (default branch / no branch) ────────────────────────


class TestGateServerComputed:
    def test_no_branch_no_default_branch_uses_server_result(self):
        product = _product(
            security_gate_passed=False,
            **_counts(high=2),
        )
        routes = {
            **_products_route(product),
            "/api/settings/1/": {"security_gate_active": True, **_thresholds(critical=0, high=0)},
        }
        gate = _publisher(routes).get_security_gate()
        assert gate.evaluated is True
        assert gate.source == "product"
        assert gate.passed is False
        assert gate.failed is True
        assert gate.counts["high"] == 2
        assert gate.thresholds["high"] == 0
        assert gate.url == f"{BASE}/#/products/3/show"

    def test_server_passed_none_means_inactive(self):
        routes = {
            **_products_route(_product(security_gate_passed=None)),
            "/api/settings/1/": {"security_gate_active": False},
        }
        gate = _publisher(routes).get_security_gate()
        assert gate.evaluated is True
        assert gate.passed is None
        assert gate.active is False
        assert gate.failed is False

    def test_default_branch_uses_server_result(self):
        product = _product(security_gate_passed=True, repository_default_branch=1)
        routes = {
            **_products_route(product),
            "/api/branches/": {"results": [{"id": 1, "name": "main", "is_default_branch": True, **_counts(high=9)}]},
            "/api/settings/1/": {"security_gate_active": True, **_thresholds()},
        }
        gate = _publisher(routes, branch_name="main").get_security_gate()
        assert gate.source == "product"
        assert gate.passed is True

    def test_threshold_read_failure_does_not_block_server_result(self):
        routes = {
            **_products_route(_product(security_gate_passed=True)),
            "/api/settings/1/": requests.exceptions.ConnectionError("boom"),
        }
        gate = _publisher(routes).get_security_gate()
        assert gate.evaluated is True
        assert gate.passed is True
        assert gate.thresholds == {}


# ── Gate: branch evaluated by ThothCTL ────────────────────────────────────────


class TestGateBranchEvaluated:
    def _routes(self, product, branch_counts, settings=None, group=None):
        routes = {
            **_products_route(product),
            "/api/branches/": {
                "results": [
                    {"id": 2, "name": "feature", "is_default_branch": False, **branch_counts}
                ]
            },
        }
        if settings is not None:
            routes["/api/settings/1/"] = settings
        if group is not None:
            routes["/api/product_groups/7/"] = group
        return routes

    def test_branch_fails_when_count_exceeds_threshold(self):
        product = _product(
            repository_default_branch=1,
            security_gate_active=True,
            **_thresholds(critical=0, high=1, medium=999, low=999, none=999, unknown=999),
        )
        gate = _publisher(
            self._routes(product, _counts(high=2)), branch_name="feature"
        ).get_security_gate()
        assert gate.source == "branch"
        assert gate.evaluated is True
        assert gate.passed is False

    def test_branch_passes_at_threshold(self):
        product = _product(
            repository_default_branch=1,
            security_gate_active=True,
            **_thresholds(critical=0, high=2, medium=999, low=999, none=999, unknown=999),
        )
        gate = _publisher(
            self._routes(product, _counts(high=2)), branch_name="feature"
        ).get_security_gate()
        assert gate.passed is True

    def test_unset_threshold_counts_as_zero_when_product_active(self):
        # SecObserve: `getattr(source, threshold) or 0` for active product/group.
        product = _product(repository_default_branch=1, security_gate_active=True)
        gate = _publisher(
            self._routes(product, _counts(low=1)), branch_name="feature"
        ).get_security_gate()
        assert gate.thresholds["low"] == 0
        assert gate.passed is False

    def test_group_setting_overrides_product(self):
        product = _product(
            repository_default_branch=1,
            product_group=7,
            security_gate_active=True,
            **_thresholds(high=0),
        )
        group = {"security_gate_active": False}
        gate = _publisher(
            self._routes(product, _counts(high=5), group=group), branch_name="feature"
        ).get_security_gate()
        assert gate.evaluated is True
        assert gate.active is False
        assert gate.passed is None

    def test_active_group_thresholds_are_used(self):
        product = _product(
            repository_default_branch=1,
            product_group=7,
            security_gate_active=True,
            **_thresholds(high=0),
        )
        group = {"security_gate_active": True, **_thresholds(high=10)}
        gate = _publisher(
            self._routes(product, _counts(high=5), group=group), branch_name="feature"
        ).get_security_gate()
        assert gate.thresholds["high"] == 10
        assert gate.passed is True

    def test_inherits_global_settings(self):
        product = _product(repository_default_branch=1)
        settings = {"security_gate_active": True, **_thresholds(critical=0, high=0, medium=5)}
        gate = _publisher(
            self._routes(product, _counts(medium=6), settings=settings),
            branch_name="feature",
        ).get_security_gate()
        assert gate.passed is False

    def test_global_gate_off_is_inactive(self):
        product = _product(repository_default_branch=1)
        gate = _publisher(
            self._routes(product, _counts(high=50), settings={"security_gate_active": False}),
            branch_name="feature",
        ).get_security_gate()
        assert gate.evaluated is True
        assert gate.passed is None

    def test_unreadable_settings_is_unknown(self):
        product = _product(repository_default_branch=1)
        routes = self._routes(product, _counts())
        routes["/api/settings/1/"] = ({"detail": "forbidden"}, 403)
        gate = _publisher(routes, branch_name="feature").get_security_gate()
        assert gate.evaluated is False
        assert "settings" in gate.error


# ── Gate: cannot be evaluated ─────────────────────────────────────────────────


class TestGateUnknown:
    def test_no_branch_but_product_has_default_branch(self):
        routes = _products_route(_product(repository_default_branch=1, security_gate_passed=True))
        gate = _publisher(routes).get_security_gate()
        assert gate.evaluated is False
        assert "SECOBSERVE_BRANCH_NAME" in gate.error

    def test_branch_not_found(self):
        routes = {**_products_route(_product()), "/api/branches/": {"results": []}}
        gate = _publisher(routes, branch_name="nope").get_security_gate()
        assert gate.evaluated is False
        assert "not found" in gate.error

    def test_product_name_is_exact_match(self):
        # SecObserve's ?name= filter is a contains match.
        routes = _products_route(_product(name="infra-legacy", security_gate_passed=True))
        gate = _publisher(routes).get_security_gate("infra")
        assert gate.evaluated is False
        assert "not found" in gate.error

    def test_unreachable_server(self):
        routes = {"/api/products/": requests.exceptions.ConnectionError("down")}
        gate = _publisher(routes).get_security_gate()
        assert gate.evaluated is False
        assert "Could not query SecObserve" in gate.error
        assert gate.failed is False  # 'failed' is only for evaluated gates


class TestEnsureProduct:
    def test_does_not_match_substring_product(self):
        pub = _publisher(_products_route(_product(id=9, name="infra-legacy")))
        pub._session.post = MagicMock(return_value=_response({"id": 42}, 201))
        assert pub._ensure_product("infra") == 42
        pub._session.post.assert_called_once()

    def test_returns_existing_exact_product(self):
        pub = _publisher(_products_route(_product(id=9, name="infra")))
        pub._session.post = MagicMock()
        assert pub._ensure_product("infra") == 9
        pub._session.post.assert_not_called()


# ── SARIF generation ──────────────────────────────────────────────────────────


class TestBuildSarifIncludeEmpty:
    def test_empty_tool_skipped_by_default(self):
        doc = build_sarif({"checkov": {"status": "COMPLETE", "findings": []}}, ".")
        assert doc["runs"] == []

    def test_empty_tool_emits_run_with_no_results(self):
        doc = build_sarif(
            {"checkov": {"status": "COMPLETE", "findings": []}}, ".", include_empty=True
        )
        assert len(doc["runs"]) == 1
        assert doc["runs"][0]["tool"]["driver"]["name"] == "checkov"
        assert doc["runs"][0]["results"] == []


# ── Publishing: one file per tool ─────────────────────────────────────────────


@pytest.fixture
def publish_env(tmp_path):
    """Run _publish_scan_to_secobserve with a mocked publisher; capture uploads."""
    uploads = []

    def fake_publish(path, product_name=None, parser_name="SARIF", service_name=None):
        uploads.append(
            {
                "file": path.name,
                "service": service_name,
                "doc": json.loads(Path(path).read_text()),
            }
        )
        result = MagicMock()
        result.success = True
        result.observations_new = 0
        result.observations_updated = 0
        result.observations_resolved = 0
        return result

    def run(results, origin_service=None):
        with patch(
            "thothctl.services.inventory.secobserve_publisher.SecObservePublisher"
        ) as pub_cls, patch(
            "thothctl.services.inventory.secobserve_publisher.SecObserveConfig"
        ) as cfg_cls:
            cfg = MagicMock()
            cfg.url = BASE
            cfg.product_name = "infra"
            cfg.origin_service = origin_service
            cfg_cls.from_toml.return_value = cfg
            pub_cls.return_value.publish_observations.side_effect = fake_publish
            outcome = RestoredIaCScanCommand()._publish_scan_to_secobserve(
                results, str(tmp_path), "infra", str(tmp_path)
            )
        return outcome

    return tmp_path, uploads, run


def _tool(status="COMPLETE", findings=None):
    return {"status": status, "findings": findings or []}


FINDING = {"id": "CKV_AWS_1", "severity": "HIGH", "title": "t", "file": "main.tf", "line": 1}


class TestPublishPerTool:
    def test_each_tool_gets_its_own_file_and_service(self, publish_env):
        reports, uploads, run = publish_env
        (reports / "kics").mkdir()
        (reports / "kics" / "kics-results.sarif").write_text('{"runs": []}')
        outcome = run(
            {
                "kics": _tool(findings=[FINDING]),
                "checkov": _tool(findings=[FINDING]),
                "trivy": _tool(findings=[FINDING]),
                "summary": {},
            }
        )
        files = {u["file"]: u["service"] for u in uploads}
        assert files == {
            "kics-results.sarif": "kics",
            "thothctl-checkov.sarif": "checkov",
            "thothctl-trivy.sarif": "trivy",
        }
        # Each generated file contains only its own tool (no cross-tool resolution).
        for u in uploads:
            if u["file"].startswith("thothctl-"):
                names = [r["tool"]["driver"]["name"] for r in u["doc"]["runs"]]
                assert names == [u["service"]]
        assert outcome["ok"] is True
        assert outcome["published"] == outcome["attempted"] == 3

    def test_completed_tool_without_findings_uploads_empty_run(self, publish_env):
        _, uploads, run = publish_env
        run({"checkov": _tool(findings=[])})
        assert len(uploads) == 1
        runs = uploads[0]["doc"]["runs"]
        assert len(runs) == 1  # never an empty runs array (SecObserve returns 500)
        assert runs[0]["results"] == []

    def test_incomplete_tools_are_not_uploaded(self, publish_env):
        _, uploads, run = publish_env
        outcome = run(
            {
                "checkov": _tool(findings=[FINDING]),
                "opa": _tool(status="SKIPPED"),
                "trivy": _tool(status="FAIL"),
            }
        )
        assert [u["file"] for u in uploads] == ["thothctl-checkov.sarif"]
        assert sorted(outcome["incomplete_tools"]) == ["opa", "trivy"]

    def test_stale_and_generated_sarif_files_are_ignored(self, publish_env):
        reports, uploads, run = publish_env
        (reports / "trivy-results.sarif").write_text("{}")  # trivy did not run
        (reports / "scan_results.sarif").write_text("{}")  # --output sarif file
        (reports / "thothctl-old.sarif").write_text("{}")  # generated, not native
        run({"checkov": _tool(findings=[FINDING])})
        assert [u["file"] for u in uploads] == ["thothctl-checkov.sarif"]
        assert (reports / "scan_results.sarif").read_text() == "{}"

    def test_origin_service_overrides_tool_name(self, publish_env):
        _, uploads, run = publish_env
        run({"checkov": _tool(findings=[FINDING])}, origin_service="platform")
        assert uploads[0]["service"] == "platform"

    def test_failed_upload_marks_outcome_not_ok(self, publish_env):
        reports, _, _ = publish_env

        def failing(path, **kwargs):
            r = MagicMock()
            r.success = False
            r.error = "boom"
            return r

        with patch(
            "thothctl.services.inventory.secobserve_publisher.SecObservePublisher"
        ) as pub_cls, patch(
            "thothctl.services.inventory.secobserve_publisher.SecObserveConfig"
        ) as cfg_cls:
            cfg_cls.from_toml.return_value = MagicMock(
                url=BASE, product_name="infra", origin_service=None
            )
            pub_cls.return_value.publish_observations.side_effect = failing
            outcome = RestoredIaCScanCommand()._publish_scan_to_secobserve(
                {"checkov": _tool(findings=[FINDING])}, str(reports), "infra", str(reports)
            )
        assert outcome["attempted"] == 1
        assert outcome["published"] == 0
        assert outcome["ok"] is False

    def test_config_error_returns_outcome_without_publisher(self, publish_env):
        reports, _, _ = publish_env
        with patch(
            "thothctl.services.inventory.secobserve_publisher.SecObserveConfig"
        ) as cfg_cls, patch(
            "thothctl.services.inventory.secobserve_publisher.SecObservePublisher",
            side_effect=ValueError("SecObserve URL not configured"),
        ):
            cfg_cls.from_toml.return_value = MagicMock(product_name="infra")
            outcome = RestoredIaCScanCommand()._publish_scan_to_secobserve(
                {"checkov": _tool()}, str(reports), "infra", str(reports)
            )
        assert outcome["publisher"] is None
        assert outcome["ok"] is False


# ── --gate-source decision (end-to-end through the Click command) ────────────


def _scan_results(local_failed):
    failed = 3 if local_failed else 0
    return {
        "checkov": {
            "status": "COMPLETE",
            "report_data": {
                "passed_count": 10,
                "failed_count": failed,
                "error_count": 0,
                "skipped_count": 0,
            },
            "findings": [FINDING] if local_failed else [],
        },
        "summary": {"total_issues": failed},
    }


def _gate(passed, evaluated=True, error=None):
    return SecObserveGateResult(
        product_name="infra",
        evaluated=evaluated,
        passed=passed,
        active=passed is not None,
        source="product",
        counts={"critical": 0, "high": 2, "medium": 0, "low": 0},
        error=error,
    )


@pytest.fixture
def run_scan(tmp_path):
    """Invoke `scan iac` with the scanners and side effects mocked out."""
    reports = tmp_path / "Reports"
    reports.mkdir()

    def run(args, local_failed=False, gate=None, publisher_available=True):
        publisher = MagicMock()
        publisher.get_security_gate.return_value = gate
        outcome = {
            "publisher": publisher if publisher_available else None,
            "config": MagicMock(product_name="infra"),
            "attempted": 1,
            "published": 1,
            "incomplete_tools": [],
            "ok": True,
        }
        with patch(
            "thothctl.commands.scan.commands.iac.ScanService"
        ) as scan_cls, patch(
            "thothctl.services.scan.scan_history.get_previous_run", return_value=None
        ), patch(
            "thothctl.services.scan.scan_history.save_scan"
        ), patch(
            "thothctl.utils.common.render_scan_report.render_unified_report",
            return_value=str(reports / "scan_report.html"),
        ), patch.object(
            RestoredIaCScanCommand, "_publish_scan_to_secobserve", return_value=outcome
        ) as publish:
            scan_cls.return_value.execute_scans.return_value = _scan_results(local_failed)
            result = CliRunner().invoke(
                scan_iac_cli,
                ["-t", "checkov", "-r", str(reports), "-p", "infra", *args],
                obj={"CODE_DIRECTORY": str(tmp_path), "DEBUG": False},
            )
        return result, publish

    return run


SO = ["--publish-to", "secobserve"]


class TestGateSourceDecision:
    def test_gate_source_requires_publish_to_secobserve(self, run_scan):
        result, publish = run_scan(["--gate-source", "secobserve"])
        assert result.exit_code == 2
        assert "requires --publish-to secobserve" in result.output
        publish.assert_not_called()

    def test_local_default_unchanged(self, run_scan):
        result, _ = run_scan(["--enforcement", "hard"], local_failed=True)
        assert result.exit_code == 1
        result, _ = run_scan(["--enforcement", "hard"], local_failed=False)
        assert result.exit_code == 0

    def test_secobserve_failed_blocks_in_hard(self, run_scan):
        result, _ = run_scan(
            [*SO, "--gate-source", "secobserve", "--enforcement", "hard"],
            gate=_gate(passed=False),
        )
        assert result.exit_code == 1
        assert "SecObserve Security Gate" in result.output

    def test_secobserve_passed_ignores_local_findings(self, run_scan):
        result, _ = run_scan(
            [*SO, "--gate-source", "secobserve", "--enforcement", "hard"],
            local_failed=True,
            gate=_gate(passed=True),
        )
        assert result.exit_code == 0

    def test_secobserve_failed_soft_reports_only(self, run_scan):
        result, _ = run_scan(
            [*SO, "--gate-source", "secobserve", "--enforcement", "soft"],
            gate=_gate(passed=False),
        )
        assert result.exit_code == 0
        assert "not blocking" in result.output

    def test_inactive_gate_passes(self, run_scan):
        result, _ = run_scan(
            [*SO, "--gate-source", "secobserve", "--enforcement", "hard"],
            gate=_gate(passed=None),
        )
        assert result.exit_code == 0

    def test_unknown_gate_fails_closed(self, run_scan):
        result, _ = run_scan(
            [*SO, "--gate-source", "secobserve", "--enforcement", "hard"],
            gate=_gate(passed=None, evaluated=False, error="Could not query SecObserve"),
        )
        assert result.exit_code == 1

    def test_missing_publisher_fails_closed(self, run_scan):
        result, _ = run_scan(
            [*SO, "--gate-source", "secobserve", "--enforcement", "hard"],
            publisher_available=False,
        )
        assert result.exit_code == 1

    @pytest.mark.parametrize(
        "local_failed, gate_passed, expected",
        [
            (False, True, 0),
            (True, True, 1),
            (False, False, 1),
            (True, False, 1),
        ],
    )
    def test_both_fails_if_either_fails(self, run_scan, local_failed, gate_passed, expected):
        result, _ = run_scan(
            [*SO, "--gate-source", "both", "--enforcement", "hard"],
            local_failed=local_failed,
            gate=_gate(passed=gate_passed),
        )
        assert result.exit_code == expected

    def test_local_gate_source_does_not_query_secobserve(self, run_scan):
        with patch.object(RestoredIaCScanCommand, "_evaluate_secobserve_gate") as evaluate:
            result, publish = run_scan([*SO, "--enforcement", "hard"], local_failed=False)
        assert result.exit_code == 0
        publish.assert_called_once()
        evaluate.assert_not_called()


# ── Product group ─────────────────────────────────────────────────────────────


def _groups_route(*groups):
    return {"/api/product_groups/": {"results": list(groups)}}


class TestProductGroupConfig:
    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("SECOBSERVE_PRODUCT_GROUP", "platform")
        assert SecObserveConfig.from_env().product_group == "platform"

    def test_from_toml(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SECOBSERVE_PRODUCT_GROUP", raising=False)
        (tmp_path / ".thothcf.toml").write_text(
            '[integrations.secobserve]\nproduct_group = "from-toml"\n'
        )
        assert SecObserveConfig.from_toml(str(tmp_path)).product_group == "from-toml"

    def test_env_overrides_toml(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SECOBSERVE_PRODUCT_GROUP", "from-env")
        (tmp_path / ".thothcf.toml").write_text(
            '[integrations.secobserve]\nproduct_group = "from-toml"\n'
        )
        assert SecObserveConfig.from_toml(str(tmp_path)).product_group == "from-env"


class TestEnsureProductGroup:
    def test_new_product_joins_existing_group(self):
        pub = _publisher(
            {**_products_route(), **_groups_route({"id": 5, "name": "platform"})},
            post_routes={"/api/products/": ({"id": 42}, 201)},
            product_group="platform",
        )
        assert pub._ensure_product("infra") == 42
        assert pub._session.posts == [
            ("/api/products/", {"name": "infra", "description": "IaC project: infra", "product_group": 5})
        ]
        assert pub.warnings == []

    def test_group_name_is_exact_match(self):
        # The ?name= filter on product groups is a contains match too.
        pub = _publisher(
            {**_products_route(), **_groups_route({"id": 5, "name": "platform-legacy"})},
            post_routes={
                "/api/product_groups/": ({"id": 8}, 201),
                "/api/products/": ({"id": 42}, 201),
            },
            product_group="platform",
        )
        pub._ensure_product("infra")
        assert pub._session.posts[0][0] == "/api/product_groups/"
        assert pub._session.posts[1][1]["product_group"] == 8

    def test_missing_group_is_created(self):
        pub = _publisher(
            {**_products_route(), **_groups_route()},
            post_routes={
                "/api/product_groups/": ({"id": 8}, 201),
                "/api/products/": ({"id": 42}, 201),
            },
            product_group="platform",
        )
        assert pub._ensure_product("infra") == 42
        group_post, product_post = pub._session.posts
        assert group_post == (
            "/api/product_groups/",
            {"name": "platform", "description": "Product group managed by ThothCTL"},
        )
        assert product_post[1]["product_group"] == 8

    def test_group_not_created_without_auto_create(self):
        pub = _publisher(
            {**_products_route(), **_groups_route()},
            post_routes={"/api/products/": ({"id": 42}, 201)},
            product_group="platform",
            auto_create=False,
        )
        pub._ensure_product("infra")
        assert [p for p, _ in pub._session.posts] == ["/api/products/"]
        assert "product_group" not in pub._session.posts[0][1]
        assert "not found" in pub.warnings[0]

    def test_group_create_failure_creates_product_without_group(self):
        pub = _publisher(
            {**_products_route(), **_groups_route()},
            post_routes={
                "/api/product_groups/": ({"message": "Name: product with this name already exists."}, 400),
                "/api/products/": ({"id": 42}, 201),
            },
            product_group="platform",
        )
        assert pub._ensure_product("infra") == 42
        assert "product_group" not in pub._session.posts[1][1]
        assert "Could not create product group 'platform'" in pub.warnings[0]

    def test_existing_product_in_other_group_is_not_moved(self):
        product = _product(name="infra", product_group=2, product_group_name="legacy")
        pub = _publisher(
            {**_products_route(product), **_groups_route({"id": 5, "name": "platform"})},
            product_group="platform",
        )
        assert pub._ensure_product("infra") == 3
        assert pub._session.posts == []  # no create, no move
        assert len(pub.warnings) == 1
        assert "'legacy'" in pub.warnings[0] and "left unchanged" in pub.warnings[0]

    def test_existing_product_without_group_is_not_moved(self):
        pub = _publisher(
            {**_products_route(_product(name="infra")), **_groups_route({"id": 5, "name": "platform"})},
            product_group="platform",
        )
        pub._ensure_product("infra")
        assert pub._session.posts == []
        assert "'no group'" in pub.warnings[0]

    def test_existing_product_in_same_group_has_no_warning(self):
        product = _product(name="infra", product_group=5, product_group_name="platform")
        pub = _publisher(
            {**_products_route(product), **_groups_route({"id": 5, "name": "platform"})},
            product_group="platform",
        )
        pub._ensure_product("infra")
        assert pub.warnings == []

    def test_setup_runs_once_per_product(self):
        product = _product(name="infra", product_group=2, product_group_name="legacy")
        pub = _publisher(
            {**_products_route(product), **_groups_route({"id": 5, "name": "platform"})},
            product_group="platform",
        )
        pub._ensure_product("infra")
        pub._ensure_product("infra")
        assert len(pub.warnings) == 1  # one warning per run, not per upload

    def test_pop_warnings_clears(self):
        pub = _publisher({})
        pub.warnings.append("w")
        assert pub.pop_warnings() == ["w"]
        assert pub.warnings == []


class TestPublishSbomService:
    def test_sbom_sends_configured_service(self, tmp_path):
        sbom = tmp_path / "sbom_cyclonedx.json"
        sbom.write_text("{}")
        pub = _publisher(
            {},
            post_routes={"/api/import/file_upload_sbom_by_name/": ({"license_components_new": 1}, 200)},
            auto_create=False,
            origin_service="platform-svc",
        )
        result = pub.publish_sbom(sbom)
        assert result.success is True
        _, data = pub._session.posts[0]
        assert data["service"] == "platform-svc"
        assert data["product_name"] == "infra"

    def test_sbom_without_service_omits_field(self, tmp_path):
        sbom = tmp_path / "sbom_cyclonedx.json"
        sbom.write_text("{}")
        pub = _publisher(
            {},
            post_routes={"/api/import/file_upload_sbom_by_name/": ({}, 200)},
            auto_create=False,
        )
        pub.publish_sbom(sbom)
        assert "service" not in pub._session.posts[0][1]


class TestProductGroupFlag:
    def test_scan_requires_publish_to_secobserve(self, run_scan):
        result, publish = run_scan(["--product-group", "platform"])
        assert result.exit_code == 2
        assert "--product-group requires --publish-to secobserve" in result.output
        publish.assert_not_called()

    def test_scan_rejects_other_platform(self, run_scan):
        result, _ = run_scan(["--publish-to", "defectdojo", "--product-group", "platform"])
        assert result.exit_code == 2

    def test_scan_flag_overrides_config_and_warnings_are_shown(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SECOBSERVE_PRODUCT_GROUP", "from-env")
        seen = {}

        def make_publisher(config):
            seen["group"] = config.product_group
            pub = MagicMock()
            pub.publish_observations.return_value = MagicMock(
                success=True, observations_new=0, observations_updated=0, observations_resolved=0
            )
            pub.pop_warnings.return_value = ["Product 'infra' is in 'legacy', not 'from-flag'"]
            return pub

        cmd = RestoredIaCScanCommand()
        cmd._product_group = "from-flag"
        cmd.console = MagicMock()
        with patch(
            "thothctl.services.inventory.secobserve_publisher.SecObservePublisher",
            side_effect=make_publisher,
        ), patch.dict(
            "os.environ", {"SECOBSERVE_URL": BASE, "SECOBSERVE_API_TOKEN": "t"}
        ):
            cmd._publish_scan_to_secobserve(
                {"checkov": _tool(findings=[FINDING])}, str(tmp_path), "infra", str(tmp_path)
            )
        assert seen["group"] == "from-flag"
        printed = " ".join(str(c.args[0]) for c in cmd.console.print.call_args_list)
        assert "is in 'legacy'" in printed

    def test_inventory_requires_publish_sbom_secobserve(self, tmp_path):
        from thothctl.commands.inventory.commands.iac import cli as inventory_cli

        for extra in ([], ["--publish-sbom", "defectdojo"]):
            result = CliRunner().invoke(
                inventory_cli,
                ["--product-group", "platform", *extra],
                obj={"CODE_DIRECTORY": str(tmp_path), "DEBUG": False},
            )
            assert result.exit_code == 2, result.output
            assert "--product-group requires --publish-sbom secobserve" in result.output
