"""Unit tests for OPA cost policy enforcement integration."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestCostPolicyEnforcement:
    """Test the cost policy enforcement via conftest."""

    @pytest.fixture
    def cost_policy_dir(self, tmp_path):
        """Create a temporary cost policy directory with Rego + config."""
        policy_dir = tmp_path / "policy"
        policy_dir.mkdir()

        # config.yaml
        (policy_dir / "config.yaml").write_text(
            "budget:\n"
            "  max_monthly_total: 1000\n"
            "  warn_monthly_total: 500\n"
            "  expensive_resource_threshold: 100\n"
        )

        # budget.rego
        (policy_dir / "budget.rego").write_text(
            "package main\n\n"
            "import rego.v1\n\n"
            "deny contains msg if {\n"
            "    data.budget.max_monthly_total\n"
            "    input.summary.total_monthly_cost > data.budget.max_monthly_total\n"
            '    msg := sprintf("Total monthly cost $%.2f exceeds budget limit $%.2f", [\n'
            "        input.summary.total_monthly_cost,\n"
            "        data.budget.max_monthly_total,\n"
            "    ])\n"
            "}\n\n"
            "warn contains msg if {\n"
            "    data.budget.warn_monthly_total\n"
            "    input.summary.total_monthly_cost > data.budget.warn_monthly_total\n"
            "    input.summary.total_monthly_cost <= data.budget.max_monthly_total\n"
            '    msg := sprintf("Monthly cost $%.2f approaching budget limit", [\n'
            "        input.summary.total_monthly_cost,\n"
            "    ])\n"
            "}\n"
        )

        return str(policy_dir)

    @pytest.fixture
    def mock_cost_results_under_budget(self):
        """Cost results under budget ($200/month)."""
        analysis = MagicMock()
        analysis.total_monthly_cost = 200.0
        analysis.total_annual_cost = 2400.0
        analysis.analysis_metadata = {"total_running_monthly_cost": 200.0}
        analysis.resource_costs = []
        analysis.cost_breakdown_by_service = {"EC2": 200.0}
        return [{"stack": "test", "analysis": analysis}]

    @pytest.fixture
    def mock_cost_results_over_budget(self):
        """Cost results over budget ($1500/month)."""
        analysis = MagicMock()
        analysis.total_monthly_cost = 1500.0
        analysis.total_annual_cost = 18000.0
        analysis.analysis_metadata = {"total_running_monthly_cost": 1500.0}
        analysis.resource_costs = []
        analysis.cost_breakdown_by_service = {"RDS": 1000.0, "EC2": 500.0}
        return [{"stack": "production", "analysis": analysis}]

    @pytest.fixture
    def mock_cost_results_warn_zone(self):
        """Cost results in warn zone ($700/month — above warn, below deny)."""
        analysis = MagicMock()
        analysis.total_monthly_cost = 700.0
        analysis.total_annual_cost = 8400.0
        analysis.analysis_metadata = {"total_running_monthly_cost": 700.0}
        analysis.resource_costs = []
        analysis.cost_breakdown_by_service = {"EC2": 700.0}
        return [{"stack": "staging", "analysis": analysis}]

    def test_conftest_available(self):
        """Verify conftest is installed for tests."""
        result = subprocess.run(["conftest", "--version"], capture_output=True)
        assert result.returncode == 0

    def test_policy_validates(self, cost_policy_dir):
        """Cost policies parse without errors."""
        result = subprocess.run(
            ["conftest", "verify", "--policy", cost_policy_dir],
            capture_output=True, text=True,
        )
        assert "error" not in result.stdout.lower()

    def test_under_budget_passes(self, cost_policy_dir, mock_cost_results_under_budget, tmp_path):
        """Cost under $1000 budget should pass all policies."""
        input_data = {
            "summary": {"total_monthly_cost": 200.0, "total_running_monthly_cost": 200.0},
            "resources": [],
            "cost_by_service": {"EC2": 200.0},
        }
        input_file = tmp_path / "cost_input.json"
        input_file.write_text(json.dumps(input_data))

        # Prepare data files (YAML → JSON)
        import yaml
        config = yaml.safe_load((Path(cost_policy_dir) / "config.yaml").read_text())
        (Path(cost_policy_dir) / "config.json").write_text(json.dumps(config))

        result = subprocess.run(
            ["conftest", "test", str(input_file),
             "--policy", cost_policy_dir,
             "--data", str(Path(cost_policy_dir) / "config.json"),
             "--output", "json"],
            capture_output=True, text=True,
        )
        results = json.loads(result.stdout)
        failures = []
        for r in results:
            failures.extend(r.get("failures", []))
        assert len(failures) == 0

    def test_over_budget_denies(self, cost_policy_dir, tmp_path):
        """Cost over $1000 budget should trigger deny."""
        input_data = {
            "summary": {"total_monthly_cost": 1500.0, "total_running_monthly_cost": 1500.0},
            "resources": [],
            "cost_by_service": {"RDS": 1500.0},
        }
        input_file = tmp_path / "cost_input.json"
        input_file.write_text(json.dumps(input_data))

        import yaml
        config = yaml.safe_load((Path(cost_policy_dir) / "config.yaml").read_text())
        (Path(cost_policy_dir) / "config.json").write_text(json.dumps(config))

        result = subprocess.run(
            ["conftest", "test", str(input_file),
             "--policy", cost_policy_dir,
             "--data", str(Path(cost_policy_dir) / "config.json"),
             "--output", "json"],
            capture_output=True, text=True,
        )
        results = json.loads(result.stdout)
        failures = []
        for r in results:
            failures.extend(r.get("failures", []))
        assert len(failures) >= 1
        assert "exceeds budget" in failures[0]["msg"]

    def test_warn_zone_warns_but_passes(self, cost_policy_dir, tmp_path):
        """Cost in warn zone ($500-$1000) should warn but not deny."""
        input_data = {
            "summary": {"total_monthly_cost": 700.0, "total_running_monthly_cost": 700.0},
            "resources": [],
            "cost_by_service": {"EC2": 700.0},
        }
        input_file = tmp_path / "cost_input.json"
        input_file.write_text(json.dumps(input_data))

        import yaml
        config = yaml.safe_load((Path(cost_policy_dir) / "config.yaml").read_text())
        (Path(cost_policy_dir) / "config.json").write_text(json.dumps(config))

        result = subprocess.run(
            ["conftest", "test", str(input_file),
             "--policy", cost_policy_dir,
             "--data", str(Path(cost_policy_dir) / "config.json"),
             "--output", "json"],
            capture_output=True, text=True,
        )
        results = json.loads(result.stdout)
        failures = []
        warnings = []
        for r in results:
            failures.extend(r.get("failures", []))
            warnings.extend(r.get("warnings", []))
        assert len(failures) == 0
        assert len(warnings) >= 1
        assert "approaching budget" in warnings[0]["msg"]

    def test_exact_budget_passes(self, cost_policy_dir, tmp_path):
        """Cost exactly at limit ($1000) should pass (uses > not >=)."""
        input_data = {
            "summary": {"total_monthly_cost": 1000.0, "total_running_monthly_cost": 1000.0},
            "resources": [],
            "cost_by_service": {"EC2": 1000.0},
        }
        input_file = tmp_path / "cost_input.json"
        input_file.write_text(json.dumps(input_data))

        import yaml
        config = yaml.safe_load((Path(cost_policy_dir) / "config.yaml").read_text())
        (Path(cost_policy_dir) / "config.json").write_text(json.dumps(config))

        result = subprocess.run(
            ["conftest", "test", str(input_file),
             "--policy", cost_policy_dir,
             "--data", str(Path(cost_policy_dir) / "config.json"),
             "--output", "json"],
            capture_output=True, text=True,
        )
        results = json.loads(result.stdout)
        failures = []
        for r in results:
            failures.extend(r.get("failures", []))
        # $1000 is NOT > $1000, so should pass
        assert len(failures) == 0
