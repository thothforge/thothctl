"""Unit tests for AWS Pricing Client."""

import pytest
from unittest.mock import Mock, patch
from thothctl.services.check.project.cost.pricing.aws_pricing_client import AWSPricingClient


class TestAWSPricingClient:
    """Test AWS Pricing API client (public bulk pricing, no credentials)"""

    @pytest.fixture
    def pricing_client(self):
        """Pricing client instance"""
        return AWSPricingClient(region='us-east-1')

    def test_initialization(self, pricing_client):
        """Test client initialization"""
        assert pricing_client.region == 'us-east-1'
        assert pricing_client._index_cache is None
        assert pricing_client._api_available is None

    @patch('thothctl.services.check.project.cost.pricing.aws_pricing_client.requests.get')
    def test_is_available_success(self, mock_get, pricing_client):
        """Test API availability check success (fetches service index)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"offers": {"AmazonEC2": {}}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert pricing_client.is_available() is True
        mock_get.assert_called_once()

    @patch('thothctl.services.check.project.cost.pricing.aws_pricing_client.requests.get')
    def test_is_available_failure(self, mock_get, pricing_client):
        """Test API availability check failure (network error)"""
        import requests
        mock_get.side_effect = requests.Timeout("Connection timed out")

        assert pricing_client.is_available() is False

    @patch('thothctl.services.check.project.cost.pricing.aws_pricing_client.requests.get')
    def test_get_service_index_caches(self, mock_get, pricing_client):
        """Test that service index is cached after first fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"offers": {"AmazonEC2": {}}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # First call
        pricing_client._get_service_index()
        # Second call (should use cache)
        pricing_client._get_service_index()

        # Only one HTTP call made
        assert mock_get.call_count == 1

    def test_get_products_returns_empty(self, pricing_client):
        """Test get_products returns empty list (triggers offline estimates)"""
        filters = (('TERM_MATCH', 'instanceType', 't3.micro'),)
        products = pricing_client.get_products('AmazonEC2', filters)

        # Implementation returns empty to trigger offline estimates
        assert products == []

    def test_get_products_caching(self, pricing_client):
        """Test that get_products uses lru_cache"""
        assert hasattr(pricing_client.get_products, 'cache_info')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
