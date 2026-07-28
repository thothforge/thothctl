"""Unit tests for Intent-to-IaC pipeline orchestrator."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from thothctl.services.generate.intent.intent_service import IntentToIaCService
from thothctl.services.generate.intent.models import (
    ContextPayload,
    GeneratedFile,
    GenerationOutput,
    ValidationResult,
    Violation,
)


@pytest.fixture
def temp_project():
    """Create a temp project directory with minimal .thothcf.toml."""
    temp_dir = tempfile.mkdtemp()
    Path(temp_dir, ".thothcf.toml").write_text(
        '[thothcf]\nproject_type = "terraform"\n'
    )
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_service():
    """IntentToIaCService with mocked internal components."""
    with patch(
        "thothctl.services.generate.intent.intent_service.CodeGenerator"
    ) as MockCodeGen:
        mock_gen = MagicMock()
        MockCodeGen.return_value = mock_gen

        service = IntentToIaCService.__new__(IntentToIaCService)
        service.provider = "ollama"
        service.model = "llama3"
        service.context_builder = MagicMock()
        service.code_generator = mock_gen
        service.validator = MagicMock()

        # Default: context builder returns valid payload
        mock_payload = ContextPayload(project_type="terraform", project_config="test")
        mock_payload.total_tokens_estimate = 500
        service.context_builder.build_context.return_value = mock_payload

        yield service


class TestGeneratePipeline:
    """Test the full generate pipeline."""

    def test_successful_generation_no_violations(self, mock_service, temp_project):
        """Happy path: generate → validate passes → return files."""
        mock_service.code_generator.generate.return_value = GenerationOutput(
            files=[
                GeneratedFile(
                    "main.tf",
                    'resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }',
                ),
                GeneratedFile(
                    "variables.tf", 'variable "cidr" { default = "10.0.0.0/16" }'
                ),
            ],
            explanation="Created VPC",
            modules_used=["terraform-aws-modules/vpc/aws@5.17.0"],
            estimated_resources=["aws_vpc"],
        )
        mock_service.validator.validate.return_value = ValidationResult(passed=True)

        result = mock_service.generate(
            intent="Create a VPC with CIDR 10.0.0.0/16",
            directory=temp_project,
        )

        assert result.success is True
        assert len(result.files) == 2
        assert result.explanation == "Created VPC"
        assert result.iterations == 1
        assert result.validation.passed is True

    def test_generation_with_self_correction(self, mock_service, temp_project):
        """Generate → fails validation → fix → passes."""
        # First generation
        original = GenerationOutput(
            files=[GeneratedFile("main.tf", 'resource "aws_vpc" "main" {}')],
            explanation="VPC without flow logs",
        )
        # Fixed generation
        fixed = GenerationOutput(
            files=[
                GeneratedFile(
                    "main.tf",
                    'resource "aws_vpc" "main" {}\nresource "aws_flow_log" "main" {}',
                )
            ],
            explanation="Added flow logs",
        )

        mock_service.code_generator.generate.return_value = original
        mock_service.code_generator.fix.return_value = fixed

        # First validate fails, second passes
        mock_service.validator.validate.side_effect = [
            ValidationResult(
                passed=False,
                violations=[
                    Violation(
                        "CKV_AWS_130", "HIGH", "aws_vpc.main", "Enable flow logs"
                    ),
                ],
            ),
            ValidationResult(passed=True),
        ]

        result = mock_service.generate(
            intent="Create a VPC",
            directory=temp_project,
            self_correct=True,
            max_iterations=3,
        )

        assert result.success is True
        assert result.iterations == 2
        assert result.validation.passed is True
        assert "flow_log" in result.files[0].content
        mock_service.code_generator.fix.assert_called_once()

    def test_generation_max_iterations_reached(self, mock_service, temp_project):
        """Generate → fails all 3 correction attempts → returns with violations."""
        mock_service.code_generator.generate.return_value = GenerationOutput(
            files=[GeneratedFile("main.tf", "bad code")],
        )
        mock_service.code_generator.fix.return_value = GenerationOutput(
            files=[GeneratedFile("main.tf", "still bad code")],
        )

        # Always fails
        mock_service.validator.validate.return_value = ValidationResult(
            passed=False,
            violations=[Violation("CKV1", "HIGH", "r1", "keeps failing")],
        )

        result = mock_service.generate(
            intent="Create something",
            directory=temp_project,
            self_correct=True,
            max_iterations=3,
        )

        assert result.success is True  # Files were generated (just didn't pass)
        assert result.iterations == 3
        assert result.validation.passed is False

    def test_skip_validation(self, mock_service, temp_project):
        """--skip-validation skips Checkov/OPA entirely."""
        mock_service.code_generator.generate.return_value = GenerationOutput(
            files=[GeneratedFile("main.tf", "resource {}")],
        )

        result = mock_service.generate(
            intent="Create something",
            directory=temp_project,
            skip_validation=True,
        )

        assert result.success is True
        assert result.iterations == 0
        mock_service.validator.validate.assert_not_called()

    def test_no_self_correction(self, mock_service, temp_project):
        """self_correct=False runs validation once, doesn't fix."""
        mock_service.code_generator.generate.return_value = GenerationOutput(
            files=[GeneratedFile("main.tf", "resource {}")],
        )
        mock_service.validator.validate.return_value = ValidationResult(
            passed=False,
            violations=[Violation("CKV1", "MEDIUM", "r1", "issue")],
        )

        result = mock_service.generate(
            intent="Create something",
            directory=temp_project,
            self_correct=False,
        )

        assert result.iterations == 1
        assert result.validation.passed is False
        mock_service.code_generator.fix.assert_not_called()

    def test_ai_returns_empty_files(self, mock_service, temp_project):
        """AI returns no files → error result."""
        mock_service.code_generator.generate.return_value = GenerationOutput(
            files=[],
            raw_response="AI returned garbage",
        )

        result = mock_service.generate(
            intent="Create something",
            directory=temp_project,
        )

        assert result.success is False
        assert "no files" in result.error.lower()

    def test_apply_writes_files(self, mock_service):
        """--apply writes generated files to disk."""
        output_dir = tempfile.mkdtemp()
        try:
            mock_service.code_generator.generate.return_value = GenerationOutput(
                files=[
                    GeneratedFile("stacks/vpc/main.tf", "resource {}"),
                    GeneratedFile("stacks/vpc/variables.tf", "variable {}"),
                ],
            )
            mock_service.validator.validate.return_value = ValidationResult(passed=True)

            # Need a context builder that works
            mock_payload = ContextPayload(project_type="terraform")
            mock_service.context_builder.build_context.return_value = mock_payload

            result = mock_service.generate(
                intent="Create VPC",
                directory=output_dir,
                output_dir=output_dir,
                apply=True,
            )

            assert result.success is True
            assert (Path(output_dir) / "stacks" / "vpc" / "main.tf").exists()
            assert (Path(output_dir) / "stacks" / "vpc" / "variables.tf").exists()
            assert (
                Path(output_dir) / "stacks" / "vpc" / "main.tf"
            ).read_text() == "resource {}"
        finally:
            shutil.rmtree(output_dir)

    def test_dry_run_does_not_write(self, mock_service):
        """Without --apply, no files are written."""
        output_dir = tempfile.mkdtemp()
        try:
            mock_service.code_generator.generate.return_value = GenerationOutput(
                files=[GeneratedFile("main.tf", "resource {}")],
            )
            mock_service.validator.validate.return_value = ValidationResult(passed=True)

            mock_payload = ContextPayload(project_type="terraform")
            mock_service.context_builder.build_context.return_value = mock_payload

            result = mock_service.generate(
                intent="Create VPC",
                directory=output_dir,
                apply=False,  # dry-run
            )

            assert result.success is True
            # No files written
            assert not (Path(output_dir) / "main.tf").exists()
        finally:
            shutil.rmtree(output_dir)


class TestResolveOrgPolicyDir:
    """Test org policy directory resolution."""

    def setup_method(self):
        self.service = IntentToIaCService.__new__(IntentToIaCService)

    def test_finds_local_policies_dir(self):
        """Finds policies/ with .rego files."""
        temp_dir = tempfile.mkdtemp()
        try:
            policies = Path(temp_dir) / "policies"
            policies.mkdir()
            (policies / "tags.rego").write_text("package tags\n")

            result = self.service._resolve_org_policy_dir(temp_dir)
            assert result == str(policies)
        finally:
            shutil.rmtree(temp_dir)

    def test_finds_local_policy_dir(self):
        """Finds policy/ with .rego files."""
        temp_dir = tempfile.mkdtemp()
        try:
            policy = Path(temp_dir) / "policy"
            policy.mkdir()
            (policy / "security.rego").write_text("package security\n")

            result = self.service._resolve_org_policy_dir(temp_dir)
            assert result == str(policy)
        finally:
            shutil.rmtree(temp_dir)

    def test_returns_none_when_no_policies(self):
        """No policy dirs → None."""
        temp_dir = tempfile.mkdtemp()
        fake_home = tempfile.mkdtemp()
        try:
            with patch("pathlib.Path.home", return_value=Path(fake_home)):
                result = self.service._resolve_org_policy_dir(temp_dir)
            assert result is None
        finally:
            shutil.rmtree(temp_dir)
            shutil.rmtree(fake_home)

    def test_ignores_empty_policy_dir(self):
        """Policy dir without .rego files → None."""
        temp_dir = tempfile.mkdtemp()
        fake_home = tempfile.mkdtemp()
        try:
            policies = Path(temp_dir) / "policies"
            policies.mkdir()
            (policies / "readme.md").write_text("# Policies\n")

            with patch("pathlib.Path.home", return_value=Path(fake_home)):
                result = self.service._resolve_org_policy_dir(temp_dir)
            assert result is None
        finally:
            shutil.rmtree(temp_dir)
            shutil.rmtree(fake_home)

    @patch.dict("os.environ", {"THOTH_ORG_POLICY": "/tmp/fake_policies"})
    def test_env_var_used_if_local_path(self):
        """THOTH_ORG_POLICY env var used if it's a local dir with .rego files."""
        temp_dir = tempfile.mkdtemp()
        policy_dir = tempfile.mkdtemp()
        try:
            (Path(policy_dir) / "rule.rego").write_text("package rule\n")

            with patch.dict("os.environ", {"THOTH_ORG_POLICY": policy_dir}):
                result = self.service._resolve_org_policy_dir(temp_dir)
            assert result == policy_dir
        finally:
            shutil.rmtree(temp_dir)
            shutil.rmtree(policy_dir)

    @patch.dict(
        "os.environ", {"THOTH_ORG_POLICY": "git::https://github.com/org/policies.git"}
    )
    def test_env_var_ignored_if_git_url(self):
        """Git URLs in THOTH_ORG_POLICY are skipped (need clone first)."""
        temp_dir = tempfile.mkdtemp()
        fake_home = tempfile.mkdtemp()
        try:
            with patch("pathlib.Path.home", return_value=Path(fake_home)):
                result = self.service._resolve_org_policy_dir(temp_dir)
            assert result is None
        finally:
            shutil.rmtree(temp_dir)
            shutil.rmtree(fake_home)


class TestWriteFiles:
    """Test file writing."""

    def setup_method(self):
        self.service = IntentToIaCService.__new__(IntentToIaCService)

    def test_writes_flat_files(self):
        """Simple files at root level."""
        temp_dir = tempfile.mkdtemp()
        try:
            files = [
                GeneratedFile("main.tf", "resource {}"),
                GeneratedFile("outputs.tf", "output {}"),
            ]
            self.service._write_files(files, temp_dir)

            assert (Path(temp_dir) / "main.tf").read_text() == "resource {}"
            assert (Path(temp_dir) / "outputs.tf").read_text() == "output {}"
        finally:
            shutil.rmtree(temp_dir)

    def test_writes_nested_files(self):
        """Files with directory structure."""
        temp_dir = tempfile.mkdtemp()
        try:
            files = [
                GeneratedFile("stacks/foundation/vpc/main.tf", "vpc resource"),
                GeneratedFile("stacks/foundation/vpc/terragrunt.hcl", "include {}"),
            ]
            self.service._write_files(files, temp_dir)

            vpc_dir = Path(temp_dir) / "stacks" / "foundation" / "vpc"
            assert (vpc_dir / "main.tf").read_text() == "vpc resource"
            assert (vpc_dir / "terragrunt.hcl").read_text() == "include {}"
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
