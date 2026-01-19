"""ELB/ALB pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class ELBPricingProvider(BasePricingProvider):
    """ELB/ALB pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # Offline pricing estimates (monthly USD)
        self.elb_costs = {
            'application': 16.20,  # ALB
            'network': 16.20,      # NLB
            'classic': 18.00       # Classic ELB
        }
    
    def get_service_code(self) -> str:
        return 'AWSELB'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_lb', 'aws_alb', 'aws_elb']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate ELB cost using AWS Pricing API"""
        config = resource_change['change'].get('after', {})
        load_balancer_type = config.get('load_balancer_type', 'application')
        
        if not self.pricing_client.is_available():
            return self.get_offline_estimate(resource_change, region)
        
        try:
            # Map LB type to product family
            product_family_map = {
                'application': 'Load Balancer-Application',
                'network': 'Load Balancer-Network',
                'gateway': 'Load Balancer-Gateway',
                'classic': 'Load Balancer'
            }
            
            product_family = product_family_map.get(load_balancer_type, 'Load Balancer-Application')
            
            filters = (
                ('TERM_MATCH', 'location', self._region_to_location(region)),
                ('TERM_MATCH', 'productFamily', product_family)
            )
            
            products = self.pricing_client.get_products(
                self.get_service_code(), filters
            )
            
            if products:
                hourly_cost = self._extract_hourly_cost(products[0])
                return self._create_resource_cost(
                    resource_change, load_balancer_type, region, 
                    hourly_cost, 'high'
                )
        except Exception as e:
            logger.warning(f"API pricing failed for ELB: {e}")
        
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for ELB"""
        config = resource_change['change'].get('after', {})
        load_balancer_type = config.get('load_balancer_type', 'application')
        
        monthly_cost = self.elb_costs.get(load_balancer_type, 16.20)
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, load_balancer_type, region, 
            hourly_cost, 'medium'
        )
    
    def _create_resource_cost(self, resource_change: Dict, lb_type: str,
                            region: str, hourly_cost: float, 
                            confidence: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type=resource_change['type'],
            service_name='ELB',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'load_balancer_type': lb_type},
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
