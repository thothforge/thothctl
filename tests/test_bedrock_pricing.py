"""Unit tests for Bedrock pricing provider."""

import pytest
from unittest.mock import Mock
from thothctl.services.check.project.cost.pricing.providers.bedrock_pricing import BedrockPricingProvider
from thothctl.services.check.project.cost.models.cost_models import CostAction


class TestBedrockPricingProvider:
    """Test Bedrock pricing provider"""
    
    @pytest.fixture
    def mock_pricing_client(self):
        """Mock AWS pricing client"""
        client = Mock()
        client.is_available.return_value = False
        return client
    
    @pytest.fixture
    def bedrock_provider(self, mock_pricing_client):
        """Bedrock pricing provider instance"""
        return BedrockPricingProvider(mock_pricing_client)
    
    def test_service_code(self, bedrock_provider):
        """Test service code"""
        assert bedrock_provider.get_service_code() == 'AmazonBedrock'
    
    def test_supported_resources(self, bedrock_provider):
        """Test supported resources"""
        resources = bedrock_provider.get_supported_resources()
        expected_resources = [
            'aws_bedrock_model_invocation_logging_configuration',
            'aws_bedrock_custom_model',
            'aws_bedrock_provisioned_model_throughput',
            'aws_bedrock_knowledge_base',
            'aws_bedrock_agent',
            'aws_bedrock_agent_action_group',
            'aws_bedrock_data_source'
        ]
        
        for resource in expected_resources:
            assert resource in resources
    
    def test_provisioned_throughput_cost(self, bedrock_provider):
        """Test provisioned throughput cost estimation"""
        resource_change = {
            'address': 'aws_bedrock_provisioned_model_throughput.test',
            'type': 'aws_bedrock_provisioned_model_throughput',
            'change': {
                'actions': ['create'],
                'after': {}
            }
        }
        
        cost = bedrock_provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert cost is not None
        assert cost.service_name == 'Bedrock'
        assert cost.action == CostAction.CREATE
        assert cost.monthly_cost == 2500.0  # High cost for provisioned capacity
        assert cost.pricing_details['component_type'] == 'provisioned_throughput'
    
    def test_knowledge_base_cost(self, bedrock_provider):
        """Test knowledge base cost estimation"""
        resource_change = {
            'address': 'aws_bedrock_knowledge_base.test',
            'type': 'aws_bedrock_knowledge_base',
            'change': {
                'actions': ['create'],
                'after': {}
            }
        }
        
        cost = bedrock_provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert cost is not None
        assert cost.monthly_cost == 10.0
        assert cost.pricing_details['component_type'] == 'knowledge_base'
    
    def test_agent_cost(self, bedrock_provider):
        """Test agent cost estimation"""
        resource_change = {
            'address': 'aws_bedrock_agent.test',
            'type': 'aws_bedrock_agent',
            'change': {
                'actions': ['create'],
                'after': {}
            }
        }
        
        cost = bedrock_provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert cost is not None
        assert cost.monthly_cost == 50.0
        assert cost.pricing_details['component_type'] == 'agent'
    
    def test_custom_model_cost(self, bedrock_provider):
        """Test custom model cost estimation"""
        resource_change = {
            'address': 'aws_bedrock_custom_model.test',
            'type': 'aws_bedrock_custom_model',
            'change': {
                'actions': ['create'],
                'after': {}
            }
        }
        
        cost = bedrock_provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert cost is not None
        assert cost.monthly_cost == 500.0
        assert cost.pricing_details['component_type'] == 'custom_model'
