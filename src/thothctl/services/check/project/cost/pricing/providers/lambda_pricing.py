"""Lambda function pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class LambdaPricingProvider(BasePricingProvider):
    """Lambda function pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # Lambda pricing (per GB-second and per request)
        self.gb_second_cost = 0.0000166667  # $0.0000166667 per GB-second
        self.request_cost = 0.0000002  # $0.0000002 per request
    
    def get_service_code(self) -> str:
        return 'AWSLambda'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_lambda_function']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate Lambda function cost"""
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for Lambda"""
        config = resource_change['change'].get('after', {})
        memory_size = config.get('memory_size', 128)  # MB
        timeout = config.get('timeout', 3)  # seconds
        
        # Estimate: 1000 executions per month
        executions_per_month = 1000
        gb_seconds = (memory_size / 1024) * timeout * executions_per_month
        
        monthly_cost = (gb_seconds * self.gb_second_cost) + (executions_per_month * self.request_cost)
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, f"{memory_size}MB", region, 
            hourly_cost, 'medium'
        )
    
    def _create_resource_cost(self, resource_change: Dict, memory_config: str,
                            region: str, hourly_cost: float, 
                            confidence: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type='aws_lambda_function',
            service_name='Lambda',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'memory_config': memory_config},
            confidence_level=confidence
        )
