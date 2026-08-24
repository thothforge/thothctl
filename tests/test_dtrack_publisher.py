"""Unit tests for DependencyTrackPublisher — SBOM upload to Dependency-Track."""

import base64
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thothctl.services.inventory.dtrack_publisher import (
    API_PREFIX,
    DependencyTrackPublisher,
    DTrackConfig,
    PublishResult,
)


# --- Fixtures ---


@pytest.fixture
def config():
    """Valid DTrack config for tests."""
    return DTrackConfig(
        url="https://dtrack.example.com",
        api_key="test-api-key-12345",
        project_name="my-infra-project",
        project_version="1.0.0",
        auto_create=True,
    )


@pytest.fixture
def publisher(config):
    """Publisher with mocked config."""
    return DependencyTrackPublisher(config)


@pytest.fixture
def sbom_file(tmp_path):
    """Create a temporary CycloneDX SBOM file."""
    sbom_data = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {
                "name": "test-project",
                "version": "1.0.0",
                "type": "application",
            }
        },
        "components": [
            {
                "type": "library",
                "name": "terraform-aws-modules/vpc/aws",
                "version": "5.16.0",
            }
        ],
    }
    sbom_path = tmp_path / "sbom-cyclonedx.json"
    sbom_path.write_text(json.dumps(sbom_data))
    return sbom_path


# --- DTrackConfig Tests ---


class TestDTrackConfig:
    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("DTRACK_URL", "https://dtrack.test.com")
        monkeypatch.setenv("DTRACK_API_KEY", "env-key-123")
        monkeypatch.setenv("DTRACK_PROJECT_NAME", "env-project")
        monkeypatch.setenv("DTRACK_PROJECT_VERSION", "2.0.0")

        config = DTrackConfig.from_env()

        assert config.url == "https://dtrack.test.com"
        assert config.api_key == "env-key-123"
        assert config.project_name == "env-project"
        assert config.project_version == "2.0.0"
        assert config.auto_create is True

    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("DTRACK_URL", raising=False)
        monkeypatch.delenv("DTRACK_API_KEY", raising=False)
        monkeypatch.delenv("DTRACK_PROJECT_NAME", raising=False)

        config = DTrackConfig.from_env()

        assert config.url == ""
        assert config.api_key == ""
        assert config.project_name is None
        assert config.project_version == "latest"

    def test_from_toml(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DTRACK_URL", raising=False)
        monkeypatch.delenv("DTRACK_API_KEY", raising=False)

        toml_content = """
[integrations.dependency_track]
url = "https://dtrack.toml.com"
api_key = "toml-key-456"
project_name = "toml-project"
project_version = "3.0.0"
auto_create = false
parent_project = "parent-org"
"""
        (tmp_path / ".thothcf.toml").write_text(toml_content)

        config = DTrackConfig.from_toml(str(tmp_path))

        assert config.url == "https://dtrack.toml.com"
        assert config.api_key == "toml-key-456"
        assert config.project_name == "toml-project"
        assert config.project_version == "3.0.0"
        assert config.auto_create is False
        assert config.parent_project == "parent-org"

    def test_env_overrides_toml(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DTRACK_URL", "https://dtrack.env.com")
        monkeypatch.setenv("DTRACK_API_KEY", "env-key")

        toml_content = """
[integrations.dependency_track]
url = "https://dtrack.toml.com"
api_key = "toml-key"
"""
        (tmp_path / ".thothcf.toml").write_text(toml_content)

        config = DTrackConfig.from_toml(str(tmp_path))

        assert config.url == "https://dtrack.env.com"
        assert config.api_key == "env-key"

    def test_validate_missing_url(self):
        config = DTrackConfig(url="", api_key="key")
        with pytest.raises(ValueError, match="URL not configured"):
            config.validate()

    def test_validate_missing_api_key(self):
        config = DTrackConfig(url="https://dtrack.com", api_key="")
        with pytest.raises(ValueError, match="API key not configured"):
            config.validate()

    def test_validate_success(self, config):
        config.validate()  # Should not raise

    def test_base_url_adds_prefix(self):
        config = DTrackConfig(url="https://dtrack.com", api_key="key")
        assert config.base_url == f"https://dtrack.com{API_PREFIX}"

    def test_base_url_no_double_prefix(self):
        config = DTrackConfig(url="https://dtrack.com/api/v1", api_key="key")
        assert config.base_url == "https://dtrack.com/api/v1"

    def test_base_url_strips_trailing_slash(self):
        config = DTrackConfig(url="https://dtrack.com/", api_key="key")
        assert config.base_url == f"https://dtrack.com{API_PREFIX}"


# --- Publisher Init Tests ---


class TestPublisherInit:
    def test_init_success(self, config):
        publisher = DependencyTrackPublisher(config)
        assert publisher.config == config

    def test_init_raises_on_invalid_config(self):
        with pytest.raises(ValueError):
            DependencyTrackPublisher(DTrackConfig(url="", api_key=""))

    def test_headers_contain_api_key(self, publisher):
        assert publisher._session.headers["X-Api-Key"] == "test-api-key-12345"
        assert publisher._session.headers["Accept"] == "application/json"


# --- Publish Tests ---


class TestPublish:
    def test_successful_publish(self, publisher, sbom_file):
        """Test successful BOM upload returns token."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "abc-123-token"}

        with patch.object(publisher._session, "put", return_value=mock_response):
            result = publisher.publish(sbom_file)

        assert result.success is True
        assert result.project_name == "my-infra-project"
        assert result.project_version == "1.0.0"
        assert result.token == "abc-123-token"
        assert result.project_url is not None

    def test_publish_sends_base64_bom(self, publisher, sbom_file):
        """Verify the BOM is base64-encoded in the request payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "t"}

        with patch.object(publisher._session, "put", return_value=mock_response) as mock_put:
            publisher.publish(sbom_file)

        call_kwargs = mock_put.call_args[1]
        payload = call_kwargs["json"]
        # Verify BOM is base64
        decoded = base64.b64decode(payload["bom"])
        assert b"CycloneDX" in decoded
        assert payload["projectName"] == "my-infra-project"
        assert payload["projectVersion"] == "1.0.0"
        assert payload["autoCreate"] is True

    def test_publish_file_not_found(self, publisher, tmp_path):
        """Test handling of missing SBOM file."""
        result = publisher.publish(tmp_path / "nonexistent.json")

        assert result.success is False
        assert "not found" in result.error

    def test_publish_auth_failure(self, publisher, sbom_file):
        """Test 401 response handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(publisher._session, "put", return_value=mock_response):
            result = publisher.publish(sbom_file)

        assert result.success is False
        assert "Authentication failed" in result.error

    def test_publish_forbidden(self, publisher, sbom_file):
        """Test 403 response handling."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(publisher._session, "put", return_value=mock_response):
            result = publisher.publish(sbom_file)

        assert result.success is False
        assert "Forbidden" in result.error
        assert "BOM_UPLOAD" in result.error

    def test_publish_server_error(self, publisher, sbom_file):
        """Test 500 response handling."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(publisher._session, "put", return_value=mock_response):
            result = publisher.publish(sbom_file)

        assert result.success is False
        assert "500" in result.error

    def test_publish_connection_error(self, publisher, sbom_file):
        """Test connection failure handling."""
        import requests

        with patch.object(
            publisher._session, "put", side_effect=requests.ConnectionError()
        ):
            result = publisher.publish(sbom_file)

        assert result.success is False
        assert "Cannot connect" in result.error

    def test_publish_timeout(self, publisher, sbom_file):
        """Test request timeout handling."""
        import requests

        with patch.object(
            publisher._session, "put", side_effect=requests.Timeout()
        ):
            result = publisher.publish(sbom_file)

        assert result.success is False
        assert "timed out" in result.error

    def test_publish_resolves_name_from_sbom(self, config, sbom_file):
        """Test that project name is extracted from SBOM metadata when not configured."""
        config.project_name = None
        publisher = DependencyTrackPublisher(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "t"}

        with patch.object(publisher._session, "put", return_value=mock_response) as mock_put:
            result = publisher.publish(sbom_file)

        payload = mock_put.call_args[1]["json"]
        assert payload["projectName"] == "test-project"  # From SBOM metadata
        assert result.success is True

    def test_publish_fails_without_project_name(self, config, tmp_path):
        """Test that publish fails gracefully when no project name can be determined."""
        config.project_name = None
        publisher = DependencyTrackPublisher(config)

        # SBOM without metadata.component.name
        sbom = {"bomFormat": "CycloneDX", "components": []}
        sbom_path = tmp_path / "bare-sbom.json"
        sbom_path.write_text(json.dumps(sbom))

        result = publisher.publish(sbom_path)

        assert result.success is False
        assert "Project name" in result.error

    def test_publish_with_parent_project(self, sbom_file):
        """Test parent project UUID lookup and inclusion in payload."""
        config = DTrackConfig(
            url="https://dtrack.com",
            api_key="key",
            project_name="child-project",
            parent_project="org-parent",
        )
        publisher = DependencyTrackPublisher(config)

        # Mock the parent project lookup
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = [{"uuid": "parent-uuid-123"}]

        mock_put_response = MagicMock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {"token": "t"}

        with patch.object(publisher._session, "get", return_value=mock_get_response):
            with patch.object(publisher._session, "put", return_value=mock_put_response) as mock_put:
                publisher.publish(sbom_file)

        payload = mock_put.call_args[1]["json"]
        assert payload["parentUUID"] == "parent-uuid-123"


# --- Project Lookup Tests ---


class TestProjectLookup:
    def test_lookup_found(self, publisher):
        """Test successful project lookup by name."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"uuid": "proj-uuid-456", "name": "my-project"}
        ]

        with patch.object(publisher._session, "get", return_value=mock_response):
            uuid = publisher._lookup_project_uuid("my-project")

        assert uuid == "proj-uuid-456"

    def test_lookup_not_found(self, publisher):
        """Test project not found returns None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch.object(publisher._session, "get", return_value=mock_response):
            uuid = publisher._lookup_project_uuid("nonexistent")

        assert uuid is None

    def test_lookup_error(self, publisher):
        """Test lookup failure returns None gracefully."""
        with patch.object(publisher._session, "get", side_effect=Exception("err")):
            uuid = publisher._lookup_project_uuid("project")

        assert uuid is None


# --- Processing Status Tests ---


class TestProcessingStatus:
    def test_processing_complete(self, publisher):
        """Test status check when processing is done."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"processing": False}

        with patch.object(publisher._session, "get", return_value=mock_response):
            result = publisher.check_processing_status("token-123")

        assert result is True

    def test_processing_in_progress(self, publisher):
        """Test status check when still processing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"processing": True}

        with patch.object(publisher._session, "get", return_value=mock_response):
            result = publisher.check_processing_status("token-123")

        assert result is False

    def test_processing_empty_token(self, publisher):
        """Test status check with empty token returns None."""
        result = publisher.check_processing_status("")
        assert result is None

    def test_processing_error(self, publisher):
        """Test status check failure returns None."""
        with patch.object(publisher._session, "get", side_effect=Exception("err")):
            result = publisher.check_processing_status("token-123")

        assert result is None
