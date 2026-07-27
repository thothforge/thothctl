"""Unit tests for Intent-to-IaC models and context builder."""

import shutil
import tempfile
from pathlib import Path

import pytest

from thothctl.services.generate.intent.context_builder import ContextBuilder
from thothctl.services.generate.intent.models import (
    ContextPayload,
    GeneratedFile,
    GenerationOutput,
    IntentResult,
    ValidationResult,
    Violation,
)


class TestModels:
    """Test data models."""

    def test_generated_file(self):
        f = GeneratedFile(
            path="stacks/vpc/main.tf", content='resource "aws_vpc" "main" {}'
        )
        assert f.path == "stacks/vpc/main.tf"
        assert "aws_vpc" in f.content

    def test_generation_output_properties(self):
        out = GenerationOutput(
            files=[
                GeneratedFile("a.tf", "line1\nline2"),
                GeneratedFile("b.tf", "line1\nline2\nline3"),
            ],
            explanation="test",
        )
        assert out.file_count == 2
        assert out.total_lines == 5

    def test_violation_model(self):
        v = Violation(
            check_id="CKV_AWS_130",
            severity="HIGH",
            resource="aws_vpc.main",
            message="Ensure VPC flow logs are enabled",
            tool="checkov",
        )
        assert v.check_id == "CKV_AWS_130"
        assert v.severity == "HIGH"

    def test_validation_result_format_for_ai(self):
        vr = ValidationResult(
            passed=False,
            violations=[
                Violation("CKV_AWS_130", "HIGH", "aws_vpc.main", "Enable flow logs"),
                Violation(
                    "CKV_AWS_178", "MEDIUM", "aws_nat_gateway.main", "Multi-AZ NAT"
                ),
            ],
        )
        text = vr.format_for_ai()
        assert "CKV_AWS_130" in text
        assert "CKV_AWS_178" in text
        assert "[HIGH]" in text
        assert "[MEDIUM]" in text

    def test_validation_result_counts(self):
        vr = ValidationResult(
            passed=False,
            violations=[
                Violation("CKV1", "CRITICAL", "r1", "msg1"),
                Violation("CKV2", "HIGH", "r2", "msg2"),
                Violation("CKV3", "HIGH", "r3", "msg3"),
                Violation("CKV4", "MEDIUM", "r4", "msg4"),
            ],
        )
        assert vr.total_violations == 4
        assert vr.critical_count == 1
        assert vr.high_count == 2

    def test_context_payload_compile(self):
        payload = ContextPayload(
            project_type="terraform-terragrunt",
            project_config="- Project type: terraform\n- Environment: prod",
            iac_rules="Use terraform-aws-modules first",
            existing_patterns="### Example: main.tf\n```hcl\nresource...\n```",
        )
        compiled = payload.compile()
        assert "# Organizational Context" in compiled
        assert "## Project Configuration" in compiled
        assert "## IaC Rules" in compiled
        assert "## Existing Patterns" in compiled
        assert payload.total_tokens_estimate > 0

    def test_context_payload_empty_sections_excluded(self):
        payload = ContextPayload(project_type="terraform", project_config="config only")
        compiled = payload.compile()
        assert "## Project Configuration" in compiled
        assert "## IaC Rules" not in compiled
        assert "## Existing Patterns" not in compiled

    def test_intent_result_to_dict(self):
        result = IntentResult(
            success=True,
            files=[GeneratedFile("main.tf", "resource {}")],
            validation=ValidationResult(passed=True),
            iterations=1,
            explanation="Generated VPC",
            modules_used=["terraform-aws-modules/vpc/aws@5.0.0"],
            estimated_resources=["aws_vpc", "aws_subnet"],
        )
        d = result.to_dict()
        assert d["success"] is True
        assert len(d["files"]) == 1
        assert d["validation"]["passed"] is True
        assert d["modules_used"] == ["terraform-aws-modules/vpc/aws@5.0.0"]


class TestContextBuilder:
    """Test the context builder."""

    def setup_method(self):
        """Create a temp project directory with realistic structure."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create .thothcf.toml
        (self.temp_dir / ".thothcf.toml").write_text(
            "[thothcf]\n"
            'project_id = "my-infra"\n'
            'project_type = "terraform"\n\n'
            "[template_input_parameters.project_name]\n"
            'template_value = "my-platform"\n'
            'condition = "^[a-zA-Z0-9\\\\-]+$"\n'
            'description = "Project Name"\n\n'
            "[template_input_parameters.environment]\n"
            'template_value = "prod"\n'
            'condition = "(dev|qa|stg|prod)"\n'
            'description = "Environment"\n\n'
            "[project_structure]\n"
            'root_files = ["README.md", ".gitignore"]\n'
        )

        # Create .kiro/steering/
        steering_dir = self.temp_dir / ".kiro" / "steering"
        steering_dir.mkdir(parents=True)
        (steering_dir / "iac-rules.md").write_text(
            "# IaC Rules\n\n"
            "## Module Sources\n"
            "- Use terraform-aws-modules first\n"
            "- Pin exact versions\n\n"
            "## Mandatory Tags\n"
            "- Environment, Owner, CostCenter\n"
        )
        (steering_dir / "product.md").write_text(
            "# Product Overview\n\n"
            "Enterprise AWS infrastructure with layered architecture.\n"
        )

        # Create stacks/ with example files
        vpc_dir = self.temp_dir / "stacks" / "foundation" / "network" / "vpc"
        vpc_dir.mkdir(parents=True)
        (vpc_dir / "terragrunt.hcl").write_text(
            'include "root" {\n'
            '  path = find_in_parent_folders("root.hcl")\n'
            "}\n\n"
            "inputs = {\n"
            '  vpc_cidr = "10.0.0.0/16"\n'
            '  tags = { Environment = "prod" }\n'
            "}\n"
        )
        (vpc_dir / "main.tf").write_text(
            'module "vpc" {\n'
            '  source  = "terraform-aws-modules/vpc/aws"\n'
            '  version = "5.17.0"\n'
            "}\n"
        )

        # Create root.hcl (marks as terragrunt project)
        (self.temp_dir / "root.hcl").write_text("# Root config\n")

        # Create policies/ with a .rego file
        policies_dir = self.temp_dir / "policies"
        policies_dir.mkdir()
        (policies_dir / "tags.rego").write_text(
            "package terraform.tags\n\n"
            "# Ensure all resources have required tags\n"
            "deny[msg] {\n"
            "  resource := input.resource_changes[_]\n"
            "  not resource.change.after.tags.Environment\n"
            '  msg := sprintf("Missing Environment tag: %s", [resource.address])\n'
            "}\n"
        )

        self.builder = ContextBuilder()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_build_context_returns_payload(self):
        payload = self.builder.build_context(str(self.temp_dir))
        assert isinstance(payload, ContextPayload)
        assert payload.project_type == "terraform-terragrunt"

    def test_loads_thothcf_config(self):
        payload = self.builder.build_context(str(self.temp_dir))
        assert "Project type: terraform" in payload.project_config
        assert "project_name" in payload.project_config
        assert "environment" in payload.project_config
        assert "prod" in payload.project_config

    def test_loads_iac_rules(self):
        payload = self.builder.build_context(str(self.temp_dir))
        assert "terraform-aws-modules" in payload.iac_rules
        assert "Mandatory Tags" in payload.iac_rules

    def test_loads_project_overview(self):
        payload = self.builder.build_context(str(self.temp_dir))
        assert "Enterprise AWS" in payload.project_overview

    def test_loads_existing_patterns(self):
        payload = self.builder.build_context(str(self.temp_dir))
        assert (
            "terragrunt.hcl" in payload.existing_patterns
            or "main.tf" in payload.existing_patterns
        )
        assert "find_in_parent_folders" in payload.existing_patterns

    def test_loads_org_policies(self):
        payload = self.builder.build_context(str(self.temp_dir))
        assert (
            "tags" in payload.org_policies or "terraform.tags" in payload.org_policies
        )

    def test_compile_produces_full_context(self):
        payload = self.builder.build_context(str(self.temp_dir))
        compiled = payload.compile()
        assert "# Organizational Context" in compiled
        assert "## Project Configuration" in compiled
        assert "## IaC Rules" in compiled
        assert payload.total_tokens_estimate > 0
        assert payload.total_tokens_estimate < 10000  # Should be under 10K tokens

    def test_auto_detects_terragrunt(self):
        """root.hcl present → terraform-terragrunt."""
        payload = self.builder.build_context(str(self.temp_dir), project_type="auto")
        assert payload.project_type == "terraform-terragrunt"

    def test_explicit_project_type_overrides_detection(self):
        payload = self.builder.build_context(
            str(self.temp_dir), project_type="terraform"
        )
        assert payload.project_type == "terraform"

    def test_handles_missing_thothcf(self):
        """No .thothcf.toml → empty config, no crash."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            payload = self.builder.build_context(str(empty_dir))
            assert payload.project_config == ""
            # Should still work, just with less context
            compiled = payload.compile()
            assert "# Organizational Context" in compiled
        finally:
            shutil.rmtree(empty_dir)

    def test_handles_missing_steering(self):
        """No .kiro/steering/ → empty rules, no crash."""
        shutil.rmtree(self.temp_dir / ".kiro")
        payload = self.builder.build_context(str(self.temp_dir))
        assert payload.iac_rules == ""
        assert payload.project_overview == ""

    def test_handles_empty_project(self):
        """Completely empty directory → returns minimal payload."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            payload = self.builder.build_context(str(empty_dir))
            compiled = payload.compile()
            assert "# Organizational Context" in compiled
            assert payload.project_type == "terraform"  # default
        finally:
            shutil.rmtree(empty_dir)

    def test_claude_rules_loaded(self):
        """Test .claude/rules/*.md loading as alternative to .kiro."""
        # Remove .kiro
        shutil.rmtree(self.temp_dir / ".kiro")

        # Create .claude/rules/
        rules_dir = self.temp_dir / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "iac-rules.md").write_text(
            "---\npaths:\n  - stacks/**\n---\n\n"
            "# Rules\n- Use terraform-aws-modules\n- Pin versions\n"
        )

        payload = self.builder.build_context(str(self.temp_dir))
        assert "terraform-aws-modules" in payload.iac_rules
        # Frontmatter should be stripped
        assert "paths:" not in payload.iac_rules

    def test_claude_md_loaded_as_overview(self):
        """Test CLAUDE.md at root loaded as project overview."""
        # Remove .kiro
        shutil.rmtree(self.temp_dir / ".kiro")

        (self.temp_dir / "CLAUDE.md").write_text(
            "# My Infrastructure\nProduction AWS platform.\n"
        )

        payload = self.builder.build_context(str(self.temp_dir))
        assert "Production AWS platform" in payload.project_overview

    def test_patterns_exclude_cache_dirs(self):
        """Files in .terragrunt-cache should not be loaded as patterns."""
        cache_dir = self.temp_dir / "stacks" / ".terragrunt-cache" / "abc"
        cache_dir.mkdir(parents=True)
        (cache_dir / "main.tf").write_text("# cached file - should be excluded")

        payload = self.builder.build_context(str(self.temp_dir))
        assert "cached file" not in payload.existing_patterns

    def test_token_estimate_reasonable(self):
        """Total context should stay within budget."""
        payload = self.builder.build_context(str(self.temp_dir))
        compiled = payload.compile()
        # Should be under 6000 tokens (~24000 chars) for a typical project
        assert len(compiled) < 30000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
