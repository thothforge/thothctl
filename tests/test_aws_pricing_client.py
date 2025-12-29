"""Unit tests for AWS Pricing Client."""

import pytest
from unittest.mock import Mock, patch
from thothctl.services.check.project.cost.pricing.aws_pricing_client import AWSPricingClient


class TestAWSPricingClient:
    """Test AWS Pricing API client"""
    
    @pytest.fixture
    def pricing_client(self):
        """Pricing client instance"""
        return AWSPricingClient(region='us-east-1')
    
    def test_initialization(self, pricing_client):
        """Test client initialization"""
        assert pricing_client.region == 'us-east-1'
        assert pricing_client._client is None
    
    @patch('boto3.client')
    def test_client_property_lazy_init(self, mock_boto_client, pricing_client):
        """Test lazy initialization of boto3 client"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Access client property
        client = pricing_client.client
        
        assert client == mock_client
        mock_boto_client.assert_called_once_with('pricing', region_name='us-east-1')
    
    @patch('boto3.client')
    def test_client_property_exception(self, mock_boto_client, pricing_client):
        """Test client initialization exception"""
        mock_boto_client.side_effect = Exception("AWS credentials not found")
        
        with pytest.raises(Exception):
            _ = pricing_client.client
    
    @patch('boto3.client')
    def test_get_products_success(self, mock_boto_client, pricing_client):
        """Test successful product retrieval"""
        mock_client = Mock()
        mock_client.get_products.return_value = {
            'PriceList': ['{"productFamily": "Compute Instance"}']
        }
        mock_boto_client.return_value = mock_client
        
        filters = (('TERM_MATCH', 'instanceType', 't3.micro'),)
        products = pricing_client.get_products('AmazonEC2', filters)
        
        assert len(products) == 1
        assert products[0]['productFamily'] == 'Compute Instance'
        mock_client.get_products.assert_called_once_with(
            ServiceCode='AmazonEC2',
            Filters=list(filters)
        )
    
    @patch('boto3.client')
    def test_get_products_exception(self, mock_boto_client, pricing_client):
        """Test product retrieval exception"""
        mock_client = Mock()
        mock_client.get_products.side_effect = Exception("API error")
        mock_boto_client.return_value = mock_client
        
        filters = (('TERM_MATCH', 'instanceType', 't3.micro'),)
        products = pricing_client.get_products('AmazonEC2', filters)
        
        assert products == []
    
    @patch('boto3.client')
    def test_is_available_success(self, mock_boto_client, pricing_client):
        """Test API availability check success"""
        mock_client = Mock()
        mock_client.describe_services.return_value = {}
        mock_boto_client.return_value = mock_client
        
        assert pricing_client.is_available() is True
        mock_client.describe_services.assert_called_once_with(MaxResults=1)
    
    @patch('boto3.client')
    def test_is_available_failure(self, mock_boto_client, pricing_client):
        """Test API availability check failure"""
        mock_client = Mock()
        mock_client.describe_services.side_effect = Exception("API unavailable")
        mock_boto_client.return_value = mock_client
        
        assert pricing_client.is_available() is False
    
    def test_get_products_caching(self, pricing_client):
        """Test that get_products uses caching"""
        # This test verifies the @lru_cache decorator is applied
        assert hasattr(pricing_client.get_products, '__wrapped__')
        assert hasattr(pricing_client.get_products, 'cache_info')
