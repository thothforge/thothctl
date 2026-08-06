"""Tests for Intent-to-IaC quick wins: framework validation, structured errors, diagram generation."""

import os
import tempfile
import unittest

from thothctl.services.generate.intent.intent_service import IntentToIaCService
from thothctl.services.generate.intent.models import (
    GeneratedFile,
    IntentResult,
    ValidationResult,
    Violation,
)
from thothctl.services.generate.intent.validator import GenerationValidator


class TestFrameworkValidation(unittest.TestCase):
    """Test framework-specific validation dispatch."""

    def setUp(self):
        self.validator = GenerationValidator()

    def test_valid_terraform_passes(self):
        """Valid Terraform file should pass framework validation."""
        files = [
            GeneratedFile(
                path="main.tf",
                content='variable "name" {\n  type = string\n  default = "test"\n}\n',
            )
        ]
        result = self.validator.validate(
            files, project_type="terraform", skip_checkov=True, skip_opa=True
        )
        self.assertTrue(result.passed)
        self.assertEqual(len(result.violations), 0)

    def test_invalid_terraform_caught(self):
        """Invalid Terraform references should be caught by terraform validate."""
        files = [
            GeneratedFile(
                path="main.tf",
                content='output "x" {\n  value = nonexistent.resource.id\n}\n',
            )
        ]
        result = self.validator.validate(
            files, project_type="terraform", skip_checkov=True, skip_opa=True
        )
        self.assertFalse(result.passed)
        self.assertGreater(len(result.violations), 0)
        self.assertEqual(result.violations[0].tool, "framework")
        self.assertEqual(result.violations[0].severity, "HIGH")

    def test_cloudformation_dispatch(self):
        """CloudFormation validation should not crash (cfn-lint may not be installed)."""
        files = [
            GeneratedFile(
                path="template.yaml",
                content='AWSTemplateFormatVersion: "2010-09-09"\nResources:\n  B:\n    Type: AWS::S3::Bucket\n',
            )
        ]
        # Should not raise, even if cfn-lint is unavailable
        result = self.validator.validate(
            files, project_type="cloudformation", skip_checkov=True, skip_opa=True
        )
        self.assertIsInstance(result, ValidationResult)

    def test_cdk_dispatch_without_cdk_json(self):
        """CDK validation should gracefully skip when no cdk.json exists."""
        files = [
            GeneratedFile(
                path="lib/stack.ts",
                content='import * as cdk from "aws-cdk-lib";\n',
            )
        ]
        result = self.validator.validate(
            files, project_type="cdkv2", skip_checkov=True, skip_opa=True
        )
        # Should pass (skipped gracefully)
        self.assertTrue(result.passed)

    def test_sam_dispatch(self):
        """SAM validation dispatch should not crash."""
        files = [
            GeneratedFile(
                path="template.yaml",
                content='AWSTemplateFormatVersion: "2010-09-09"\nTransform: AWS::Serverless-2016-10-31\nResources:\n  F:\n    Type: AWS::Serverless::Function\n    Properties:\n      Runtime: python3.12\n      Handler: app.handler\n',
            )
        ]
        result = self.validator.validate(
            files, project_type="sam", skip_checkov=True, skip_opa=True
        )
        self.assertIsInstance(result, ValidationResult)

    def test_skip_framework_validate(self):
        """skip_framework_validate should bypass framework validation."""
        files = [
            GeneratedFile(
                path="main.tf",
                content='output "x" {\n  value = broken.ref.id\n}\n',
            )
        ]
        result = self.validator.validate(
            files,
            project_type="terraform",
            skip_checkov=True,
            skip_opa=True,
            skip_framework_validate=True,
        )
        # No framework violations when skipped
        fw_violations = [v for v in result.violations if v.tool == "framework"]
        self.assertEqual(len(fw_violations), 0)


class TestStructuredViolations(unittest.TestCase):
    """Test the improved format_for_ai output."""

    def test_format_groups_by_tool(self):
        """format_for_ai should group violations by tool type."""
        result = ValidationResult(
            passed=False,
            violations=[
                Violation(
                    check_id="TF_VALIDATE",
                    severity="HIGH",
                    resource="aws_vpc.main",
                    message="Missing cidr_block",
                    file_path="main.tf:3",
                    tool="framework",
                ),
                Violation(
                    check_id="CKV_AWS_130",
                    severity="HIGH",
                    resource="aws_vpc.main",
                    message="Ensure VPC has flow logs",
                    tool="checkov",
                ),
                Violation(
                    check_id="ORG_TAGS",
                    severity="MEDIUM",
                    resource="aws_vpc.main",
                    message="Missing tag: Owner",
                    tool="opa",
                ),
            ],
        )
        output = result.format_for_ai()
        # Should contain all sections
        self.assertIn("SCHEMA/SYNTAX ERRORS", output)
        self.assertIn("SECURITY VIOLATIONS", output)
        self.assertIn("POLICY VIOLATIONS", output)
        self.assertIn("fix these first", output)
        self.assertIn("INSTRUCTIONS", output)

    def test_format_includes_fix_hints(self):
        """format_for_ai should include known fix hints."""
        result = ValidationResult(
            passed=False,
            violations=[
                Violation(
                    check_id="CKV_AWS_145",
                    severity="HIGH",
                    resource="aws_s3_bucket.data",
                    message="Ensure S3 bucket has encryption",
                    tool="checkov",
                ),
            ],
        )
        output = result.format_for_ai()
        self.assertIn("server_side_encryption_configuration", output)

    def test_format_empty_violations(self):
        """Empty violations returns simple message."""
        result = ValidationResult(passed=True, violations=[])
        self.assertEqual(result.format_for_ai(), "No violations found.")


class TestDiagramGeneration(unittest.TestCase):
    """Test Mermaid diagram generation from generated resources."""

    def setUp(self):
        self.svc = IntentToIaCService.__new__(IntentToIaCService)

    def test_extract_terraform_resources(self):
        """Extract resource types from Terraform files."""
        files = [
            GeneratedFile(
                path="main.tf",
                content='resource "aws_vpc" "main" {}\nresource "aws_s3_bucket" "data" {}\n',
            )
        ]
        resources = self.svc._extract_resource_types(files)
        self.assertIn("aws_vpc.main", resources)
        self.assertIn("aws_s3_bucket.data", resources)

    def test_extract_cloudformation_resources(self):
        """Extract resource types from CloudFormation templates."""
        files = [
            GeneratedFile(
                path="template.yaml",
                content="  Type: AWS::EC2::VPC\n  Type: AWS::S3::Bucket\n  Type: AWS::Lambda::Function\n",
            )
        ]
        resources = self.svc._extract_resource_types(files)
        self.assertIn("AWS::EC2::VPC", resources)
        self.assertIn("AWS::S3::Bucket", resources)
        self.assertIn("AWS::Lambda::Function", resources)

    def test_extract_cdk_resources(self):
        """Extract resource types from CDK constructs."""
        files = [
            GeneratedFile(
                path="lib/stack.ts",
                content='const vpc = new ec2.Vpc(this, "VPC");\nconst bucket = new s3.Bucket(this, "Data");\n',
            )
        ]
        resources = self.svc._extract_resource_types(files)
        self.assertIn("aws_ec2_vpc", resources)
        self.assertIn("aws_s3_bucket", resources)

    def test_build_mermaid_layers(self):
        """Mermaid diagram groups resources into layers."""
        resources = [
            "aws_vpc.main",
            "aws_subnet.private",
            "aws_instance.web",
            "aws_s3_bucket.data",
            "aws_db_instance.postgres",
        ]
        diagram = self.svc._build_mermaid_diagram(resources)
        self.assertIn("graph TB", diagram)
        self.assertIn("Network Layer", diagram)
        self.assertIn("Compute Layer", diagram)
        self.assertIn("Storage Layer", diagram)
        self.assertIn("Database Layer", diagram)

    def test_build_mermaid_connections(self):
        """Mermaid diagram includes inter-layer connections."""
        resources = [
            "aws_vpc.main",
            "aws_instance.web",
            "aws_s3_bucket.data",
        ]
        diagram = self.svc._build_mermaid_diagram(resources)
        self.assertIn("-->", diagram)

    def test_diagram_written_to_file(self):
        """_generate_diagram writes architecture.md to output dir."""
        tmpdir = tempfile.mkdtemp()
        files = [
            GeneratedFile(
                path="main.tf",
                content='resource "aws_vpc" "main" {}\nresource "aws_instance" "web" {}\n',
            )
        ]
        result = self.svc._generate_diagram(tmpdir, files=files)
        self.assertIsNotNone(result)

        # Check file was written
        diagram_file = os.path.join(tmpdir, "architecture.md")
        self.assertTrue(os.path.exists(diagram_file))
        content = open(diagram_file).read()
        self.assertIn("```mermaid", content)
        self.assertIn("graph TB", content)

    def test_intent_result_includes_diagram(self):
        """IntentResult model should accept diagram field."""
        result = IntentResult(
            success=True,
            diagram="graph TB\n    A --> B",
        )
        self.assertEqual(result.diagram, "graph TB\n    A --> B")
        self.assertIn("diagram", result.to_dict())


if __name__ == "__main__":
    unittest.main()
