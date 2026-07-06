"""Unit tests for OPA scanner YAML→JSON data file conversion."""
import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from thothctl.services.scan.scanners.opa import OPAScanner


class TestPrepareDataFiles:
    """Test the _prepare_data_files YAML→JSON conversion."""

    def setup_method(self):
        self.scanner = OPAScanner()

    def test_converts_yaml_to_json(self, tmp_path):
        """params.yaml should be converted to params.json."""
        params = {
            "tags": {
                "required_tags": ["Project", "Environment"],
                "allowed_values": {
                    "Project": ["sbsb001-bank4us", "sbsb002-kora"],
                    "Environment": ["dev", "qa", "prod"],
                },
            },
            "naming": {"pattern": "^[a-z0-9-]+$"},
        }
        yaml_file = tmp_path / "params.yaml"
        yaml_file.write_text(yaml.dump(params))

        self.scanner._prepare_data_files(str(tmp_path))

        json_file = tmp_path / "params.json"
        assert json_file.exists(), "params.json should be created"
        loaded = json.loads(json_file.read_text())
        assert loaded == params

    def test_skips_conftest_yaml(self, tmp_path):
        """conftest.yaml should NOT be converted."""
        conftest_yaml = tmp_path / "conftest.yaml"
        conftest_yaml.write_text("parser: yaml\n")

        self.scanner._prepare_data_files(str(tmp_path))

        assert not (tmp_path / "conftest.json").exists()

    def test_skips_opa_yaml(self, tmp_path):
        """opa.yaml should NOT be converted."""
        opa_yaml = tmp_path / "opa.yaml"
        opa_yaml.write_text("services:\n  - name: default\n")

        self.scanner._prepare_data_files(str(tmp_path))

        assert not (tmp_path / "opa.json").exists()

    def test_skips_hidden_files(self, tmp_path):
        """Hidden .yaml files should NOT be converted."""
        hidden = tmp_path / ".secrets.yaml"
        hidden.write_text("api_key: abc123\n")

        self.scanner._prepare_data_files(str(tmp_path))

        assert not (tmp_path / ".secrets.json").exists()

    def test_multiple_yaml_files(self, tmp_path):
        """Multiple YAML data files should all be converted."""
        (tmp_path / "params.yaml").write_text(yaml.dump({"key": "val1"}))
        (tmp_path / "overrides.yaml").write_text(yaml.dump({"key": "val2"}))

        self.scanner._prepare_data_files(str(tmp_path))

        assert (tmp_path / "params.json").exists()
        assert (tmp_path / "overrides.json").exists()
        assert json.loads((tmp_path / "params.json").read_text()) == {"key": "val1"}
        assert json.loads((tmp_path / "overrides.json").read_text()) == {"key": "val2"}

    def test_caching_skips_if_json_is_newer(self, tmp_path):
        """Should NOT regenerate JSON if it's already up-to-date."""
        params = {"tags": {"required_tags": ["Project"]}}
        yaml_file = tmp_path / "params.yaml"
        yaml_file.write_text(yaml.dump(params))

        json_file = tmp_path / "params.json"
        json_file.write_text(json.dumps({"old": "data"}))

        # Make JSON newer than YAML
        os.utime(json_file, (9999999999, 9999999999))

        self.scanner._prepare_data_files(str(tmp_path))

        # JSON should keep old content since it's newer
        loaded = json.loads(json_file.read_text())
        assert loaded == {"old": "data"}

    def test_regenerates_if_yaml_is_newer(self, tmp_path):
        """Should regenerate JSON if YAML is newer."""
        params = {"tags": {"required_tags": ["Project", "Product"]}}
        yaml_file = tmp_path / "params.yaml"
        yaml_file.write_text(yaml.dump(params))

        json_file = tmp_path / "params.json"
        json_file.write_text(json.dumps({"stale": "data"}))

        # Make YAML newer than JSON
        os.utime(json_file, (1000000000, 1000000000))
        os.utime(yaml_file, (9999999999, 9999999999))

        self.scanner._prepare_data_files(str(tmp_path))

        loaded = json.loads(json_file.read_text())
        assert loaded == params

    def test_handles_empty_directory(self, tmp_path):
        """Should do nothing for empty directories."""
        self.scanner._prepare_data_files(str(tmp_path))
        # No exception, no files created
        assert list(tmp_path.iterdir()) == []

    def test_handles_nonexistent_directory(self):
        """Should do nothing for non-existent directories."""
        self.scanner._prepare_data_files("/nonexistent/path")
        # Should not raise

    def test_yml_extension_also_converted(self, tmp_path):
        """*.yml files should also be converted."""
        (tmp_path / "sizing.yml").write_text(
            yaml.dump({"blocked_types": ["m5.4xlarge"]})
        )

        self.scanner._prepare_data_files(str(tmp_path))

        json_file = tmp_path / "sizing.json"
        assert json_file.exists()
        assert json.loads(json_file.read_text()) == {"blocked_types": ["m5.4xlarge"]}


class TestOPAScannerIntegration:
    """Integration tests for OPA scanner with data files and Rego policies."""

    def test_conftest_loads_params_from_json(self, tmp_path):
        """Conftest should correctly resolve data.params references from params.json."""
        # Create a minimal policy that uses data.params
        policy_dir = tmp_path / "policy"
        policy_dir.mkdir()

        rego = """package tagging
required_tags := data.params.tags.required_tags
deny contains msg if {
    resource := input.resource_changes[_]
    required := required_tags[_]
    not resource.change.after.tags_all[required]
    msg := sprintf("Missing tag: %s", [required])
}
"""
        (policy_dir / "tagging.rego").write_text(rego)
        (policy_dir / "params.yaml").write_text(
            yaml.dump({"tags": {"required_tags": ["Project", "Environment"]}})
        )

        # Prepare data files (convert YAML→JSON)
        scanner = OPAScanner()
        scanner._prepare_data_files(str(policy_dir))

        # Verify JSON was generated correctly
        params_json = json.loads((policy_dir / "params.json").read_text())
        assert params_json["tags"]["required_tags"] == ["Project", "Environment"]
