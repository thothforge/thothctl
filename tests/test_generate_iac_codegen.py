"""Unit tests for Intent-to-IaC code generator."""

import json
from unittest.mock import MagicMock

import pytest
from thothctl.services.generate.intent.code_generator import CodeGenerator
from thothctl.services.generate.intent.models import (
    GeneratedFile,
    GenerationOutput,
    ValidationResult,
    Violation,
)


@pytest.fixture
def mock_provider():
    """Mock AI provider that returns controllable responses."""
    provider = MagicMock()
    provider.name = "ollama"
    provider.model = "llama3"
    return provider


@pytest.fixture
def generator(mock_provider):
    """CodeGenerator with mocked provider (skips real initialization)."""
    gen = CodeGenerator.__new__(CodeGenerator)
    gen.provider_name = "ollama"
    gen.model_name = "llama3"
    gen._provider = mock_provider
    return gen


class TestGenerate:
    """Test the generate method."""

    def test_successful_generation(self, generator, mock_provider):
        """AI returns valid JSON with files."""
        mock_provider.analyze.return_value = {
            "files": [
                {"path": "main.tf", "content": 'resource "aws_vpc" "main" {}'},
                {"path": "variables.tf", "content": 'variable "cidr" {}'},
            ],
            "explanation": "Created VPC",
            "modules_used": ["terraform-aws-modules/vpc/aws@5.17.0"],
            "estimated_resources": ["aws_vpc", "aws_subnet"],
        }

        result = generator.generate("Create a VPC", "org context", "terraform")

        assert result.file_count == 2
        assert result.files[0].path == "main.tf"
        assert "aws_vpc" in result.files[0].content
        assert result.explanation == "Created VPC"
        assert "terraform-aws-modules/vpc/aws@5.17.0" in result.modules_used

    def test_empty_response(self, generator, mock_provider):
        """AI returns empty dict."""
        mock_provider.analyze.return_value = {}

        result = generator.generate("Create a VPC", "ctx", "terraform")

        assert result.file_count == 0
        assert result.raw_response is not None

    def test_provider_exception(self, generator, mock_provider):
        """AI provider throws exception."""
        mock_provider.analyze.side_effect = Exception("Connection timeout")

        result = generator.generate("Create a VPC", "ctx", "terraform")

        assert result.file_count == 0
        assert "Connection timeout" in result.explanation

    def test_response_with_nested_content(self, generator, mock_provider):
        """AI response has JSON string in 'content' key."""
        inner_json = json.dumps(
            {
                "files": [{"path": "main.tf", "content": "resource {}"}],
                "explanation": "done",
                "modules_used": [],
                "estimated_resources": [],
            }
        )
        mock_provider.analyze.return_value = {"content": inner_json}

        result = generator.generate("intent", "ctx", "terraform")

        assert result.file_count == 1
        assert result.files[0].path == "main.tf"


class TestFix:
    """Test the fix (self-correction) method."""

    def test_successful_fix(self, generator, mock_provider):
        """AI fixes violations and returns corrected code."""
        mock_provider.analyze.return_value = {
            "files": [
                {
                    "path": "main.tf",
                    "content": 'resource "aws_vpc" "main" {\n  enable_dns_support = true\n}',
                },
            ],
            "explanation": "Added flow logs",
            "modules_used": [],
            "estimated_resources": ["aws_vpc", "aws_flow_log"],
        }

        previous = GenerationOutput(
            files=[GeneratedFile("main.tf", 'resource "aws_vpc" "main" {}')],
        )
        validation = ValidationResult(
            passed=False,
            violations=[
                Violation(
                    "CKV_AWS_130", "HIGH", "aws_vpc.main", "Enable VPC flow logs"
                ),
            ],
        )

        result = generator.fix(previous, validation, "org context")

        assert result.file_count == 1
        assert "enable_dns_support" in result.files[0].content
        assert "Added flow logs" in result.explanation

    def test_fix_failure_returns_previous(self, generator, mock_provider):
        """If AI fix fails, return original output."""
        mock_provider.analyze.side_effect = Exception("API error")

        previous = GenerationOutput(
            files=[GeneratedFile("main.tf", "original code")],
        )
        validation = ValidationResult(
            passed=False,
            violations=[Violation("CKV1", "HIGH", "r1", "msg")],
        )

        result = generator.fix(previous, validation, "ctx")

        # Should return previous output, not crash
        assert result.file_count == 1
        assert result.files[0].content == "original code"


class TestParseResponse:
    """Test JSON response parsing with various formats."""

    def test_direct_dict_with_files(self, generator):
        """Standard response format."""
        raw = {
            "files": [{"path": "a.tf", "content": "resource {}"}],
            "explanation": "test",
            "modules_used": [],
            "estimated_resources": [],
        }
        result = generator._parse_response(raw)
        assert result.file_count == 1

    def test_json_string_in_content_key(self, generator):
        """Response wrapped in a 'content' key."""
        inner = json.dumps(
            {
                "files": [{"path": "b.tf", "content": "var {}"}],
                "explanation": "",
                "modules_used": [],
                "estimated_resources": [],
            }
        )
        raw = {"content": inner}
        result = generator._parse_response(raw)
        assert result.file_count == 1
        assert result.files[0].path == "b.tf"

    def test_json_string_in_response_key(self, generator):
        """Response wrapped in a 'response' key."""
        inner = json.dumps(
            {
                "files": [{"path": "c.tf", "content": "output {}"}],
                "explanation": "",
                "modules_used": [],
                "estimated_resources": [],
            }
        )
        raw = {"response": inner}
        result = generator._parse_response(raw)
        assert result.file_count == 1

    def test_invalid_files_structure(self, generator):
        """Files key present but items lack path/content."""
        raw = {"files": [{"wrong_key": "value"}], "explanation": ""}
        result = generator._parse_response(raw)
        assert result.file_count == 0

    def test_completely_unparseable(self, generator):
        """Totally invalid response."""
        raw = {"random": "data", "no_files_here": True}
        result = generator._parse_response(raw)
        assert result.file_count == 0
        assert result.raw_response is not None


class TestExtractJson:
    """Test JSON extraction from various text formats."""

    def test_clean_json(self, generator):
        """Plain JSON string."""
        text = '{"files": [{"path": "x.tf", "content": "y"}]}'
        result = generator._extract_json(text)
        assert result is not None
        assert "files" in result

    def test_json_in_markdown_fences(self, generator):
        """JSON wrapped in ```json ... ``` fences."""
        text = 'Here is the code:\n```json\n{"files": [{"path": "a.tf", "content": "b"}]}\n```\nDone.'
        result = generator._extract_json(text)
        assert result is not None
        assert result["files"][0]["path"] == "a.tf"

    def test_json_in_plain_fences(self, generator):
        """JSON wrapped in ``` ... ``` (no language tag)."""
        text = '```\n{"files": [{"path": "c.tf", "content": "d"}]}\n```'
        result = generator._extract_json(text)
        assert result is not None

    def test_json_with_surrounding_text(self, generator):
        """JSON mixed with prose (brace matching)."""
        text = 'Sure! Here is your infrastructure:\n{"files": [{"path": "main.tf", "content": "resource {}"}], "explanation": "done", "modules_used": [], "estimated_resources": []}\nLet me know if you need anything else.'
        result = generator._extract_json(text)
        assert result is not None
        assert result["files"][0]["path"] == "main.tf"

    def test_empty_string(self, generator):
        """Empty input."""
        assert generator._extract_json("") is None
        assert generator._extract_json(None) is None

    def test_no_json_at_all(self, generator):
        """Text with no JSON."""
        assert generator._extract_json("Just some plain text without any JSON") is None

    def test_nested_braces_in_content(self, generator):
        """JSON where file content contains braces (HCL code)."""
        data = {
            "files": [
                {
                    "path": "main.tf",
                    "content": 'resource "aws_vpc" "main" {\n  cidr_block = "10.0.0.0/16"\n}',
                }
            ],
            "explanation": "VPC",
            "modules_used": [],
            "estimated_resources": [],
        }
        text = f"```json\n{json.dumps(data)}\n```"
        result = generator._extract_json(text)
        assert result is not None
        assert "aws_vpc" in result["files"][0]["content"]

    def test_json_with_escaped_quotes(self, generator):
        """JSON containing escaped quotes in content."""
        data = {
            "files": [{"path": "a.tf", "content": 'name = "my-vpc"'}],
            "explanation": "",
            "modules_used": [],
            "estimated_resources": [],
        }
        text = json.dumps(data)
        result = generator._extract_json(text)
        assert result is not None
        assert "my-vpc" in result["files"][0]["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
