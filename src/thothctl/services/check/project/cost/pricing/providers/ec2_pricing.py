"""EC2 instance pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class EC2PricingProvider(BasePricingProvider):
    """EC2 instance pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # Offline pricing estimates (monthly USD)
        self.offline_estimates = {
            't3.nano': 3.8, 't3.micro': 7.6, 't3.small': 15.2,
            't3.medium': 30.4, 't3.large': 60.8, 't3.xlarge': 121.6,
            'm5.large': 70.1, 'm5.xlarge': 140.2, 'm5.2xlarge': 280.4,
            'c5.large': 62.6, 'c5.xlarge': 125.2, 'c5.2xlarge': 250.4
        }
    
    def get_service_code(self) -> str:
        return 'AmazonEC2'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_instance']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate EC2 instance cost using AWS API"""
        config = resource_change['change'].get('after', {})
        instance_type = config.get('instance_type', 't3.micro')
        
        if not self.pricing_client.is_available():
            return self.get_offline_estimate(resource_change, region)
        
        try:
            filters = (
                ('TERM_MATCH', 'instanceType', instance_type),
                ('TERM_MATCH', 'location', self._region_to_location(region)),
                ('TERM_MATCH', 'tenancy', 'Shared'),
                ('TERM_MATCH', 'operating-system', 'Linux'),
                ('TERM_MATCH', 'preInstalledSw', 'NA')
            )
            
            products = self.pricing_client.get_products(
                self.get_service_code(), filters
            )
            
            if products:
                hourly_cost = self._extract_hourly_cost(products[0])
                return self._create_resource_cost(
                    resource_change, instance_type, region, 
                    hourly_cost, 'high'
                )
        except Exception as e:
            logger.warning(f"API pricing failed for {instance_type}: {e}")
        
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate"""
        config = resource_change['change'].get('after', {})
        instance_type = config.get('instance_type', 't3.micro')
        
        monthly_cost = self.offline_estimates.get(instance_type, 7.6)
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, instance_type, region, 
            hourly_cost, 'medium'
        )
    
    def _extract_hourly_cost(self, product: Dict) -> float:
        """Extract hourly cost from AWS pricing product"""
        try:
            on_demand = product['terms']['OnDemand']
            price_dimensions = list(on_demand.values())[0]['priceDimensions']
            return float(list(price_dimensions.values())[0]['pricePerUnit']['USD'])
        except (KeyError, ValueError):
            return 0.0
    
    def _create_resource_cost(self, resource_change: Dict, instance_type: str,
                            region: str, hourly_cost: float, 
                            confidence: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type='aws_instance',
            service_name='EC2',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'instance_type': instance_type},
            confidence_level=confidence
        )
    
    def _region_to_location(self, region: str) -> str:
        """Convert AWS region to location name for pricing API"""
        region_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'Europe (Ireland)',
            'ap-southeast-1': 'Asia Pacific (Singapore)'
        }
        return region_map.get(region, 'US East (N. Virginia)')
