"""Unit tests for CloudFormation/CDK project type detection and scan routing."""
import json
from pathlib import Path

import pytest

from thothctl.services.scan.scan_service import ScanService
from thothctl.services.scan.scanners.checkov import CheckovScanner


class TestDetectProjectType:
    """Test detect_project_type method."""

    @pytest.fixture
    def scan_service(self):
        return ScanService()

    def test_terraform_project(self, tmp_path, scan_service):
        (tmp_path / "main.tf").write_text('resource "aws_vpc" "main" {}')
        assert scan_service.detect_project_type(str(tmp_path)) == "terraform"

    def test_terragrunt_project(self, tmp_path, scan_service):
        (tmp_path / "terragrunt.hcl").write_text('include "root" {}')
        assert scan_service.detect_project_type(str(tmp_path)) == "terraform"

    def test_cloudformation_yaml(self, tmp_path, scan_service):
        (tmp_path / "template.yaml").write_text(
            "AWSTemplateFormatVersion: '2010-09-09'\nResources:\n  MyBucket:\n    Type: AWS::S3::Bucket\n"
        )
        assert scan_service.detect_project_type(str(tmp_path)) == "cloudformation"

    def test_cloudformation_json(self, tmp_path, scan_service):
        template = {"AWSTemplateFormatVersion": "2010-09-09", "Resources": {"Vpc": {"Type": "AWS::EC2::VPC"}}}
        (tmp_path / "stack.json").write_text(json.dumps(template))
        assert scan_service.detect_project_type(str(tmp_path)) == "cloudformation"

    def test_cdk_project_with_cdk_json(self, tmp_path, scan_service):
        (tmp_path / "cdk.json").write_text('{"app": "npx ts-node bin/app.ts"}')
        assert scan_service.detect_project_type(str(tmp_path)) == "cdk"

    def test_cdk_project_with_cdk_out(self, tmp_path, scan_service):
        (tmp_path / "cdk.out").mkdir()
        (tmp_path / "cdk.out" / "MyStack.template.json").write_text("{}")
        assert scan_service.detect_project_type(str(tmp_path)) == "cdk"

    def test_terraform_takes_precedence_over_cfn(self, tmp_path, scan_service):
        """When both .tf and CFN templates exist, prefer terraform."""
        (tmp_path / "main.tf").write_text('resource "aws_vpc" "main" {}')
        (tmp_path / "template.yaml").write_text(
            "AWSTemplateFormatVersion: '2010-09-09'\nResources:\n  X:\n    Type: AWS::S3::Bucket\n"
        )
        assert scan_service.detect_project_type(str(tmp_path)) == "terraform"

    def test_cdk_takes_precedence_over_terraform(self, tmp_path, scan_service):
        """CDK with cdk.json takes priority."""
        (tmp_path / "cdk.json").write_text('{"app": "..."}')
        (tmp_path / "main.tf").write_text("")
        assert scan_service.detect_project_type(str(tmp_path)) == "cdk"

    def test_empty_directory_defaults_to_terraform(self, tmp_path, scan_service):
        assert scan_service.detect_project_type(str(tmp_path)) == "terraform"


class TestFindCloudFormationTemplates:
    """Test _find_cloudformation_templates method."""

    @pytest.fixture
    def scan_service(self):
        return ScanService()

    def test_finds_yaml_template(self, tmp_path, scan_service):
        (tmp_path / "template.yaml").write_text(
            "AWSTemplateFormatVersion: '2010-09-09'\nResources:\n  Bucket:\n    Type: AWS::S3::Bucket\n"
        )
        result = scan_service._find_cloudformation_templates(str(tmp_path))
        assert len(result) == 1
        assert "template.yaml" in result[0]

    def test_finds_json_template(self, tmp_path, scan_service):
        template = {"Resources": {"Vpc": {"Type": "AWS::EC2::VPC", "Properties": {}}}}
        (tmp_path / "infra.json").write_text(json.dumps(template))
        result = scan_service._find_cloudformation_templates(str(tmp_path))
        assert len(result) == 1

    def test_ignores_non_cfn_yaml(self, tmp_path, scan_service):
        (tmp_path / "config.yaml").write_text("key: value\nother: data\n")
        result = scan_service._find_cloudformation_templates(str(tmp_path))
        assert len(result) == 0

    def test_ignores_dot_files(self, tmp_path, scan_service):
        (tmp_path / ".hidden.yaml").write_text("AWSTemplateFormatVersion: '2010-09-09'\n")
        result = scan_service._find_cloudformation_templates(str(tmp_path))
        assert len(result) == 0

    def test_ignores_excluded_directories(self, tmp_path, scan_service):
        node_dir = tmp_path / "node_modules" / "pkg"
        node_dir.mkdir(parents=True)
        (node_dir / "template.yaml").write_text("AWSTemplateFormatVersion: '2010-09-09'\nResources:\n  X:\n    Type: AWS::S3::Bucket\n")
        result = scan_service._find_cloudformation_templates(str(tmp_path))
        assert len(result) == 0

    def test_finds_nested_templates(self, tmp_path, scan_service):
        nested = tmp_path / "stacks" / "network"
        nested.mkdir(parents=True)
        (nested / "vpc.yaml").write_text(
            "AWSTemplateFormatVersion: '2010-09-09'\nResources:\n  VPC:\n    Type: AWS::EC2::VPC\n"
        )
        result = scan_service._find_cloudformation_templates(str(tmp_path))
        assert len(result) == 1

    def test_finds_multiple_templates(self, tmp_path, scan_service):
        (tmp_path / "network.yaml").write_text("Resources:\n  VPC:\n    Type: AWS::EC2::VPC\n")
        (tmp_path / "database.yml").write_text("Resources:\n  DB:\n    Type: AWS::RDS::DBInstance\n")
        result = scan_service._find_cloudformation_templates(str(tmp_path))
        assert len(result) == 2


class TestFindCDKTemplates:
    """Test _find_cdk_templates method."""

    @pytest.fixture
    def scan_service(self):
        return ScanService()

    def test_finds_cdk_out_templates(self, tmp_path, scan_service):
        cdk_out = tmp_path / "cdk.out"
        cdk_out.mkdir()
        (cdk_out / "MyStack.template.json").write_text("{}")
        (cdk_out / "AnotherStack.template.json").write_text("{}")
        result = scan_service._find_cdk_templates(str(tmp_path))
        assert len(result) == 2

    def test_no_cdk_out_returns_empty(self, tmp_path, scan_service):
        result = scan_service._find_cdk_templates(str(tmp_path))
        assert result == []

    def test_ignores_non_template_files(self, tmp_path, scan_service):
        cdk_out = tmp_path / "cdk.out"
        cdk_out.mkdir()
        (cdk_out / "manifest.json").write_text("{}")
        (cdk_out / "tree.json").write_text("{}")
        (cdk_out / "MyStack.template.json").write_text("{}")
        result = scan_service._find_cdk_templates(str(tmp_path))
        assert len(result) == 1  # Only .template.json


class TestCheckovFrameworkOption:
    """Test that Checkov _build_command passes --framework correctly."""

    def test_no_framework_by_default(self):
        scanner = CheckovScanner()
        cmd = scanner._build_command("/dir", {})
        assert "--framework" not in cmd

    def test_framework_cloudformation(self):
        scanner = CheckovScanner()
        cmd = scanner._build_command("/dir", {"framework": "cloudformation"})
        assert "--framework" in cmd
        idx = cmd.index("--framework")
        assert cmd[idx + 1] == "cloudformation"

    def test_framework_with_compact(self):
        scanner = CheckovScanner()
        cmd = scanner._build_command("/dir", {"framework": "cloudformation", "compact": True})
        assert "--framework" in cmd
        assert "--compact" in cmd
