"""Unit tests for fix patterns and fix generation."""

import pytest
from thothctl.services.ai_review.utils.fix_patterns import (
    get_pattern_fix, list_supported_checks, _PATTERNS,
)


class TestListSupportedChecks:
    def test_returns_list(self):
        checks = list_supported_checks()
        assert isinstance(checks, list)
        assert len(checks) > 0

    def test_check_structure(self):
        checks = list_supported_checks()
        for c in checks:
            assert "check_id" in c
            assert "description" in c
            assert c["check_id"].startswith("CKV_AWS_")

    def test_matches_patterns_dict(self):
        checks = list_supported_checks()
        assert len(checks) == len(_PATTERNS)


class TestGetPatternFix:
    def test_known_check_returns_fix(self):
        finding = {
            "check_id": "CKV_AWS_19",
            "severity": "HIGH",
            "resource": "aws_s3_bucket.data",
            "file": "s3.tf",
        }
        fix = get_pattern_fix("CKV_AWS_19", finding, {})
        assert fix is not None
        assert fix["finding_id"] == "CKV_AWS_19"
        assert fix["severity"] == "HIGH"
        assert fix["file"] == "s3.tf"
        assert "encryption" in fix["description"].lower()

    def test_unknown_check_returns_none(self):
        finding = {"check_id": "CKV_AWS_99999", "severity": "LOW", "resource": "", "file": ""}
        fix = get_pattern_fix("CKV_AWS_99999", finding, {})
        assert fix is None

    def test_s3_versioning(self):
        finding = {"check_id": "CKV_AWS_21", "severity": "MEDIUM",
                    "resource": "aws_s3_bucket.logs", "file": "s3.tf"}
        fix = get_pattern_fix("CKV_AWS_21", finding, {})
        assert fix is not None
        assert "versioning" in fix["description"].lower()
        assert "logs" in fix["replacement"]

    def test_rds_encryption(self):
        finding = {"check_id": "CKV_AWS_16", "severity": "HIGH",
                    "resource": "aws_db_instance.main", "file": "rds.tf"}
        fix = get_pattern_fix("CKV_AWS_16", finding, {})
        assert fix is not None
        assert fix["fix_type"] == "add_attribute"
        assert "storage_encrypted" in fix["replacement"]

    def test_rds_public_access(self):
        finding = {"check_id": "CKV_AWS_17", "severity": "HIGH",
                    "resource": "aws_db_instance.main", "file": "rds.tf"}
        fix = get_pattern_fix("CKV_AWS_17", finding, {})
        assert fix is not None
        assert "publicly_accessible" in fix["replacement"]
        assert "false" in fix["replacement"]

    def test_security_group_description(self):
        finding = {"check_id": "CKV_AWS_23", "severity": "LOW",
                    "resource": "aws_security_group.web", "file": "sg.tf"}
        fix = get_pattern_fix("CKV_AWS_23", finding, {})
        assert fix is not None
        assert "description" in fix["replacement"]

    def test_ssh_cidr_restriction(self):
        finding = {"check_id": "CKV_AWS_24", "severity": "HIGH",
                    "resource": "aws_security_group_rule.ssh", "file": "sg.tf"}
        fix = get_pattern_fix("CKV_AWS_24", finding, {})
        assert fix is not None
        assert "0.0.0.0/0" in fix["original"]
        assert "var.allowed_ssh_cidrs" in fix["replacement"]

    def test_ebs_encryption(self):
        finding = {"check_id": "CKV_AWS_3", "severity": "HIGH",
                    "resource": "aws_ebs_volume.data", "file": "ebs.tf"}
        fix = get_pattern_fix("CKV_AWS_3", finding, {})
        assert fix is not None
        assert "encrypted" in fix["replacement"]

    def test_fix_has_validation(self):
        finding = {"check_id": "CKV_AWS_19", "severity": "HIGH",
                    "resource": "aws_s3_bucket.x", "file": "s3.tf"}
        fix = get_pattern_fix("CKV_AWS_19", finding, {})
        assert "checkov" in fix["validation"]
        assert "CKV_AWS_19" in fix["validation"]

    def test_resource_name_extraction(self):
        finding = {"check_id": "CKV_AWS_21", "severity": "MEDIUM",
                    "resource": "aws_s3_bucket.my_special_bucket", "file": "s3.tf"}
        fix = get_pattern_fix("CKV_AWS_21", finding, {})
        assert "my_special_bucket" in fix["replacement"]


class TestPatternFixes:
    """Test AIReviewAgent._pattern_fixes static method."""

    def test_generates_fixes_for_known_checks(self):
        from thothctl.services.ai_review.ai_agent import AIReviewAgent

        scan = {
            "total_findings": 2,
            "tools": {"checkov": {"findings": [
                {"check_id": "CKV_AWS_19", "severity": "HIGH",
                 "resource": "aws_s3_bucket.a", "file": "s3.tf"},
                {"check_id": "CKV_AWS_16", "severity": "HIGH",
                 "resource": "aws_db_instance.b", "file": "rds.tf"},
            ]}},
        }
        result = AIReviewAgent._pattern_fixes(scan, {}, "medium")
        assert result["summary"]["fixes_generated"] == 2
        assert result["summary"]["skipped"] == 0
        assert len(result["fixes"]) == 2

    def test_skips_unknown_checks(self):
        from thothctl.services.ai_review.ai_agent import AIReviewAgent

        scan = {
            "total_findings": 1,
            "tools": {"checkov": {"findings": [
                {"check_id": "CKV_AWS_99999", "severity": "HIGH",
                 "resource": "aws_x.y", "file": "main.tf"},
            ]}},
        }
        result = AIReviewAgent._pattern_fixes(scan, {}, "medium")
        assert result["summary"]["fixes_generated"] == 0
        assert result["summary"]["skipped"] == 1

    def test_severity_filter(self):
        from thothctl.services.ai_review.ai_agent import AIReviewAgent

        scan = {
            "total_findings": 2,
            "tools": {"checkov": {"findings": [
                {"check_id": "CKV_AWS_19", "severity": "HIGH",
                 "resource": "aws_s3_bucket.a", "file": "s3.tf"},
                {"check_id": "CKV_AWS_23", "severity": "LOW",
                 "resource": "aws_security_group.b", "file": "sg.tf"},
            ]}},
        }
        result = AIReviewAgent._pattern_fixes(scan, {}, "high")
        # Only HIGH severity should be included
        assert result["summary"]["fixes_generated"] == 1

    def test_empty_scan(self):
        from thothctl.services.ai_review.ai_agent import AIReviewAgent

        scan = {"total_findings": 0, "tools": {}}
        result = AIReviewAgent._pattern_fixes(scan, {}, "medium")
        assert result["summary"]["fixes_generated"] == 0
        assert len(result["fixes"]) == 0
