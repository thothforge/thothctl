"""Elastic IP pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class EIPPricingProvider(BasePricingProvider):
    """Elastic IP pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # EIP pricing: Free when attached to running instance, $0.005/hour when idle
        # Additional IPs: $0.005/hour per additional IP
        self.idle_eip_hourly = 0.005
    
    def get_service_code(self) -> str:
        return 'AmazonEC2'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_eip']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate EIP cost"""
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for EIP"""
        config = resource_change['change'].get('after', {})
        
        # Check if EIP is associated with an instance
        instance = config.get('instance')
        network_interface = config.get('network_interface')
        
        # If associated, cost is $0 (free when attached to running instance)
        # If not associated, assume idle cost
        if instance or network_interface:
            hourly_cost = 0.0
            note = 'Free when attached to running instance'
        else:
            hourly_cost = self.idle_eip_hourly
            note = 'Idle EIP charge applies'
        
        return self._create_resource_cost(
            resource_change, region, hourly_cost, 'high', note
        )
    
    def _create_resource_cost(self, resource_change: Dict, region: str,
                            hourly_cost: float, confidence: str, note: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type='aws_eip',
            service_name='EC2',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'note': note},
            confidence_level=confidence
        )
