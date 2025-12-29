"""API Gateway pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class APIGatewayPricingProvider(BasePricingProvider):
    """API Gateway pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # API Gateway pricing (monthly USD)
        self.rest_api_costs = {
            'requests': 3.50,  # per million requests
            'data_transfer': 0.09  # per GB
        }
        
        self.http_api_costs = {
            'requests': 1.00,  # per million requests (cheaper than REST)
            'data_transfer': 0.09  # per GB
        }
        
        self.websocket_costs = {
            'messages': 1.00,  # per million messages
            'connection_minutes': 0.25  # per million connection minutes
        }
    
    def get_service_code(self) -> str:
        return 'AmazonApiGateway'
    
    def get_supported_resources(self) -> List[str]:
        return [
            'aws_api_gateway_rest_api',
            'aws_api_gateway_deployment',
            'aws_apigatewayv2_api',
            'aws_apigatewayv2_stage'
        ]
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate API Gateway cost"""
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for API Gateway"""
        resource_type = resource_change['type']
        config = resource_change['change'].get('after', {})
        
        if resource_type in ['aws_api_gateway_rest_api', 'aws_api_gateway_deployment']:
            # REST API - estimate 100K requests per month
            monthly_cost = 0.1 * self.rest_api_costs['requests']  # 100K requests
            api_type = 'rest_api'
        elif resource_type in ['aws_apigatewayv2_api', 'aws_apigatewayv2_stage']:
            # HTTP API or WebSocket API
            protocol_type = config.get('protocol_type', 'HTTP')
            if protocol_type == 'WEBSOCKET':
                # WebSocket API - estimate 50K messages, 1000 connection minutes
                monthly_cost = (
                    0.05 * self.websocket_costs['messages'] +
                    0.001 * self.websocket_costs['connection_minutes']
                )
                api_type = 'websocket_api'
            else:
                # HTTP API - estimate 100K requests per month
                monthly_cost = 0.1 * self.http_api_costs['requests']
                api_type = 'http_api'
        else:
            monthly_cost = 0.35  # Default estimate
            api_type = 'api_gateway'
        
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, api_type, region, 
            hourly_cost, 'medium'
        )
    
    def _create_resource_cost(self, resource_change: Dict, api_type: str,
                            region: str, hourly_cost: float, 
                            confidence: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type=resource_change['type'],
            service_name='API Gateway',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'api_type': api_type},
            confidence_level=confidence
        )
