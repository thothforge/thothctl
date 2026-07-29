"""Tests for CDK construct library inventory: parsers, SBOM, and compatibility."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thothctl.services.inventory.cdk_parsers import (
    CDKInventoryResult,
    ConstructDependency,
    PythonParser,
    TypeScriptParser,
    detect_cdk_project,
    is_cdk_package,
    is_internal_package,
    run_cdk_inventory,
)
from thothctl.services.inventory.cdk_sbom_service import (
    CDKCompatibilityChecker,
    CDKSbomGenerator,
)


# ── CDK Package Detection ─────────────────────────────────────────────────────


class TestIsCdkPackage:
    def test_aws_cdk_lib(self):
        assert is_cdk_package("aws-cdk-lib") is True

    def test_constructs(self):
        assert is_cdk_package("constructs") is True

    def test_cdk_nag(self):
        assert is_cdk_package("cdk-nag") is True

    def test_cdk_prefix(self):
        assert is_cdk_package("cdk-lambda-powertools") is True

    def test_cdklabs_scope(self):
        assert is_cdk_package("@cdklabs/cdk-validator") is True

    def test_internal_org_package(self):
        assert is_cdk_package("@myorg/cdk-patterns") is True

    def test_unrelated_package(self):
        assert is_cdk_package("express") is False

    def test_types_package(self):
        assert is_cdk_package("@types/node") is False

    def test_jest(self):
        assert is_cdk_package("jest") is False


class TestIsInternalPackage:
    def test_org_scoped(self):
        assert is_internal_package("@mycompany/cdk-vpc") is True

    def test_aws_cdk_not_internal(self):
        assert is_internal_package("@aws-cdk/aws-lambda") is False

    def test_cdklabs_not_internal(self):
        assert is_internal_package("@cdklabs/something") is False

    def test_unscoped_not_internal(self):
        assert is_internal_package("aws-cdk-lib") is False


# ── TypeScript Parser ──────────────────────────────────────────────────────────


class TestTypeScriptParser:
    def setup_method(self):
        self.parser = TypeScriptParser()

    def test_detect_cdk_project(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "package.json").write_text("{}")
        assert self.parser.detect(tmp_path) is True

    def test_detect_no_cdk_json(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        assert self.parser.detect(tmp_path) is False

    def test_detect_no_package_json(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        assert self.parser.detect(tmp_path) is False

    def test_parse_dependencies(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "package.json").write_text(
            json.dumps(
                {
                    "dependencies": {
                        "aws-cdk-lib": "^2.262.0",
                        "constructs": "^10.7.0",
                        "express": "^4.18.0",
                    },
                    "devDependencies": {
                        "cdk-nag": "^3.0.1",
                        "jest": "^30",
                    },
                }
            )
        )

        deps = self.parser.parse_dependencies(tmp_path)

        # Should only include CDK-related packages (not express, jest)
        names = [d.name for d in deps]
        assert "aws-cdk-lib" in names
        assert "constructs" in names
        assert "cdk-nag" in names
        assert "express" not in names
        assert "jest" not in names

    def test_parse_dependencies_with_lock_file(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"aws-cdk-lib": "^2.262.0"}})
        )
        (tmp_path / "package-lock.json").write_text(
            json.dumps(
                {
                    "packages": {
                        "node_modules/aws-cdk-lib": {
                            "version": "2.262.1",
                            "integrity": "sha512-abc123def456",
                        }
                    }
                }
            )
        )

        deps = self.parser.parse_dependencies(tmp_path)
        assert len(deps) == 1
        assert deps[0].version == "2.262.1"  # Resolved from lock file
        assert deps[0].integrity_hash == "sha512-abc123def456"

    def test_parse_purl_format(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"aws-cdk-lib": "^2.262.0"}})
        )

        deps = self.parser.parse_dependencies(tmp_path)
        assert deps[0].purl == "pkg:npm/aws-cdk-lib@2.262.0"

    def test_parse_empty_package_json(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "package.json").write_text("{}")

        deps = self.parser.parse_dependencies(tmp_path)
        assert deps == []


# ── Python Parser ──────────────────────────────────────────────────────────────


class TestPythonParser:
    def setup_method(self):
        self.parser = PythonParser()

    def test_detect_cdk_python_project(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "requirements.txt").write_text("aws-cdk-lib==2.100.0")
        assert self.parser.detect(tmp_path) is True

    def test_detect_pyproject(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        assert self.parser.detect(tmp_path) is True

    def test_detect_no_cdk_json(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("aws-cdk-lib==2.100.0")
        assert self.parser.detect(tmp_path) is False

    def test_parse_requirements_txt(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "requirements.txt").write_text(
            "aws-cdk-lib==2.100.0\nconstructs>=10.0.0\nflask==2.0\ncdk-nag~=2.27.0\n"
        )

        deps = self.parser.parse_dependencies(tmp_path)
        names = [d.name for d in deps]
        assert "aws-cdk-lib" in names
        assert "constructs" in names
        assert "cdk-nag" in names
        assert "flask" not in names

    def test_parse_purl_pypi(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "requirements.txt").write_text("aws-cdk-lib==2.100.0\n")

        deps = self.parser.parse_dependencies(tmp_path)
        assert deps[0].purl == "pkg:pypi/aws-cdk-lib@2.100.0"
        assert deps[0].registry == "pypi"


# ── Project Detection ──────────────────────────────────────────────────────────


class TestDetectCdkProject:
    def test_detect_typescript(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "package.json").write_text("{}")
        parser = detect_cdk_project(tmp_path)
        assert isinstance(parser, TypeScriptParser)

    def test_detect_python(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "requirements.txt").write_text("")
        parser = detect_cdk_project(tmp_path)
        assert isinstance(parser, PythonParser)

    def test_detect_no_cdk(self, tmp_path):
        (tmp_path / "main.tf").write_text("")
        parser = detect_cdk_project(tmp_path)
        assert parser is None


# ── Run CDK Inventory ──────────────────────────────────────────────────────────


class TestRunCdkInventory:
    def test_returns_none_for_non_cdk(self, tmp_path):
        result = run_cdk_inventory(tmp_path, check_versions=False)
        assert result is None

    def test_returns_result_for_cdk_project(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"aws-cdk-lib": "^2.262.0"}})
        )

        result = run_cdk_inventory(tmp_path, check_versions=False)
        assert isinstance(result, CDKInventoryResult)
        assert result.language == "typescript"
        assert result.total_constructs == 1

    def test_counts_outdated(self, tmp_path):
        (tmp_path / "cdk.json").write_text("{}")
        (tmp_path / "package.json").write_text(
            json.dumps(
                {
                    "dependencies": {
                        "aws-cdk-lib": "^2.262.0",
                        "constructs": "^10.7.0",
                    }
                }
            )
        )

        # Mock version checking
        with patch.object(
            TypeScriptParser,
            "check_latest_versions",
            return_value=[
                ConstructDependency(
                    name="aws-cdk-lib",
                    version="2.262.0",
                    latest_version="2.262.2",
                    is_outdated=True,
                    registry="npm",
                    purl="pkg:npm/aws-cdk-lib@2.262.0",
                ),
                ConstructDependency(
                    name="constructs",
                    version="10.7.0",
                    latest_version="10.7.0",
                    is_outdated=False,
                    registry="npm",
                    purl="pkg:npm/constructs@10.7.0",
                ),
            ],
        ):
            result = run_cdk_inventory(tmp_path, check_versions=True)
            assert result.outdated_count == 1
            assert result.up_to_date_count == 1


# ── SBOM Generator ─────────────────────────────────────────────────────────────


class TestCDKSbomGenerator:
    def setup_method(self):
        self.generator = CDKSbomGenerator()
        self.inventory = {
            "projectName": "test-project",
            "version": "1.0.0",
            "components": [
                {
                    "stack": "./dependencies",
                    "components": [
                        {
                            "name": "aws-cdk-lib",
                            "version": ["2.262.0"],
                            "latest_version": "2.262.2",
                            "type": "cdk_construct",
                            "status": "Outdated",
                            "source": ["npm:aws-cdk-lib"],
                            "source_url": "https://www.npmjs.com/package/aws-cdk-lib",
                            "release_date": "2026-07-29",
                            "license": "Apache-2.0",
                            "file": "package.json",
                        },
                        {
                            "name": "cdk-nag",
                            "version": ["3.0.1"],
                            "latest_version": "3.0.1",
                            "type": "cdk_construct",
                            "status": "Updated",
                            "source": ["npm:cdk-nag"],
                            "license": "Apache-2.0",
                            "file": "package.json",
                        },
                    ],
                }
            ],
        }

    def test_generates_valid_cyclonedx(self):
        sbom = self.generator.generate(self.inventory, project_name="test")
        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.6"
        assert sbom["serialNumber"].startswith("urn:uuid:")

    def test_components_have_purls(self):
        sbom = self.generator.generate(self.inventory)
        assert len(sbom["components"]) == 2
        assert sbom["components"][0]["purl"] == "pkg:npm/aws-cdk-lib@2.262.0"
        assert sbom["components"][1]["purl"] == "pkg:npm/cdk-nag@3.0.1"

    def test_components_have_licenses(self):
        sbom = self.generator.generate(self.inventory)
        assert sbom["components"][0]["licenses"] == [
            {"license": {"id": "Apache-2.0"}}
        ]

    def test_components_have_evidence(self):
        sbom = self.generator.generate(self.inventory)
        evidence = sbom["components"][0]["evidence"]
        assert evidence["identity"]["field"] == "purl"
        assert evidence["identity"]["confidence"] == 0.95
        assert evidence["identity"]["methods"][0]["technique"] == "source-code-analysis"
        assert "package.json" in evidence["identity"]["methods"][0]["value"]

    def test_has_formulation_with_tools(self):
        sbom = self.generator.generate(self.inventory)
        formulation = sbom["formulation"]
        assert len(formulation) == 1
        tools = formulation[0]["components"]
        tool_names = [t["name"] for t in tools]
        assert "thothctl" in tool_names
        assert "npm registry" in tool_names

    def test_has_dependencies(self):
        sbom = self.generator.generate(self.inventory)
        assert len(sbom["dependencies"]) == 2

    def test_properties_include_staleness(self):
        sbom = self.generator.generate(self.inventory)
        props = {p["name"]: p["value"] for p in sbom["components"][0]["properties"]}
        assert props["iac:latest-available"] == "2.262.2"
        assert props["iac:outdated"] == "true"
        assert props["iac:last-updated"] == "2026-07-29"
        assert props["iac:source-type"] == "npm"

    def test_writes_to_file(self, tmp_path):
        output = tmp_path / "sbom.json"
        self.generator.generate(self.inventory, output_path=output)
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["bomFormat"] == "CycloneDX"

    def test_no_license_when_empty(self):
        self.inventory["components"][0]["components"][1]["license"] = ""
        sbom = self.generator.generate(self.inventory)
        assert sbom["components"][1]["licenses"] == []


# ── Compatibility Checker ──────────────────────────────────────────────────────


class TestCDKCompatibilityChecker:
    def setup_method(self):
        self.checker = CDKCompatibilityChecker()

    def test_patch_upgrade_is_safe(self):
        comps = [
            {
                "name": "aws-cdk-lib",
                "version": ["2.262.0"],
                "latest_version": "2.262.2",
                "type": "cdk_construct",
                "status": "Outdated",
            }
        ]
        reports = self.checker.check_compatibility(comps)
        assert len(reports) == 1
        assert reports[0]["semver_change"] == "patch"
        assert reports[0]["upgrade_safe"] is True
        assert reports[0]["is_breaking"] is False

    def test_minor_upgrade_is_safe(self):
        comps = [
            {
                "name": "constructs",
                "version": ["10.5.0"],
                "latest_version": "10.7.0",
                "type": "cdk_construct",
                "status": "Outdated",
            }
        ]
        reports = self.checker.check_compatibility(comps)
        assert reports[0]["semver_change"] == "minor"
        assert reports[0]["upgrade_safe"] is True

    def test_major_upgrade_is_breaking(self):
        comps = [
            {
                "name": "cdk-nag",
                "version": ["2.38.0"],
                "latest_version": "3.0.1",
                "type": "cdk_construct",
                "status": "Outdated",
            }
        ]
        reports = self.checker.check_compatibility(comps)
        assert reports[0]["semver_change"] == "major"
        assert reports[0]["is_breaking"] is True
        assert reports[0]["upgrade_safe"] is False

    def test_skips_up_to_date_components(self):
        comps = [
            {
                "name": "cdk-nag",
                "version": ["3.0.1"],
                "latest_version": "3.0.1",
                "type": "cdk_construct",
                "status": "Updated",
            }
        ]
        reports = self.checker.check_compatibility(comps)
        assert reports == []

    def test_skips_non_cdk_components(self):
        comps = [
            {
                "name": "vpc-module",
                "version": ["5.0.0"],
                "latest_version": "6.0.0",
                "type": "module",
                "status": "Outdated",
            }
        ]
        reports = self.checker.check_compatibility(comps)
        assert reports == []

    def test_recommendations_for_patch(self):
        comps = [
            {
                "name": "aws-cdk-lib",
                "version": ["2.262.0"],
                "latest_version": "2.262.2",
                "type": "cdk_construct",
                "status": "Outdated",
            }
        ]
        reports = self.checker.check_compatibility(comps)
        assert "bug fixes only" in reports[0]["recommendations"][0].lower()

    def test_recommendations_for_major(self):
        comps = [
            {
                "name": "cdk-nag",
                "version": ["2.38.0"],
                "latest_version": "3.0.1",
                "type": "cdk_construct",
                "status": "Outdated",
            }
        ]
        reports = self.checker.check_compatibility(comps)
        assert "breaking" in reports[0]["recommendations"][0].lower()
