"""Tests for the Rules Compiler (TOML → Rego).

Verifies that .thothcf.toml rules are correctly compiled into valid
Rego policy files that conftest/OPA can consume.
"""

import os
import tempfile
import textwrap
import unittest

from thothctl.services.check.rules_compiler import RulesCompiler


class TestRulesCompilerNaming(unittest.TestCase):
    """Test naming rule compilation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.compiler = RulesCompiler(output_dir=self.tmpdir)

    def test_compile_naming_rule(self):
        """Naming rules produce a naming.rego file."""
        rules_config = {
            "naming": [
                {
                    "name": "resource_naming",
                    "severity": "error",
                    "config": {
                        "pattern": "^(dev|stg|prd)_[a-z_]+$",
                    },
                }
            ]
        }
        self.compiler._compile_naming_rules(
            rules_config["naming"], self.tmpdir
        )
        rego_path = os.path.join(self.tmpdir, "naming.rego")
        self.assertTrue(os.path.exists(rego_path))

        content = open(rego_path).read()
        self.assertIn("package main", content)
        self.assertIn("deny[msg]", content)
        self.assertIn("resource_naming", content)
        self.assertIn("regex.match", content)
        self.assertIn("^(dev|stg|prd)_[a-z_]+$", content)

    def test_compile_naming_with_resource_types(self):
        """Naming rules can filter by resource type."""
        rules_config = {
            "naming": [
                {
                    "name": "bucket_naming",
                    "severity": "warning",
                    "config": {
                        "pattern": "^my-org-.*",
                        "resource_types": ["aws_s3_bucket"],
                    },
                }
            ]
        }
        self.compiler._compile_naming_rules(
            rules_config["naming"], self.tmpdir
        )
        rego_path = os.path.join(self.tmpdir, "naming.rego")
        content = open(rego_path).read()
        # Warning severity → warn instead of deny
        self.assertIn("warn[msg]", content)
        self.assertIn("aws_s3_bucket", content)

    def test_disabled_rules_skipped(self):
        """Disabled rules are not compiled."""
        rules_config = {
            "naming": [
                {
                    "name": "disabled_rule",
                    "enabled": False,
                    "config": {"pattern": "^x.*"},
                }
            ]
        }
        result = self.compiler._compile_naming_rules(
            rules_config["naming"], self.tmpdir
        )
        self.assertIsNone(result)


class TestRulesCompilerTagging(unittest.TestCase):
    """Test tagging rule compilation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.compiler = RulesCompiler(output_dir=self.tmpdir)

    def test_compile_tagging_rule(self):
        """Tagging rules produce a tagging.rego file."""
        rules_config = {
            "tagging": [
                {
                    "name": "required_tags",
                    "config": {
                        "required_tags": ["Environment", "Owner", "CostCenter"],
                    },
                }
            ]
        }
        self.compiler._compile_tagging_rules(
            rules_config["tagging"], self.tmpdir
        )
        rego_path = os.path.join(self.tmpdir, "tagging.rego")
        self.assertTrue(os.path.exists(rego_path))

        content = open(rego_path).read()
        self.assertIn("package main", content)
        self.assertIn("deny[msg]", content)
        self.assertIn("Environment", content)
        self.assertIn("Owner", content)
        self.assertIn("CostCenter", content)
        self.assertIn("required_tag", content)


class TestRulesCompilerSecurity(unittest.TestCase):
    """Test security rule compilation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.compiler = RulesCompiler(output_dir=self.tmpdir)

    def test_compile_security_rule(self):
        """Security rules produce a security.rego file with banned patterns."""
        rules_config = {
            "security": [
                {
                    "name": "no_public",
                    "severity": "error",
                    "config": {
                        "banned_patterns": [
                            "acl.*public",
                            "publicly_accessible.*true",
                        ],
                    },
                }
            ]
        }
        self.compiler._compile_security_rules(
            rules_config["security"], self.tmpdir
        )
        rego_path = os.path.join(self.tmpdir, "security.rego")
        self.assertTrue(os.path.exists(rego_path))

        content = open(rego_path).read()
        self.assertIn("package main", content)
        self.assertIn("deny[msg]", content)
        self.assertIn("acl.*public", content)
        self.assertIn("publicly_accessible.*true", content)
        self.assertIn("walk(instance", content)


class TestRulesCompilerArchitecture(unittest.TestCase):
    """Test architecture rule compilation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.compiler = RulesCompiler(output_dir=self.tmpdir)

    def test_compile_multi_az_rule(self):
        """Architecture rules compile multi-AZ checks."""
        rules_config = {
            "architecture": [
                {
                    "name": "ha_databases",
                    "config": {"require_multi_az": True},
                }
            ]
        }
        self.compiler._compile_architecture_rules(
            rules_config["architecture"], self.tmpdir
        )
        rego_path = os.path.join(self.tmpdir, "architecture.rego")
        content = open(rego_path).read()
        self.assertIn("multi_az", content)
        self.assertIn("aws_db_instance", content)

    def test_compile_require_modules(self):
        """Architecture rules compile module requirement checks."""
        rules_config = {
            "architecture": [
                {
                    "name": "approved_modules",
                    "config": {
                        "require_modules": [
                            "terraform-aws-modules/vpc/aws"
                        ],
                    },
                }
            ]
        }
        self.compiler._compile_architecture_rules(
            rules_config["architecture"], self.tmpdir
        )
        rego_path = os.path.join(self.tmpdir, "architecture.rego")
        content = open(rego_path).read()
        self.assertIn("terraform-aws-modules/vpc/aws", content)

    def test_compile_max_resources(self):
        """Architecture rules compile max resources per file."""
        rules_config = {
            "architecture": [
                {
                    "name": "file_size",
                    "config": {"max_resources_per_file": 10},
                }
            ]
        }
        self.compiler._compile_architecture_rules(
            rules_config["architecture"], self.tmpdir
        )
        rego_path = os.path.join(self.tmpdir, "architecture.rego")
        content = open(rego_path).read()
        self.assertIn("count(resources) > 10", content)


class TestRulesCompilerFull(unittest.TestCase):
    """Test full compilation from .thothcf.toml."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.tmpdir, "compiled")
        self.compiler = RulesCompiler(output_dir=self.output_dir)

    def test_compile_from_toml(self):
        """Full pipeline: write .thothcf.toml, compile, verify output."""
        toml_content = textwrap.dedent("""\
            [project]
            name = "test-infra"

            [[rules.naming]]
            name = "resource_naming"
            severity = "error"
            [rules.naming.config]
            pattern = "^(dev|stg|prd)_.*"

            [[rules.tagging]]
            name = "required_tags"
            [rules.tagging.config]
            required_tags = ["Environment", "Owner"]

            [[rules.security]]
            name = "no_public"
            [rules.security.config]
            banned_patterns = ["acl.*public"]

            [[rules.architecture]]
            name = "ha"
            [rules.architecture.config]
            require_multi_az = true
        """)

        config_path = os.path.join(self.tmpdir, ".thothcf.toml")
        with open(config_path, "w") as f:
            f.write(toml_content)

        result = self.compiler.compile(self.tmpdir)
        self.assertIsNotNone(result)
        self.assertEqual(result, self.output_dir)

        # All 4 rego files should exist
        self.assertTrue(os.path.exists(os.path.join(result, "naming.rego")))
        self.assertTrue(os.path.exists(os.path.join(result, "tagging.rego")))
        self.assertTrue(os.path.exists(os.path.join(result, "security.rego")))
        self.assertTrue(
            os.path.exists(os.path.join(result, "architecture.rego"))
        )

    def test_compile_no_rules_returns_none(self):
        """If no rules section, compile returns None."""
        toml_content = "[project]\nname = \"test\"\n"
        config_path = os.path.join(self.tmpdir, ".thothcf.toml")
        with open(config_path, "w") as f:
            f.write(toml_content)

        result = self.compiler.compile(self.tmpdir)
        self.assertIsNone(result)

    def test_compile_no_toml_returns_none(self):
        """If no .thothcf.toml, compile returns None."""
        result = self.compiler.compile(self.tmpdir)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
