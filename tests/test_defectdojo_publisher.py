"""Unit tests for DefectDojoPublisher — SBOM upload to DefectDojo."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thothctl.services.inventory.defectdojo_publisher import (
    API_PREFIX,
    SCAN_TYPE_CYCLONEDX,
    DefectDojoConfig,
    DefectDojoPublisher,
    DefectDojoPublishResult,
)


# --- Fixtures ---


@pytest.fixture
def config():
    """Valid DefectDojo config for tests."""
    return DefectDojoConfig(
        url="http://defectdojo.example.com:8090",
        token="test-token-12345",
        product_name="my-infra-project",
        engagement_name="IaC Supply Chain Inventory",
        auto_create=True,
    )


@pytest.fixture
def publisher(config):
    """Publisher with mocked config."""
    return DefectDojoPublisher(config)


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
                "group": "terraform-aws-modules",
            }
        ],
    }
    sbom_path = tmp_path / "sbom-cyclonedx.json"
    sbom_path.write_text(json.dumps(sbom_data))
    return sbom_path


# --- Config Tests ---


class TestDefectDojoConfig:
    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("DEFECTDOJO_URL", "http://dd.test.com:8090")
        monkeypatch.setenv("DEFECTDOJO_TOKEN", "env-token-123")
        monkeypatch.setenv("DEFECTDOJO_PRODUCT_NAME", "env-product")

        config = DefectDojoConfig.from_env()

        assert config.url == "http://dd.test.com:8090"
        assert config.token == "env-token-123"
        assert config.product_name == "env-product"
        assert config.auto_create is True

    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("DEFECTDOJO_URL", raising=False)
        monkeypatch.delenv("DEFECTDOJO_TOKEN", raising=False)

        config = DefectDojoConfig.from_env()

        assert config.url == ""
        assert config.token == ""
        assert config.product_type_name == "Infrastructure"

    def test_from_toml(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DEFECTDOJO_URL", raising=False)
        monkeypatch.delenv("DEFECTDOJO_TOKEN", raising=False)

        toml_content = """
[integrations.defectdojo]
url = "http://dd.toml.com:8090"
token = "toml-token-456"
product_name = "toml-product"
engagement_name = "CI/CD Scan"
auto_create = false
close_old_findings = false
"""
        (tmp_path / ".thothcf.toml").write_text(toml_content)

        config = DefectDojoConfig.from_toml(str(tmp_path))

        assert config.url == "http://dd.toml.com:8090"
        assert config.token == "toml-token-456"
        assert config.product_name == "toml-product"
        assert config.engagement_name == "CI/CD Scan"
        assert config.auto_create is False
        assert config.close_old_findings is False

    def test_validate_missing_url(self):
        config = DefectDojoConfig(url="", token="token")
        with pytest.raises(ValueError, match="URL not configured"):
            config.validate()

    def test_validate_missing_token(self):
        config = DefectDojoConfig(url="http://dd.com", token="")
        with pytest.raises(ValueError, match="token not configured"):
            config.validate()

    def test_validate_success(self, config):
        config.validate()  # Should not raise

    def test_base_url_adds_prefix(self):
        config = DefectDojoConfig(url="http://dd.com:8090", token="t")
        assert config.base_url == f"http://dd.com:8090{API_PREFIX}"

    def test_base_url_no_double_prefix(self):
        config = DefectDojoConfig(url="http://dd.com:8090/api/v2", token="t")
        assert config.base_url == "http://dd.com:8090/api/v2"


# --- Publisher Init Tests ---


class TestPublisherInit:
    def test_init_success(self, config):
        publisher = DefectDojoPublisher(config)
        assert publisher.config == config

    def test_init_raises_on_invalid_config(self):
        with pytest.raises(ValueError):
            DefectDojoPublisher(DefectDojoConfig(url="", token=""))

    def test_headers_contain_token(self, publisher):
        assert publisher._session.headers["Authorization"] == "Token test-token-12345"
        assert publisher._session.headers["Accept"] == "application/json"


# --- Publish Tests ---


class TestPublish:
    def test_successful_publish(self, publisher, sbom_file):
        """Test successful reimport-scan upload."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "test": 42,
            "statistics": {"after": {"total": 5}},
        }

        # Mock product and engagement lookup
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {"results": [{"id": 1}]}

        with patch.object(publisher._session, "get", return_value=mock_get):
            with patch.object(publisher._session, "post", return_value=mock_response):
                result = publisher.publish(sbom_file)

        assert result.success is True
        assert result.product_name == "my-infra-project"
        assert result.engagement_name == "IaC Supply Chain Inventory"
        assert result.test_id == 42
        assert result.findings_count == 5

    def test_publish_file_not_found(self, publisher, tmp_path):
        """Test handling of missing SBOM file."""
        result = publisher.publish(tmp_path / "nonexistent.json")
        assert result.success is False
        assert "not found" in result.error

    def test_publish_no_product_name(self, tmp_path):
        """Test failure when no product name configured."""
        config = DefectDojoConfig(
            url="http://dd.com", token="t", product_name=None
        )
        publisher = DefectDojoPublisher(config)
        sbom = tmp_path / "sbom.json"
        sbom.write_text('{"bomFormat": "CycloneDX"}')

        result = publisher.publish(sbom)
        assert result.success is False
        assert "Product name" in result.error

    def test_publish_auth_failure(self, publisher, sbom_file):
        """Test 401 response handling."""
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {"results": [{"id": 1}]}

        mock_post = MagicMock()
        mock_post.status_code = 401

        with patch.object(publisher._session, "get", return_value=mock_get):
            with patch.object(publisher._session, "post", return_value=mock_post):
                result = publisher.publish(sbom_file)

        assert result.success is False
        assert "Authentication failed" in result.error

    def test_publish_connection_error(self, publisher, sbom_file):
        """Test connection failure handling."""
        import requests

        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {"results": [{"id": 1}]}

        with patch.object(publisher._session, "get", return_value=mock_get):
            with patch.object(
                publisher._session, "post", side_effect=requests.ConnectionError()
            ):
                result = publisher.publish(sbom_file)

        assert result.success is False
        assert "Cannot connect" in result.error

    def test_publish_sends_multipart(self, publisher, sbom_file):
        """Verify the upload uses multipart form data with correct fields."""
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {"results": [{"id": 1}]}

        mock_post = MagicMock()
        mock_post.status_code = 201
        mock_post.json.return_value = {"test": 1}

        with patch.object(publisher._session, "get", return_value=mock_get):
            with patch.object(publisher._session, "post", return_value=mock_post) as mock:
                publisher.publish(sbom_file)

        call_kwargs = mock.call_args[1]
        assert "data" in call_kwargs
        assert "files" in call_kwargs
        assert call_kwargs["data"]["scan_type"] == SCAN_TYPE_CYCLONEDX
        assert call_kwargs["data"]["product_name"] == "my-infra-project"
        assert call_kwargs["data"]["engagement_name"] == "IaC Supply Chain Inventory"


# --- Product/Engagement Auto-Create Tests ---


class TestAutoCreate:
    def test_ensure_product_finds_existing(self, publisher):
        """Test finding an existing product by name."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"id": 42, "name": "my-project"}]
        }

        with patch.object(publisher._session, "get", return_value=mock_response):
            product_id = publisher._ensure_product("my-project")

        assert product_id == 42

    def test_ensure_product_creates_new(self, publisher):
        """Test creating a new product when not found."""
        # First call: GET products (not found)
        mock_get_empty = MagicMock()
        mock_get_empty.status_code = 200
        mock_get_empty.json.return_value = {"results": []}

        # Second call: GET product_types
        mock_get_type = MagicMock()
        mock_get_type.status_code = 200
        mock_get_type.json.return_value = {"results": [{"id": 1}]}

        # Third call: POST create product
        mock_post = MagicMock()
        mock_post.status_code = 201
        mock_post.json.return_value = {"id": 99}

        with patch.object(
            publisher._session, "get", side_effect=[mock_get_empty, mock_get_type]
        ):
            with patch.object(publisher._session, "post", return_value=mock_post):
                product_id = publisher._ensure_product("new-project")

        assert product_id == 99

    def test_ensure_engagement_finds_existing(self, publisher):
        """Test finding an existing engagement."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"id": 7, "name": "CI/CD Scan"}]
        }

        with patch.object(publisher._session, "get", return_value=mock_response):
            engagement_id = publisher._ensure_engagement(1, "CI/CD Scan")

        assert engagement_id == 7

    def test_ensure_engagement_creates_new(self, publisher):
        """Test creating a new engagement."""
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {"results": []}

        mock_post = MagicMock()
        mock_post.status_code = 201
        mock_post.json.return_value = {"id": 15}

        with patch.object(publisher._session, "get", return_value=mock_get):
            with patch.object(publisher._session, "post", return_value=mock_post):
                engagement_id = publisher._ensure_engagement(1, "New Engagement")

        assert engagement_id == 15
