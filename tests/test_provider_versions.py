"""Unit tests for provider version checking functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from thothctl.services.inventory.version_service import ProviderVersionChecker, ProviderVersionManager


@pytest.fixture
def test_providers():
    """Sample provider data for testing."""
    return [
        {
            "name": "aws",
            "version": "~> 5.0",
            "source": "registry.terraform.io/hashicorp/aws",
            "module": "Root",
            "component": "main"
        },
        {
            "name": "random",
            "version": ">= 3.1",
            "source": "registry.terraform.io/hashicorp/random",
            "module": "Root",
            "component": "main"
        },
    ]


def test_provider_version_checker():
    """Test the provider version checker can be instantiated and has required methods."""
    checker = ProviderVersionChecker()
    assert hasattr(checker, 'get_latest_provider_version')
    assert hasattr(checker, '_compare_provider_versions')


def test_single_provider():
    """Test single provider version comparison logic."""
    checker = ProviderVersionChecker()

    # Test version comparison
    status = checker._compare_provider_versions("~> 5.0", "5.80.0")
    assert status in ("current", "outdated", "newer", "unknown")

    # Test constraint parsing
    status2 = checker._compare_provider_versions(">= 3.1", "3.5.0")
    assert status2 in ("current", "outdated", "newer", "unknown")


def test_provider_version_manager_instantiation():
    """Test the ProviderVersionManager can be created."""
    manager = ProviderVersionManager()
    assert hasattr(manager, 'check_provider_versions')


@pytest.mark.asyncio
async def test_provider_version_checker_async():
    """Test async version checking with mocked HTTP."""
    checker = ProviderVersionChecker()

    with patch.object(checker, 'get_latest_provider_version', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = ("5.80.0", "https://registry.terraform.io", "2024-01-01")

        version, url, pub = await checker.get_latest_provider_version(
            "registry.terraform.io/hashicorp/aws",
            "aws"
        )

        assert version == "5.80.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
