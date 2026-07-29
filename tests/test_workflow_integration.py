"""Integration tests for ThothCTL workflow pipeline."""

import json
from pathlib import Path

import pytest
import yaml


class TestWorkflowBuildPhase:
    """Test the build phase (inventory) on a CDK project."""

    @pytest.fixture
    def cdk_project(self, tmp_path):
        """Create a minimal CDK project structure."""
        (tmp_path / "cdk.json").write_text(
            json.dumps({"app": "npx ts-node bin/app.ts"})
        )
        (tmp_path / "package.json").write_text(
            json.dumps(
                {
                    "name": "test-cdk-project",
                    "version": "1.0.0",
                    "dependencies": {
                        "aws-cdk-lib": "^2.262.0",
                        "constructs": "^10.7.0",
                        "cdk-nag": "^3.0.1",
                    },
                    "devDependencies": {
                        "aws-cdk": "2.1133.0",
                        "typescript": "~5.9.3",
                    },
                }
            )
        )
        (tmp_path / "bin").mkdir()
        (tmp_path / "bin" / "app.ts").write_text(
            'import * as cdk from "aws-cdk-lib";\nconst app = new cdk.App();'
        )
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "stack.ts").write_text(
            'import * as cdk from "aws-cdk-lib";\n'
            "export class MyStack extends cdk.Stack {}"
        )
        return tmp_path

    def test_inventory_creates_json_report(self, cdk_project):
        """Test that inventory iac produces a JSON report for CDK project."""
        import asyncio

        from thothctl.services.inventory.inventory_service import InventoryService

        service = InventoryService()
        result = asyncio.run(
            service.create_inventory(
                source_directory=str(cdk_project),
                check_versions=False,
                report_type="json",
                reports_directory=str(cdk_project / "Reports"),
                print_console=False,
            )
        )

        assert result is not None
        assert result.get("projectType") == "cdkv2"
        assert len(result.get("components", [])) > 0

        # Check components contain CDK constructs
        all_comps = [c for g in result["components"] for c in g.get("components", [])]
        names = [c["name"] for c in all_comps]
        assert "aws-cdk-lib" in names
        assert "constructs" in names

    def test_inventory_generates_sbom(self, cdk_project):
        """Test that inventory generates CycloneDX SBOM for CDK."""
        import asyncio

        from thothctl.services.inventory.inventory_service import InventoryService

        service = InventoryService()
        reports_dir = str(cdk_project / "Reports")
        asyncio.run(
            service.create_inventory(
                source_directory=str(cdk_project),
                check_versions=False,
                report_type="cyclonedx",
                reports_directory=reports_dir,
                print_console=False,
            )
        )

        # Check SBOM file was created in Reports/inventory/
        sbom_files = list(Path(reports_dir).rglob("*cyclonedx*.json"))
        assert len(sbom_files) > 0

        sbom = json.loads(sbom_files[0].read_text())
        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.6"
        assert len(sbom["components"]) >= 3

        # Check PURLs
        purls = [c["purl"] for c in sbom["components"]]
        assert any("pkg:npm/aws-cdk-lib" in p for p in purls)


class TestCustomWorkflowEngine:
    """Test the composable YAML workflow engine."""

    @pytest.fixture
    def workflow_file(self, tmp_path):
        """Create a test workflow YAML.

        Note: The engine prepends 'thothctl' to commands via _build_command_string,
        so we use '--version' which thothctl handles as a valid flag.
        """
        workflow = {
            "name": "test-pipeline",
            "description": "Integration test workflow",
            "stages": [
                {
                    "name": "version-check",
                    "command": "--version",
                },
                {
                    "name": "depends-on-version",
                    "command": "--version",
                    "depends_on": ["version-check"],
                },
            ],
        }
        path = tmp_path / "workflow.yaml"
        path.write_text(yaml.dump(workflow))
        return path

    def test_load_valid_workflow(self, workflow_file):
        """Test loading a valid workflow YAML."""
        from thothctl.services.workflow.custom_workflow_engine import (
            CustomWorkflowEngine,
        )

        engine = CustomWorkflowEngine()
        workflow = engine.load(workflow_file)

        assert workflow.name == "test-pipeline"
        assert len(workflow.stages) == 2
        assert workflow.stages[1].depends_on == ["version-check"]

    def test_detect_circular_dependency(self, tmp_path):
        """Test that circular dependencies are rejected."""
        from thothctl.services.workflow.custom_workflow_engine import (
            CustomWorkflowEngine,
            WorkflowValidationError,
        )

        workflow = {
            "name": "circular",
            "stages": [
                {"name": "a", "command": "--version", "depends_on": ["b"]},
                {"name": "b", "command": "--version", "depends_on": ["a"]},
            ],
        }
        path = tmp_path / "circular.yaml"
        path.write_text(yaml.dump(workflow))

        engine = CustomWorkflowEngine()
        with pytest.raises(WorkflowValidationError, match="Circular"):
            engine.load(path)

    def test_execute_simple_workflow(self, workflow_file):
        """Test executing a simple workflow (thothctl --version succeeds)."""
        from thothctl.services.workflow.custom_workflow_engine import (
            CustomWorkflowEngine,
            StageStatus,
        )

        engine = CustomWorkflowEngine()
        workflow = engine.load(workflow_file)
        results = engine.execute(workflow)

        assert len(results) == 2
        assert all(r.status == StageStatus.SUCCESS for r in results)

    def test_on_failure_block(self, tmp_path):
        """Test that on_failure=block stops the pipeline.

        Uses a nonexistent subcommand which will cause thothctl to exit non-zero.
        """
        from thothctl.services.workflow.custom_workflow_engine import (
            CustomWorkflowEngine,
            StageStatus,
        )

        workflow = {
            "name": "fail-test",
            "stages": [
                {
                    "name": "fail",
                    "command": "nonexistent-subcommand-xyz",
                    "on_failure": "block",
                },
                {
                    "name": "after",
                    "command": "--version",
                    "depends_on": ["fail"],
                },
            ],
        }
        path = tmp_path / "fail.yaml"
        path.write_text(yaml.dump(workflow))

        engine = CustomWorkflowEngine()
        wf = engine.load(path)
        results = engine.execute(wf)

        assert results[0].status == StageStatus.FAILED
        assert results[1].status == StageStatus.SKIPPED

    def test_on_failure_warn_continues(self, tmp_path):
        """Test that on_failure=warn continues the pipeline.

        The first stage fails (nonexistent command) but with warn mode,
        the second stage (thothctl --version) still runs.
        """
        from thothctl.services.workflow.custom_workflow_engine import (
            CustomWorkflowEngine,
            StageStatus,
        )

        workflow = {
            "name": "warn-test",
            "stages": [
                {
                    "name": "fail",
                    "command": "nonexistent-subcommand-xyz",
                    "on_failure": "warn",
                },
                {
                    "name": "after",
                    "command": "--version",
                    "depends_on": ["fail"],
                },
            ],
        }
        path = tmp_path / "warn.yaml"
        path.write_text(yaml.dump(workflow))

        engine = CustomWorkflowEngine()
        wf = engine.load(path)
        results = engine.execute(wf)

        assert results[0].status == StageStatus.WARNED
        assert results[1].status == StageStatus.SUCCESS


class TestQuickstartDetection:
    """Test quickstart project detection logic."""

    def test_detect_cdk_project(self, tmp_path):
        """Test CDK project detection."""
        from thothctl.commands.quickstart.cli import detect_project_type

        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "package.json").write_text("{}")
        assert detect_project_type(tmp_path) == "cdkv2"

    def test_detect_terragrunt(self, tmp_path):
        """Test Terragrunt detection."""
        from thothctl.commands.quickstart.cli import detect_project_type

        (tmp_path / "terragrunt.hcl").write_text("")
        assert detect_project_type(tmp_path) == "terraform-terragrunt"

    def test_detect_terraform(self, tmp_path):
        """Test Terraform detection."""
        from thothctl.commands.quickstart.cli import detect_project_type

        (tmp_path / "main.tf").write_text("")
        assert detect_project_type(tmp_path) == "terraform"

    def test_detect_from_thothcf(self, tmp_path):
        """Test detection from .thothcf.toml."""
        import toml

        from thothctl.commands.quickstart.cli import detect_project_type

        (tmp_path / ".thothcf.toml").write_text(
            toml.dumps({"thothcf": {"project_type": "tofu"}})
        )
        assert detect_project_type(tmp_path) == "tofu"

    def test_detect_nothing(self, tmp_path):
        """Test no detection for empty dir."""
        from thothctl.commands.quickstart.cli import detect_project_type

        assert detect_project_type(tmp_path) is None
