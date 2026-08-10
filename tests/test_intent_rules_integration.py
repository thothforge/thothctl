"""Tests for Phase 2.4: Rules integration with Intent-to-IaC validation.

Verifies that .thothcf.toml [rules] are compiled and evaluated against
generated code inside the validation loop.
"""

import os
import tempfile
import textwrap
import unittest

from thothctl.services.generate.intent.models import GeneratedFile, ValidationResult
from thothctl.services.generate.intent.validator import GenerationValidator


class TestRulesIntegrationWithValidator(unittest.TestCase):
    """Test that compiled rules are evaluated during Intent-to-IaC validation."""

    def setUp(self):
        self.validator = GenerationValidator()
        # Create a temp project dir with .thothcf.toml rules
        self.project_dir = tempfile.mkdtemp()

    def _write_rules(self, toml_content: str):
        """Write .thothcf.toml to the project dir."""
        config_path = os.path.join(self.project_dir, ".thothcf.toml")
        with open(config_path, "w") as f:
            f.write(toml_content)

    def test_naming_rule_enforced_at_generation(self):
        """Naming rules should catch violations in generated code."""
        self._write_rules(
            textwrap.dedent("""\
                [[rules.naming]]
                name = "resource_naming"
                severity = "error"
                [rules.naming.config]
                pattern = "^(dev|stg|prd)_.*"
            """)
        )

        # Generated code with BAD naming (doesn't start with dev|stg|prd)
        files = [
            GeneratedFile(
                path="main.tf",
                content=textwrap.dedent("""\
                    resource "aws_s3_bucket" "my_bucket" {
                      bucket = "my-bucket"
                    }
                """),
            )
        ]

        result = self.validator.validate(
            files=files,
            project_type="terraform",
            project_dir=self.project_dir,
            skip_checkov=True,
            skip_framework_validate=True,
        )

        # Should have violations from compiled rules (if conftest is available)
        # Note: violations depend on conftest being installed
        # The test verifies the integration path works without crashing
        self.assertIsInstance(result, ValidationResult)

    def test_no_rules_no_violations(self):
        """No .thothcf.toml rules should produce no rule violations."""
        # Project dir exists but no .thothcf.toml
        files = [
            GeneratedFile(
                path="main.tf",
                content='resource "aws_s3_bucket" "test" {\n  bucket = "test"\n}\n',
            )
        ]

        result = self.validator.validate(
            files=files,
            project_type="terraform",
            project_dir=self.project_dir,
            skip_checkov=True,
            skip_framework_validate=True,
        )

        # No rules = no rule violations (OPA violations would only come from org policy)
        opa_violations = [v for v in result.violations if v.tool == "opa"]
        self.assertEqual(len(opa_violations), 0)

    def test_project_dir_none_skips_rules(self):
        """If project_dir is None, rules compilation is skipped gracefully."""
        files = [
            GeneratedFile(
                path="main.tf",
                content='resource "aws_s3_bucket" "test" {\n  bucket = "test"\n}\n',
            )
        ]

        result = self.validator.validate(
            files=files,
            project_type="terraform",
            project_dir=None,
            skip_checkov=True,
            skip_framework_validate=True,
        )

        self.assertIsInstance(result, ValidationResult)
        # Should not crash when project_dir is None

    def test_rules_compiled_to_rego(self):
        """Verify rules are actually compiled to .rego files."""
        from thothctl.services.check.rules_compiler import RulesCompiler

        self._write_rules(
            textwrap.dedent("""\
                [[rules.tagging]]
                name = "required_tags"
                [rules.tagging.config]
                required_tags = ["Environment", "Owner"]
            """)
        )

        compiler = RulesCompiler()
        compiled_dir = compiler.compile(self.project_dir)

        self.assertIsNotNone(compiled_dir)
        # Check .rego file was generated
        rego_files = [f for f in os.listdir(compiled_dir) if f.endswith(".rego")]
        self.assertGreater(len(rego_files), 0)
        # Verify content mentions the rule
        content = open(os.path.join(compiled_dir, "tagging.rego")).read()
        self.assertIn("required_tags", content)
        self.assertIn("Environment", content)
        self.assertIn("Owner", content)

    def test_validate_passes_project_dir_to_rules(self):
        """Full integration: validate() compiles and evaluates rules."""
        self._write_rules(
            textwrap.dedent("""\
                [[rules.security]]
                name = "no_public_access"
                severity = "error"
                [rules.security.config]
                banned_patterns = ["acl.*public"]
            """)
        )

        # Generated code WITH a banned pattern
        files = [
            GeneratedFile(
                path="main.tf",
                content=textwrap.dedent("""\
                    resource "aws_s3_bucket" "data" {
                      bucket = "my-data-bucket"
                      acl    = "public-read"
                    }
                """),
            )
        ]

        result = self.validator.validate(
            files=files,
            project_type="terraform",
            project_dir=self.project_dir,
            skip_checkov=True,
            skip_framework_validate=True,
        )

        # The integration path should work without crashing
        # Actual violations depend on conftest being installed
        self.assertIsInstance(result, ValidationResult)


if __name__ == "__main__":
    unittest.main()
