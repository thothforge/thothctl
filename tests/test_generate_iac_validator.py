"""Unit tests for Intent-to-IaC validator."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from thothctl.services.generate.intent.models import GeneratedFile, Violation
from thothctl.services.generate.intent.validator import GenerationValidator


class TestCreateTempWorkspace:
    """Test temp directory creation."""

    def setup_method(self):
        self.validator = GenerationValidator()

    def test_creates_files(self):
        """Files are written to temp dir with correct content."""
        files = [
            GeneratedFile("main.tf", 'resource "aws_vpc" "main" {}'),
            GeneratedFile("variables.tf", 'variable "cidr" {}'),
        ]
        temp_dir = self.validator._create_temp_workspace(files)
        try:
            assert os.path.exists(temp_dir)
            assert (
                Path(temp_dir) / "main.tf"
            ).read_text() == 'resource "aws_vpc" "main" {}'
            assert (Path(temp_dir) / "variables.tf").read_text() == 'variable "cidr" {}'
        finally:
            self.validator._cleanup_temp(temp_dir)

    def test_preserves_nested_paths(self):
        """Files with directory paths are created with proper structure."""
        files = [
            GeneratedFile("stacks/foundation/vpc/main.tf", "resource {}"),
            GeneratedFile("stacks/foundation/vpc/terragrunt.hcl", "include {}"),
        ]
        temp_dir = self.validator._create_temp_workspace(files)
        try:
            assert (
                Path(temp_dir) / "stacks" / "foundation" / "vpc" / "main.tf"
            ).exists()
            assert (
                Path(temp_dir) / "stacks" / "foundation" / "vpc" / "terragrunt.hcl"
            ).exists()
        finally:
            self.validator._cleanup_temp(temp_dir)

    def test_cleanup_removes_temp(self):
        """Cleanup removes the temp directory."""
        files = [GeneratedFile("test.tf", "x")]
        temp_dir = self.validator._create_temp_workspace(files)
        self.validator._cleanup_temp(temp_dir)
        assert not os.path.exists(temp_dir)


class TestValidateWithMockedScanners:
    """Test the validate method with mocked scanners."""

    def setup_method(self):
        self.validator = GenerationValidator()

    @patch(
        "thothctl.services.generate.intent.validator.GenerationValidator._run_checkov"
    )
    def test_passes_when_no_violations(self, mock_checkov):
        """No violations → passed=True."""
        mock_checkov.return_value = []

        files = [GeneratedFile("main.tf", 'resource "aws_vpc" "main" {}')]
        result = self.validator.validate(files)

        assert result.passed is True
        assert result.total_violations == 0

    @patch(
        "thothctl.services.generate.intent.validator.GenerationValidator._run_checkov"
    )
    def test_fails_when_violations_found(self, mock_checkov):
        """Violations → passed=False."""
        mock_checkov.return_value = [
            Violation("CKV_AWS_130", "HIGH", "aws_vpc.main", "Enable flow logs"),
            Violation(
                "CKV_AWS_23", "MEDIUM", "aws_security_group.main", "Add description"
            ),
        ]

        files = [GeneratedFile("main.tf", "resource {}")]
        result = self.validator.validate(files)

        assert result.passed is False
        assert result.total_violations == 2
        assert result.high_count == 1
        assert result.checkov_failed == 2

    @patch("thothctl.services.generate.intent.validator.GenerationValidator._run_opa")
    @patch(
        "thothctl.services.generate.intent.validator.GenerationValidator._run_checkov"
    )
    def test_combines_checkov_and_opa_violations(self, mock_checkov, mock_opa):
        """Both scanners contribute to total violations."""
        mock_checkov.return_value = [
            Violation(
                "CKV_AWS_130", "HIGH", "aws_vpc.main", "Flow logs", tool="checkov"
            ),
        ]
        mock_opa.return_value = [
            Violation(
                "OPA_TAGS",
                "MEDIUM",
                "aws_vpc.main",
                "Missing CostCenter tag",
                tool="opa",
            ),
        ]

        files = [GeneratedFile("main.tf", "resource {}")]
        result = self.validator.validate(files, org_policy_dir="/fake/policies")

        assert result.passed is False
        assert result.total_violations == 2
        assert result.checkov_failed == 1
        assert result.opa_failed == 1

    @patch(
        "thothctl.services.generate.intent.validator.GenerationValidator._run_checkov"
    )
    def test_skip_checkov_flag(self, mock_checkov):
        """skip_checkov=True skips Checkov entirely."""
        files = [GeneratedFile("main.tf", "resource {}")]
        result = self.validator.validate(files, skip_checkov=True)

        mock_checkov.assert_not_called()
        assert result.passed is True

    def test_empty_files_passes(self):
        """No files → immediate pass."""
        result = self.validator.validate([])
        assert result.passed is True

    @patch(
        "thothctl.services.generate.intent.validator.GenerationValidator._run_checkov"
    )
    def test_opa_skipped_without_policy_dir(self, mock_checkov):
        """OPA not called when no policy_dir provided."""
        mock_checkov.return_value = []

        files = [GeneratedFile("main.tf", "resource {}")]
        result = self.validator.validate(files, org_policy_dir=None)

        assert result.passed is True

    @patch(
        "thothctl.services.generate.intent.validator.GenerationValidator._run_checkov"
    )
    def test_format_for_ai(self, mock_checkov):
        """ValidationResult.format_for_ai() produces readable text for self-correction."""
        mock_checkov.return_value = [
            Violation("CKV_AWS_130", "HIGH", "aws_vpc.main", "Enable VPC flow logs"),
            Violation(
                "CKV_AWS_145", "MEDIUM", "aws_s3_bucket.data", "Enable S3 encryption"
            ),
        ]

        files = [GeneratedFile("main.tf", "resource {}")]
        result = self.validator.validate(files)

        ai_text = result.format_for_ai()
        assert "CKV_AWS_130" in ai_text
        assert "CKV_AWS_145" in ai_text
        assert "[HIGH]" in ai_text
        assert "aws_vpc.main" in ai_text


class TestParseCheckovResult:
    """Test Checkov result parsing."""

    def setup_method(self):
        self.validator = GenerationValidator()

    def test_parse_findings_list(self):
        """Parse from 'findings' list format."""
        result = {
            "status": "COMPLETE",
            "findings": [
                {
                    "id": "CKV_AWS_130",
                    "severity": "HIGH",
                    "resource": "aws_vpc.main",
                    "title": "Enable flow logs",
                    "file": "main.tf",
                },
                {
                    "id": "CKV_AWS_23",
                    "severity": "MEDIUM",
                    "resource": "aws_sg.main",
                    "title": "Add description",
                    "file": "main.tf",
                },
            ],
        }
        violations = self.validator._parse_checkov_result(result)
        assert len(violations) == 2
        assert violations[0].check_id == "CKV_AWS_130"
        assert violations[0].severity == "HIGH"
        assert violations[1].severity == "MEDIUM"

    def test_parse_empty_findings(self):
        """No findings → empty list."""
        result = {"status": "COMPLETE", "findings": []}
        violations = self.validator._parse_checkov_result(result)
        assert len(violations) == 0

    def test_parse_non_dict_returns_empty(self):
        """Non-dict input → empty list."""
        assert self.validator._parse_checkov_result(None) == []
        assert self.validator._parse_checkov_result("error") == []

    def test_parse_json_report_files(self):
        """Parse from Checkov native JSON report files."""
        temp_dir = tempfile.mkdtemp()
        try:
            report_data = [
                {
                    "results": {
                        "failed_checks": [
                            {
                                "check_id": "CKV_AWS_18",
                                "severity": "MEDIUM",
                                "resource": "aws_s3_bucket.logs",
                                "name": "Enable S3 logging",
                                "file_path": "main.tf",
                            },
                        ]
                    }
                }
            ]
            report_file = Path(temp_dir) / "checkov_results.json"
            report_file.write_text(json.dumps(report_data))

            violations = self.validator._parse_checkov_json_reports(temp_dir)
            assert len(violations) == 1
            assert violations[0].check_id == "CKV_AWS_18"
        finally:
            import shutil

            shutil.rmtree(temp_dir)


class TestParseOpaResult:
    """Test OPA result parsing."""

    def setup_method(self):
        self.validator = GenerationValidator()

    def test_parse_findings(self):
        """Parse OPA findings."""
        result = {
            "findings": [
                {
                    "rule": "deny_public_s3",
                    "severity": "HIGH",
                    "resource": "aws_s3_bucket.public",
                    "message": "Public S3 not allowed",
                },
                {
                    "rule": "require_tags",
                    "severity": "MEDIUM",
                    "resource": "aws_vpc.main",
                    "message": "Missing required tags",
                },
            ]
        }
        violations = self.validator._parse_opa_result(result)
        assert len(violations) == 2
        assert violations[0].tool == "opa"
        assert violations[0].check_id == "deny_public_s3"

    def test_parse_empty(self):
        """No findings → empty."""
        result = {"findings": []}
        assert self.validator._parse_opa_result(result) == []

    def test_parse_non_dict(self):
        """Invalid input → empty."""
        assert self.validator._parse_opa_result(None) == []


class TestCheckovSeverityNormalization:
    """Test severity string normalization."""

    def setup_method(self):
        self.validator = GenerationValidator()

    def test_standard_values_pass_through(self):
        assert self.validator._checkov_severity("CRITICAL") == "CRITICAL"
        assert self.validator._checkov_severity("HIGH") == "HIGH"
        assert self.validator._checkov_severity("MEDIUM") == "MEDIUM"
        assert self.validator._checkov_severity("LOW") == "LOW"

    def test_alternate_names_mapped(self):
        assert self.validator._checkov_severity("ERROR") == "HIGH"
        assert self.validator._checkov_severity("WARNING") == "MEDIUM"
        assert self.validator._checkov_severity("INFO") == "LOW"

    def test_case_insensitive(self):
        assert self.validator._checkov_severity("high") == "HIGH"
        assert self.validator._checkov_severity("Critical") == "CRITICAL"

    def test_unknown_defaults_to_medium(self):
        assert self.validator._checkov_severity("UNKNOWN") == "MEDIUM"
        assert self.validator._checkov_severity("") == "MEDIUM"
        assert self.validator._checkov_severity(None) == "MEDIUM"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
