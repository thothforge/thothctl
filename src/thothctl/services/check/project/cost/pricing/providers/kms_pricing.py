"""KMS pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class KMSPricingProvider(BasePricingProvider):
    """KMS key pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # KMS pricing
        self.customer_managed_key_monthly = 1.0  # $1/month per key
        self.api_request_cost = 0.03 / 10000  # $0.03 per 10,000 requests
    
    def get_service_code(self) -> str:
        return 'awskms'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_kms_key', 'aws_kms_alias']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate KMS cost"""
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for KMS"""
        resource_type = resource_change['type']
        
        if resource_type == 'aws_kms_alias':
            # Aliases are free
            hourly_cost = 0.0
            note = 'KMS aliases are free'
        else:
            # aws_kms_key
            config = resource_change['change'].get('after', {})
            
            # Check if it's AWS managed or customer managed
            key_usage = config.get('key_usage', 'ENCRYPT_DECRYPT')
            
            # Customer managed keys: $1/month
            # AWS managed keys: Free
            monthly_cost = self.customer_managed_key_monthly
            hourly_cost = monthly_cost / (24 * 30)
            note = f'Customer managed key: ${monthly_cost}/month + API requests'
        
        return self._create_resource_cost(
            resource_change, resource_type, region, hourly_cost, 'high', note
        )
    
    def _create_resource_cost(self, resource_change: Dict, resource_type: str,
                            region: str, hourly_cost: float, 
                            confidence: str, note: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type=resource_type,
            service_name='KMS',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'note': note},
            confidence_level=confidence
        )
