"""RDS instance pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class RDSPricingProvider(BasePricingProvider):
    """RDS instance pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # Offline pricing estimates (monthly USD)
        self.offline_estimates = {
            'db.t3.micro': 12.4, 'db.t3.small': 24.8, 'db.t3.medium': 49.6,
            'db.t3.large': 99.2, 'db.m5.large': 140.2, 'db.m5.xlarge': 280.4,
            'db.r5.large': 162.0, 'db.r5.xlarge': 324.0
        }
    
    def get_service_code(self) -> str:
        return 'AmazonRDS'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_db_instance']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate RDS instance cost"""
        config = resource_change['change'].get('after', {})
        instance_class = config.get('instance_class', 'db.t3.micro')
        
        if not self.pricing_client.is_available():
            return self.get_offline_estimate(resource_change, region)
        
        # For now, use offline estimates (AWS RDS pricing API is more complex)
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate"""
        config = resource_change['change'].get('after', {})
        instance_class = config.get('instance_class', 'db.t3.micro')
        
        monthly_cost = self.offline_estimates.get(instance_class, 12.4)
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, instance_class, region, 
            hourly_cost, 'medium'
        )
    
    def _create_resource_cost(self, resource_change: Dict, instance_class: str,
                            region: str, hourly_cost: float, 
                            confidence: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type='aws_db_instance',
            service_name='RDS',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'instance_class': instance_class},
            confidence_level=confidence
        )
