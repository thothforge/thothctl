"""Amazon Bedrock pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class BedrockPricingProvider(BasePricingProvider):
    """Amazon Bedrock pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # Bedrock model pricing (per 1K tokens - estimates)
        self.model_costs = {
            'claude-3-sonnet': {'input': 0.003, 'output': 0.015},
            'claude-3-haiku': {'input': 0.00025, 'output': 0.00125},
            'titan-text-express': {'input': 0.0008, 'output': 0.0016},
            'titan-embeddings': {'input': 0.0001, 'output': 0.0001},
            'cohere-command': {'input': 0.0015, 'output': 0.002},
            'ai21-j2-ultra': {'input': 0.0188, 'output': 0.0188}
        }
        
        # Knowledge base and agent costs
        self.kb_cost = 0.10  # per GB per month for vector storage
        self.agent_cost = 0.00  # Agents use underlying model costs
    
    def get_service_code(self) -> str:
        return 'AmazonBedrock'
    
    def get_supported_resources(self) -> List[str]:
        return [
            'aws_bedrock_model_invocation_logging_configuration',
            'aws_bedrock_custom_model',
            'aws_bedrock_provisioned_model_throughput',
            'aws_bedrock_knowledge_base',
            'aws_bedrock_agent',
            'aws_bedrock_agent_action_group',
            'aws_bedrock_data_source'
        ]
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate Bedrock cost"""
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for Bedrock"""
        resource_type = resource_change['type']
        config = resource_change['change'].get('after', {})
        
        if resource_type == 'aws_bedrock_provisioned_model_throughput':
            # Provisioned throughput - high cost
            monthly_cost = 2500.0  # Estimated for provisioned capacity
            component_type = 'provisioned_throughput'
        elif resource_type == 'aws_bedrock_knowledge_base':
            # Knowledge base storage cost
            monthly_cost = 10.0  # Estimated for 100GB storage
            component_type = 'knowledge_base'
        elif resource_type == 'aws_bedrock_agent':
            # Agent orchestration (uses model costs)
            monthly_cost = 50.0  # Estimated monthly usage
            component_type = 'agent'
        elif resource_type == 'aws_bedrock_custom_model':
            # Custom model training/hosting
            monthly_cost = 500.0  # Estimated training + hosting cost
            component_type = 'custom_model'
        elif resource_type == 'aws_bedrock_data_source':
            # Data source ingestion
            monthly_cost = 5.0  # Estimated ingestion cost
            component_type = 'data_source'
        else:
            # Other Bedrock resources (logging, etc.)
            monthly_cost = 1.0
            component_type = 'bedrock_service'
        
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, component_type, region, 
            hourly_cost, 'medium'
        )
    
    def _create_resource_cost(self, resource_change: Dict, component_type: str,
                            region: str, hourly_cost: float, 
                            confidence: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type=resource_change['type'],
            service_name='Bedrock',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'component_type': component_type},
            confidence_level=confidence
        )

    def _extract_hourly_cost(self, product: Dict) -> float:
        """Extract hourly cost from AWS pricing product"""
        try:
            on_demand = product['terms']['OnDemand']
            price_dimensions = list(on_demand.values())[0]['priceDimensions']
            return float(list(price_dimensions.values())[0]['pricePerUnit']['USD'])
        except (KeyError, ValueError):
            return 0.0
    
    def _region_to_location(self, region: str) -> str:
        """Convert AWS region to location name for pricing API"""
        region_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-east-2': 'US East (Ohio)',
            'us-west-1': 'US West (N. California)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'Europe (Ireland)',
            'eu-west-2': 'Europe (London)',
            'eu-central-1': 'Europe (Frankfurt)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            'ap-southeast-2': 'Asia Pacific (Sydney)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)'
        }
        return region_map.get(region, 'US East (N. Virginia)')
