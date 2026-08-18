"""Unit tests for KiroProvider — Kiro CLI headless mode as AI provider."""

import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from thothctl.services.ai_review.config.ai_settings import ProviderConfig
from thothctl.services.ai_review.providers.kiro_provider import (
    DEFAULT_AGENT,
    DEFAULT_TIMEOUT,
    RECURSION_GUARD_ENV,
    KiroProvider,
)


# --- Fixtures ---


@pytest.fixture
def config():
    """Default provider config for tests."""
    return ProviderConfig(model="kiro_default")


@pytest.fixture
def provider(monkeypatch):
    """Create a KiroProvider with mocked binary detection."""
    monkeypatch.delenv(RECURSION_GUARD_ENV, raising=False)
    with patch("shutil.which", return_value="/usr/bin/kiro-cli"):
        return KiroProvider(ProviderConfig(model="kiro_default"))


@pytest.fixture
def custom_agent_provider(monkeypatch):
    """Create a KiroProvider with a custom agent name."""
    monkeypatch.delenv(RECURSION_GUARD_ENV, raising=False)
    with patch("shutil.which", return_value="/usr/bin/kiro-cli"):
        return KiroProvider(ProviderConfig(model="iac-expert"))


# --- Initialization Tests ---


class TestInit:
    def test_init_with_default_agent(self, monkeypatch):
        monkeypatch.delenv(RECURSION_GUARD_ENV, raising=False)
        with patch("shutil.which", return_value="/usr/local/bin/kiro-cli"):
            p = KiroProvider(ProviderConfig())
            assert p.agent == DEFAULT_AGENT
            assert p.kiro_binary == "/usr/local/bin/kiro-cli"
            assert p.timeout == DEFAULT_TIMEOUT

    def test_init_with_custom_agent(self, monkeypatch):
        monkeypatch.delenv(RECURSION_GUARD_ENV, raising=False)
        with patch("shutil.which", return_value="/usr/bin/kiro-cli"):
            p = KiroProvider(ProviderConfig(model="terraform-expert"))
            assert p.agent == "terraform-expert"

    def test_init_with_explicit_binary_path(self, monkeypatch):
        monkeypatch.delenv(RECURSION_GUARD_ENV, raising=False)
        with patch("shutil.which", return_value=None):
            # endpoint is used as binary path override
            p = KiroProvider(
                ProviderConfig(endpoint="/opt/kiro/bin/kiro-cli")
            )
            assert p.kiro_binary == "/opt/kiro/bin/kiro-cli"

    def test_init_raises_when_binary_not_found(self, monkeypatch):
        monkeypatch.delenv(RECURSION_GUARD_ENV, raising=False)
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="kiro-cli not found"):
                KiroProvider(ProviderConfig())

    def test_init_raises_on_recursive_invocation(self, monkeypatch):
        monkeypatch.setenv(RECURSION_GUARD_ENV, "1")
        with patch("shutil.which", return_value="/usr/bin/kiro-cli"):
            with pytest.raises(RuntimeError, match="Recursive invocation detected"):
                KiroProvider(ProviderConfig())

    def test_name_property(self, provider):
        assert provider.name == "kiro"


# --- is_available Tests ---


class TestIsAvailable:
    def test_available_when_binary_exists(self):
        with patch("shutil.which", return_value="/usr/bin/kiro-cli"):
            assert KiroProvider.is_available() is True

    def test_not_available_when_binary_missing(self):
        with patch("shutil.which", return_value=None):
            assert KiroProvider.is_available() is False


# --- analyze() Tests ---


class TestAnalyze:
    def test_successful_json_response(self, provider):
        """Test that valid JSON output from Kiro is parsed correctly."""
        response_json = json.dumps({
            "files": [{"path": "main.tf", "content": "resource \"aws_vpc\" {}"}],
            "explanation": "Created VPC",
        })
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=response_json, stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            result = provider.analyze("You are an IaC generator", "Create a VPC")

        assert result["files"] == [
            {"path": "main.tf", "content": 'resource "aws_vpc" {}'}
        ]
        assert result["explanation"] == "Created VPC"
        assert "_usage" in result

    def test_json_in_markdown_block(self, provider):
        """Test extraction of JSON from markdown code blocks."""
        output = (
            "I'll generate the Terraform code for you.\n\n"
            "```json\n"
            '{"files": [{"path": "vpc.tf", "content": "resource {}"}]}\n'
            "```\n\n"
            "This creates a basic VPC."
        )
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=output, stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            result = provider.analyze("system", "user")

        assert "files" in result
        assert result["files"][0]["path"] == "vpc.tf"

    def test_json_embedded_in_mixed_output(self, provider):
        """Test extraction when JSON is embedded in tool-use output."""
        output = (
            "Reading project structure...\n"
            "Found .thothcf.toml with naming rules.\n"
            "Searching Terraform documentation...\n\n"
            '{"files": [{"path": "main.tf", "content": "resource \\"aws_vpc\\" \\"main\\" {}"}], '
            '"explanation": "Generated", "risk_score": 10}\n'
        )
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=output, stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            result = provider.analyze("system", "user")

        assert result["files"][0]["path"] == "main.tf"
        assert result["risk_score"] == 10

    def test_empty_response_raises(self, provider):
        """Test that empty response raises ValueError."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(ValueError, match="Empty response"):
                provider.analyze("system", "user")

    def test_no_json_falls_back_to_wrapped_text(self, provider):
        """Test that non-JSON output is wrapped as a structured response."""
        output = "I created a VPC with 3 subnets and a NAT gateway in us-east-1."
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=output, stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            result = provider.analyze("system", "user")

        assert result.get("_parse_failed") is True
        assert result["_raw_text"] == output

    def test_timeout_raises_runtime_error(self, provider):
        """Test that timeout produces a clear error message."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 300)):
            with pytest.raises(RuntimeError, match="timed out"):
                provider.analyze("system", "user")

    def test_binary_not_found_raises(self, provider):
        """Test that missing binary at execution time raises."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(RuntimeError, match="binary not found"):
                provider.analyze("system", "user")

    def test_nonzero_exit_with_output_still_parses(self, provider):
        """Test that non-zero exit code with valid output still works."""
        response_json = json.dumps({"files": [], "explanation": "partial"})
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=response_json, stderr="warning: something"
        )
        with patch("subprocess.run", return_value=mock_result):
            result = provider.analyze("system", "user")

        assert result["explanation"] == "partial"

    def test_nonzero_exit_no_output_raises(self, provider):
        """Test that non-zero exit with no output raises RuntimeError."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error: model not available"
        )
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="Kiro CLI failed"):
                provider.analyze("system", "user")

    def test_usage_metadata_estimated(self, provider):
        """Test that _usage metadata is populated with estimates."""
        response_json = json.dumps({"result": "ok"})
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=response_json, stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            result = provider.analyze("short system", "short user")

        assert "_usage" in result
        assert "input_tokens" in result["_usage"]
        assert "output_tokens" in result["_usage"]
        assert result["_usage"]["input_tokens"] > 0
        assert result["_usage"]["output_tokens"] > 0


# --- Execution Details Tests ---


class TestExecutionDetails:
    def test_command_construction_default_agent(self, provider):
        """Test that the subprocess command is built correctly."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"ok": true}', stderr=""
        )
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            provider.analyze("system prompt", "user content")

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "/usr/bin/kiro-cli"
        assert "chat" in cmd
        assert "--no-interactive" in cmd
        assert "--trust-all-tools" in cmd
        # Default agent should NOT include --agent flag
        assert "--agent" not in cmd

    def test_command_construction_custom_agent(self, custom_agent_provider):
        """Test that custom agent name is passed via --agent flag."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"ok": true}', stderr=""
        )
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            custom_agent_provider.analyze("system", "user")

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "--agent" in cmd
        agent_idx = cmd.index("--agent")
        assert cmd[agent_idx + 1] == "iac-expert"

    def test_recursion_guard_env_set_in_child(self, provider):
        """Test that THOTHCTL_KIRO_PROVIDER_ACTIVE is set in child env."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"ok": true}', stderr=""
        )
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            provider.analyze("system", "user")

        call_kwargs = mock_run.call_args[1]
        child_env = call_kwargs["env"]
        assert child_env[RECURSION_GUARD_ENV] == "1"

    def test_timeout_passed_to_subprocess(self, provider):
        """Test that timeout is passed to subprocess.run."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"ok": true}', stderr=""
        )
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            provider.analyze("system", "user")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == DEFAULT_TIMEOUT

    def test_cwd_is_current_directory(self, provider):
        """Test that subprocess runs in current working directory."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"ok": true}', stderr=""
        )
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            provider.analyze("system", "user")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == os.getcwd()


# --- JSON Extraction Edge Cases ---


class TestJsonExtraction:
    def test_extract_last_json_when_multiple(self, provider):
        """When output has multiple JSON objects, extract the last complete one."""
        output = (
            '{"status": "searching"}\n'
            "Reading files...\n"
            '{"files": [{"path": "main.tf", "content": "final"}], "done": true}\n'
        )
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=output, stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            result = provider.analyze("system", "user")

        # Should get the last/most complete JSON
        assert "files" in result or "done" in result

    def test_extract_json_array_wrapped(self, provider):
        """Test that a JSON array output is wrapped in an object."""
        output = '[{"path": "main.tf", "content": "resource {}"}]'
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=output, stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            result = provider.analyze("system", "user")

        assert "files" in result
        assert result["_raw_array"] is True

    def test_extract_json_with_nested_braces(self, provider):
        """Test JSON extraction with nested objects."""
        output = json.dumps({
            "files": [
                {
                    "path": "main.tf",
                    "content": 'resource "aws_vpc" "main" {\n  cidr_block = "10.0.0.0/16"\n}',
                }
            ],
            "metadata": {"modules": ["vpc"], "provider": "aws"},
        })
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=output, stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            result = provider.analyze("system", "user")

        assert result["files"][0]["path"] == "main.tf"
        assert "cidr_block" in result["files"][0]["content"]
        assert result["metadata"]["provider"] == "aws"

    def test_handles_unicode_in_output(self, provider):
        """Test that unicode characters in output are handled."""
        output = json.dumps({
            "files": [{"path": "main.tf", "content": "# Módulo VPC — región us-east-1"}]
        })
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=output, stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            result = provider.analyze("system", "user")

        assert "Módulo" in result["files"][0]["content"]


# --- Prompt Building Tests ---


class TestPromptBuilding:
    def test_prompt_includes_json_instruction(self, provider):
        """Test that the built prompt includes JSON output instruction."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"ok": true}', stderr=""
        )
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            provider.analyze("Be an IaC generator", "Create a VPC")

        # The prompt (last positional arg) should contain both parts
        cmd = mock_run.call_args[0][0]
        prompt = cmd[-1]  # Last element is the prompt
        assert "Be an IaC generator" in prompt
        assert "Create a VPC" in prompt
        assert "CRITICAL" in prompt  # JSON instruction
        assert "valid JSON" in prompt
