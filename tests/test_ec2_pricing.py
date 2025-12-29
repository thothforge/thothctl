"""Unit tests for EC2 pricing provider."""

import pytest
from unittest.mock import Mock, patch
from thothctl.services.check.project.cost.pricing.providers.ec2_pricing import EC2PricingProvider
from thothctl.services.check.project.cost.models.cost_models import CostAction


class TestEC2PricingProvider:
    """Test EC2 pricing provider"""
    
    @pytest.fixture
    def mock_pricing_client(self):
        """Mock AWS pricing client"""
        client = Mock()
        client.is_available.return_value = False
        return client
    
    @pytest.fixture
    def ec2_provider(self, mock_pricing_client):
        """EC2 pricing provider instance"""
        return EC2PricingProvider(mock_pricing_client)
    
    def test_service_code(self, ec2_provider):
        """Test service code"""
        assert ec2_provider.get_service_code() == 'AmazonEC2'
    
    def test_supported_resources(self, ec2_provider):
        """Test supported resources"""
        resources = ec2_provider.get_supported_resources()
        assert 'aws_instance' in resources
    
    def test_offline_estimate(self, ec2_provider):
        """Test offline cost estimate"""
        resource_change = {
            'address': 'aws_instance.test',
            'type': 'aws_instance',
            'change': {
                'actions': ['create'],
                'after': {
                    'instance_type': 't3.micro'
                }
            }
        }
        
        cost = ec2_provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert cost is not None
        assert cost.resource_type == 'aws_instance'
        assert cost.service_name == 'EC2'
        assert cost.action == CostAction.CREATE
        assert cost.monthly_cost == 7.6  # t3.micro offline estimate
        assert cost.confidence_level == 'medium'
    
    def test_calculate_cost_api_unavailable(self, ec2_provider):
        """Test cost calculation when API is unavailable"""
        resource_change = {
            'address': 'aws_instance.test',
            'type': 'aws_instance',
            'change': {
                'actions': ['create'],
                'after': {
                    'instance_type': 't3.small'
                }
            }
        }
        
        cost = ec2_provider.calculate_cost(resource_change, 'us-east-1')
        
        assert cost is not None
        assert cost.monthly_cost == 15.2  # t3.small offline estimate
        assert cost.confidence_level == 'medium'
    
    def test_region_to_location_mapping(self, ec2_provider):
        """Test region to location name mapping"""
        assert ec2_provider._region_to_location('us-east-1') == 'US East (N. Virginia)'
        assert ec2_provider._region_to_location('us-west-2') == 'US West (Oregon)'
        assert ec2_provider._region_to_location('unknown-region') == 'US East (N. Virginia)'
