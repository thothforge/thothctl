"""Unit tests for Phase 1.10: Secure Plan Validation.

Tests StateResolver, PlanRunner, and PlanValidator with mocked subprocesses.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from thothctl.services.generate.intent.models import (
    GeneratedFile,
    PlanContext,
    PlanMode,
    PlanResult,
    StateConfig,
    ValidationResult,
    Violation,
)
from thothctl.services.generate.intent.plan_runner import PlanRunner
from thothctl.services.generate.intent.plan_validator import PlanValidator
from thothctl.services.generate.intent.state_resolver import StateResolver


# ==================================================================
# StateResolver Tests
# ==================================================================


class TestStateResolver(unittest.TestCase):
    """Test StateResolver context resolution and file management."""

    def setUp(self):
        self.resolver = StateResolver()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_terragrunt_project_returns_in_place(self):
        """Terragrunt projects should use in-place validation."""
        context = self.resolver.resolve(
            project_dir=self.temp_dir,
            project_type="terraform-terragrunt",
            stack_path="stacks/network/vpc",
            plan_mode=PlanMode.PER_STACK,
        )
        self.assertTrue(context.is_in_place)
        self.assertEqual(context.project_type, "terraform-terragrunt")
        self.assertIn("stacks/network/vpc", context.work_dir)

    def test_resolve_terraform_project_returns_temp_workspace(self):
        """Plain terraform projects should use temp workspace."""
        context = self.resolver.resolve(
            project_dir=self.temp_dir,
            project_type="terraform",
            plan_mode=PlanMode.TERRAFORM,
        )
        self.assertFalse(context.is_in_place)
        self.assertEqual(context.work_dir, "")

    def test_write_files_for_plan_creates_tf_files(self):
        """Writing files for plan creates them in the work_dir."""
        stack_dir = os.path.join(self.temp_dir, "stacks", "network", "vpc")
        context = PlanContext(
            mode=PlanMode.PER_STACK,
            work_dir=stack_dir,
            project_type="terraform-terragrunt",
            stack_path="stacks/network/vpc",
            is_in_place=True,
            written_files=[],
        )
        files = [
            GeneratedFile(path="main.tf", content='resource "aws_vpc" "main" {}'),
            GeneratedFile(path="variables.tf", content='variable "name" {}'),
        ]

        updated = self.resolver.write_files_for_plan(files, context)

        self.assertTrue((Path(stack_dir) / "main.tf").exists())
        self.assertTrue((Path(stack_dir) / "variables.tf").exists())
        self.assertEqual(len(updated.written_files), 2)

    def test_write_files_skips_non_tf(self):
        """Non-.tf files should be skipped during write."""
        stack_dir = os.path.join(self.temp_dir, "stacks", "test")
        context = PlanContext(
            mode=PlanMode.PER_STACK,
            work_dir=stack_dir,
            project_type="terraform-terragrunt",
            stack_path="stacks/test",
            is_in_place=True,
            written_files=[],
        )
        files = [
            GeneratedFile(path="main.tf", content='resource "aws_vpc" "main" {}'),
            GeneratedFile(path="README.md", content="# Readme"),
        ]

        updated = self.resolver.write_files_for_plan(files, context)

        self.assertTrue((Path(stack_dir) / "main.tf").exists())
        self.assertFalse((Path(stack_dir) / "README.md").exists())
        self.assertEqual(len(updated.written_files), 1)

    def test_rollback_removes_written_files(self):
        """Rollback should remove all written files."""
        stack_dir = os.path.join(self.temp_dir, "stacks", "rollback_test")
        os.makedirs(stack_dir, exist_ok=True)

        # Create a file
        main_tf = os.path.join(stack_dir, "main.tf")
        Path(main_tf).write_text('resource "aws_vpc" "main" {}')

        context = PlanContext(
            mode=PlanMode.PER_STACK,
            work_dir=stack_dir,
            project_type="terraform-terragrunt",
            stack_path="stacks/rollback_test",
            is_in_place=True,
            written_files=[main_tf],
        )

        self.resolver.rollback(context)
        self.assertFalse(Path(main_tf).exists())

    def test_rollback_restores_backups(self):
        """Rollback should restore backup files."""
        stack_dir = os.path.join(self.temp_dir, "stacks", "backup_test")
        os.makedirs(stack_dir, exist_ok=True)

        # Create a backup file
        backup = os.path.join(stack_dir, "main.tf.thothctl_bak")
        Path(backup).write_text("original content")

        context = PlanContext(
            mode=PlanMode.PER_STACK,
            work_dir=stack_dir,
            project_type="terraform-terragrunt",
            stack_path="stacks/backup_test",
            is_in_place=True,
            written_files=[backup],
        )

        self.resolver.rollback(context)

        original = os.path.join(stack_dir, "main.tf")
        self.assertTrue(Path(original).exists())
        self.assertEqual(Path(original).read_text(), "original content")

    def test_rollback_noop_for_temp_workspace(self):
        """Rollback should be no-op for temp workspace mode."""
        context = PlanContext(
            mode=PlanMode.TERRAFORM,
            work_dir="/tmp/some_dir",
            project_type="terraform",
            is_in_place=False,
            written_files=[],
        )
        # Should not raise
        self.resolver.rollback(context)

    def test_detect_terragrunt_project_with_root_hcl(self):
        """Should detect terragrunt project with root.hcl."""
        Path(self.temp_dir, "root.hcl").write_text("# root config")
        self.assertTrue(self.resolver.detect_terragrunt_project(self.temp_dir))

    def test_detect_terragrunt_project_without_root_hcl(self):
        """Should not detect terragrunt without root.hcl."""
        self.assertFalse(self.resolver.detect_terragrunt_project(self.temp_dir))


# ==================================================================
# PlanRunner Tests
# ==================================================================


class TestPlanRunner(unittest.TestCase):
    """Test PlanRunner subprocess execution with mocked commands."""

    def setUp(self):
        self.runner = PlanRunner(
            project_type="terraform-terragrunt",
            tftool="tofu",
            config={"plan_timeout": 60, "provider_cache": True},
        )

    @patch("shutil.which")
    def test_terragrunt_plan_no_binary(self, mock_which):
        """Should return skipped when terragrunt binary not found."""
        mock_which.return_value = None
        result = self.runner.run_per_stack("/tmp/fake")
        self.assertTrue(result.skipped)
        self.assertIn("not found", result.skip_reason)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_terragrunt_plan_no_terragrunt_hcl(self, mock_which, mock_run):
        """Should return skipped when no terragrunt.hcl in stack dir."""
        mock_which.return_value = "/usr/local/bin/terragrunt"
        temp = tempfile.mkdtemp()
        try:
            result = self.runner.run_per_stack(temp)
            self.assertTrue(result.skipped)
            self.assertIn("terragrunt.hcl", result.skip_reason)
        finally:
            shutil.rmtree(temp)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_terragrunt_plan_success(self, mock_which, mock_run):
        """Successful plan should return no violations."""
        mock_which.return_value = "/usr/local/bin/terragrunt"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr=""
        )

        temp = tempfile.mkdtemp()
        Path(temp, "terragrunt.hcl").write_text("include \"root\" {}")
        try:
            result = self.runner.run_per_stack(temp)
            self.assertFalse(result.skipped)
            self.assertTrue(result.plan_succeeded)
            self.assertEqual(len(result.violations), 0)
        finally:
            shutil.rmtree(temp)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_terragrunt_plan_failure_parses_errors(self, mock_which, mock_run):
        """Failed plan should parse error output into violations."""
        mock_which.return_value = "/usr/local/bin/terragrunt"
        error_output = (
            'Error: Invalid instance type\n'
            '  "t3.nano" is not available in us-east-1a\n'
        )
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr=error_output
        )

        temp = tempfile.mkdtemp()
        Path(temp, "terragrunt.hcl").write_text("include \"root\" {}")
        try:
            result = self.runner.run_per_stack(temp)
            self.assertFalse(result.plan_succeeded)
            self.assertTrue(len(result.violations) > 0)
            self.assertEqual(result.violations[0].tool, "plan")
        finally:
            shutil.rmtree(temp)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_terragrunt_plan_timeout(self, mock_which, mock_run):
        """Timeout should return skipped result."""
        import subprocess

        mock_which.return_value = "/usr/local/bin/terragrunt"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="terragrunt", timeout=60)

        temp = tempfile.mkdtemp()
        Path(temp, "terragrunt.hcl").write_text("include \"root\" {}")
        try:
            result = self.runner.run_per_stack(temp)
            self.assertTrue(result.skipped)
            self.assertIn("timed out", result.skip_reason)
        finally:
            shutil.rmtree(temp)

    def test_build_terragrunt_plan_cmd_basic(self):
        """Basic command should include non-interactive and provider-cache."""
        cmd = self.runner._build_terragrunt_plan_cmd()
        self.assertIn("terragrunt", cmd)
        self.assertIn("plan", cmd)
        self.assertIn("--non-interactive", cmd)
        self.assertIn("--provider-cache", cmd)
        self.assertIn("--no-color", cmd)

    def test_build_terragrunt_plan_cmd_with_iam_role(self):
        """Command should include IAM role when configured."""
        runner = PlanRunner(
            project_type="terraform-terragrunt",
            config={
                "iam_assume_role": "arn:aws:iam::123:role/plan-ro",
                "session_duration": 900,
            },
        )
        cmd = runner._build_terragrunt_plan_cmd()
        self.assertIn("--iam-assume-role", cmd)
        self.assertIn("arn:aws:iam::123:role/plan-ro", cmd)
        self.assertIn("--iam-assume-role-duration", cmd)
        self.assertIn("900", cmd)

    def test_parse_streaming_json_extracts_errors(self):
        """Should parse terraform plan -json streaming output."""
        json_lines = (
            '{"@level":"info","@message":"Terraform plan"}\n'
            '{"@level":"error","type":"diagnostic","diagnostic":{'
            '"severity":"error","summary":"Invalid type",'
            '"detail":"t3.nano not available",'
            '"range":{"filename":"main.tf","start":{"line":5}}}}\n'
        )
        violations = self.runner._parse_streaming_json(json_lines)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].severity, "HIGH")
        self.assertIn("t3.nano", violations[0].message)
        self.assertEqual(violations[0].file_path, "main.tf:5")

    def test_parse_streaming_json_handles_empty(self):
        """Empty output should return no violations."""
        violations = self.runner._parse_streaming_json("")
        self.assertEqual(len(violations), 0)

    def test_parse_streaming_json_handles_invalid_json(self):
        """Invalid JSON lines should be skipped gracefully."""
        violations = self.runner._parse_streaming_json("not json\nalso not json\n")
        self.assertEqual(len(violations), 0)


# ==================================================================
# PlanValidator Tests
# ==================================================================


class TestPlanValidator(unittest.TestCase):
    """Test PlanValidator orchestration and mode routing."""

    def test_disabled_mode_returns_empty(self):
        """Disabled mode should never run plan and return empty."""
        pv = PlanValidator(config={"plan_validation": "disabled"})
        self.assertFalse(pv.is_enabled)
        result = pv.validate_per_stack(
            files=[GeneratedFile(path="main.tf", content="")],
            project_dir="/tmp",
        )
        self.assertEqual(result, [])

    def test_enabled_mode_detects_correctly(self):
        """Per-stack mode should be detected as enabled."""
        pv = PlanValidator(
            config={"plan_validation": "per-stack"},
            project_type="terraform-terragrunt",
        )
        self.assertTrue(pv.is_enabled)
        self.assertEqual(pv.mode, PlanMode.PER_STACK)

    def test_full_project_mode(self):
        """Full-project mode should be detected."""
        pv = PlanValidator(
            config={"plan_validation": "full-project"},
            project_type="terraform-terragrunt",
        )
        self.assertEqual(pv.mode, PlanMode.FULL_PROJECT)

    def test_invalid_mode_defaults_to_disabled(self):
        """Invalid mode string should default to disabled."""
        pv = PlanValidator(config={"plan_validation": "invalid_mode"})
        self.assertEqual(pv.mode, PlanMode.DISABLED)
        self.assertFalse(pv.is_enabled)

    @patch("shutil.which")
    def test_validate_per_stack_no_binary_returns_empty(self, mock_which):
        """Missing terragrunt binary should return empty violations."""
        mock_which.return_value = None
        pv = PlanValidator(
            config={"plan_validation": "per-stack"},
            project_type="terraform-terragrunt",
        )
        result = pv.validate_per_stack(
            files=[GeneratedFile(path="main.tf", content="")],
            project_dir="/tmp",
        )
        self.assertEqual(result, [])

    def test_validate_full_project_disabled_returns_empty(self):
        """Disabled validator should return empty for full project."""
        pv = PlanValidator(config={"plan_validation": "disabled"})
        result = pv.validate_full_project(project_dir="/tmp")
        self.assertEqual(result, [])


# ==================================================================
# PlanResult / Model Tests
# ==================================================================


class TestPlanResultModel(unittest.TestCase):
    """Test PlanResult data model."""

    def test_has_errors_with_high_severity(self):
        """Should detect HIGH severity violations."""
        result = PlanResult(
            violations=[
                Violation(
                    check_id="TF_PLAN",
                    severity="HIGH",
                    resource="aws_instance.web",
                    message="Invalid type",
                    tool="plan",
                )
            ]
        )
        self.assertTrue(result.has_errors)

    def test_has_errors_with_low_severity(self):
        """LOW severity should not count as error."""
        result = PlanResult(
            violations=[
                Violation(
                    check_id="TF_PLAN",
                    severity="LOW",
                    resource="",
                    message="Warning",
                    tool="plan",
                )
            ]
        )
        self.assertFalse(result.has_errors)

    def test_skipped_result(self):
        """Skipped result should have no violations."""
        result = PlanResult(skipped=True, skip_reason="No binary")
        self.assertEqual(len(result.violations), 0)
        self.assertEqual(result.skip_reason, "No binary")


class TestValidationResultPlanFormat(unittest.TestCase):
    """Test ValidationResult.format_for_ai() with plan violations."""

    def test_plan_violations_formatted_separately(self):
        """Plan violations should appear in their own section."""
        vr = ValidationResult(
            passed=False,
            violations=[
                Violation(
                    check_id="TF_PLAN",
                    severity="HIGH",
                    resource="aws_instance.web",
                    message='"t3.nano" is not a valid instance type',
                    file_path="main.tf:12",
                    tool="plan",
                ),
                Violation(
                    check_id="CKV_AWS_79",
                    severity="HIGH",
                    resource="aws_instance.web",
                    message="Enable IMDSv2",
                    tool="checkov",
                ),
            ],
        )
        formatted = vr.format_for_ai()
        self.assertIn("PLAN/DEPLOYABILITY ERRORS", formatted)
        self.assertIn("SECURITY VIOLATIONS", formatted)
        self.assertIn("instance type", formatted)

    def test_plan_fix_hint_instance_type(self):
        """Should provide instance type fix hint."""
        from thothctl.services.generate.intent.models import ValidationResult

        hint = ValidationResult._get_plan_fix_hint("t3.nano is not a valid instance type")
        self.assertIn("valid instance type", hint)

    def test_plan_fix_hint_reference_error(self):
        """Should provide reference fix hint."""
        from thothctl.services.generate.intent.models import ValidationResult

        hint = ValidationResult._get_plan_fix_hint("resource reference not found")
        self.assertIn("reference", hint)

    def test_plan_fix_hint_generic(self):
        """Unknown patterns should get generic hint."""
        from thothctl.services.generate.intent.models import ValidationResult

        hint = ValidationResult._get_plan_fix_hint("some unknown error xyz")
        self.assertIn("provider documentation", hint)


if __name__ == "__main__":
    unittest.main()
