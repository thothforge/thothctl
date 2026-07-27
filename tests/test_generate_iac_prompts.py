"""Unit tests for Intent-to-IaC prompts."""

import pytest

from thothctl.services.generate.intent.models import GeneratedFile
from thothctl.services.generate.intent.prompts import (
    CDK_HINTS,
    CLOUDFORMATION_HINTS,
    TERRAFORM_HINTS,
    TERRAGRUNT_STACK_HINTS,
    _get_project_hints,
    build_fix_prompt,
    build_generation_prompt,
    format_previous_files,
)


class TestBuildGenerationPrompt:
    """Test generation prompt assembly."""

    def test_includes_project_type(self):
        prompt = build_generation_prompt("terraform-terragrunt", "some context")
        assert "terraform-terragrunt" in prompt

    def test_includes_context(self):
        prompt = build_generation_prompt(
            "terraform", "My org requires encryption at rest"
        )
        assert "My org requires encryption at rest" in prompt

    def test_includes_terragrunt_hints(self):
        prompt = build_generation_prompt("terraform-terragrunt", "context")
        assert "find_in_parent_folders" in prompt
        assert "mock_outputs" in prompt

    def test_includes_terraform_hints(self):
        prompt = build_generation_prompt("terraform", "context")
        assert "provider block" in prompt
        assert "backend configuration" in prompt

    def test_includes_cloudformation_hints(self):
        prompt = build_generation_prompt("cloudformation", "context")
        assert "AWSTemplateFormatVersion" in prompt
        assert "!Ref" in prompt

    def test_includes_cdk_hints(self):
        prompt = build_generation_prompt("cdkv2", "context")
        assert "L2 constructs" in prompt
        assert "CfnOutput" in prompt

    def test_json_output_format_specified(self):
        prompt = build_generation_prompt("terraform", "context")
        assert '"files"' in prompt
        assert '"path"' in prompt
        assert '"content"' in prompt
        assert '"explanation"' in prompt

    def test_no_markdown_fences_instruction(self):
        prompt = build_generation_prompt("terraform", "context")
        assert "no markdown fences" in prompt

    def test_unknown_project_type_defaults_to_terraform_hints(self):
        prompt = build_generation_prompt("unknown-type", "context")
        assert "provider block" in prompt  # Falls back to terraform hints


class TestBuildFixPrompt:
    """Test self-correction prompt assembly."""

    def test_includes_violations(self):
        prompt = build_fix_prompt(
            context="rules here",
            violations="- [HIGH] CKV_AWS_130: Enable VPC flow logs",
            previous_files="### main.tf\n```\nresource...\n```",
        )
        assert "CKV_AWS_130" in prompt
        assert "VPC flow logs" in prompt

    def test_includes_context(self):
        prompt = build_fix_prompt(
            context="Use terraform-aws-modules",
            violations="violation list",
            previous_files="files",
        )
        assert "terraform-aws-modules" in prompt

    def test_includes_previous_files(self):
        prompt = build_fix_prompt(
            context="ctx",
            violations="viols",
            previous_files='### main.tf\n```\nresource "aws_vpc" {}\n```',
        )
        assert "aws_vpc" in prompt

    def test_contains_common_fix_hints(self):
        prompt = build_fix_prompt("ctx", "viols", "files")
        assert "CKV_AWS_130" in prompt
        assert "CKV_AWS_145" in prompt
        assert "CKV_AWS_23" in prompt

    def test_instructs_not_to_remove_functionality(self):
        prompt = build_fix_prompt("ctx", "viols", "files")
        assert "Do NOT remove functionality" in prompt


class TestFormatPreviousFiles:
    """Test file formatting for fix prompt."""

    def test_formats_single_file(self):
        files = [GeneratedFile("main.tf", 'resource "aws_vpc" "main" {}')]
        result = format_previous_files(files)
        assert "### main.tf" in result
        assert "aws_vpc" in result

    def test_formats_multiple_files(self):
        files = [
            GeneratedFile("main.tf", "resource {}"),
            GeneratedFile("variables.tf", 'variable "name" {}'),
        ]
        result = format_previous_files(files)
        assert "### main.tf" in result
        assert "### variables.tf" in result

    def test_truncates_large_files(self):
        large_content = "x" * 3000
        files = [GeneratedFile("big.tf", large_content)]
        result = format_previous_files(files)
        assert "truncated" in result
        assert len(result) < 3000


class TestProjectHints:
    """Test project-type hint selection."""

    def test_terragrunt_hints(self):
        hints = _get_project_hints("terraform-terragrunt")
        assert hints == TERRAGRUNT_STACK_HINTS

    def test_terragrunt_standalone(self):
        hints = _get_project_hints("terragrunt")
        assert hints == TERRAGRUNT_STACK_HINTS

    def test_terraform_hints(self):
        hints = _get_project_hints("terraform")
        assert hints == TERRAFORM_HINTS

    def test_cloudformation_hints(self):
        hints = _get_project_hints("cloudformation")
        assert hints == CLOUDFORMATION_HINTS

    def test_cdk_hints(self):
        hints = _get_project_hints("cdkv2")
        assert hints == CDK_HINTS.format(language="typescript")

    def test_unknown_defaults_to_terraform(self):
        hints = _get_project_hints("pulumi")
        assert hints == TERRAFORM_HINTS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
