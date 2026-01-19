"""EBS storage pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class EBSPricingProvider(BasePricingProvider):
    """EBS storage pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # Offline pricing estimates (monthly USD per GB)
        self.ebs_costs = {
            'gp2': 0.10,    # General Purpose SSD
            'gp3': 0.08,    # General Purpose SSD (gp3)
            'io1': 0.125,   # Provisioned IOPS SSD
            'io2': 0.125,   # Provisioned IOPS SSD (io2)
            'st1': 0.045,   # Throughput Optimized HDD
            'sc1': 0.025,   # Cold HDD
            'standard': 0.05 # Magnetic
        }
    
    def get_service_code(self) -> str:
        return 'AmazonEC2'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_ebs_volume']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate EBS volume cost using AWS Pricing API"""
        config = resource_change['change'].get('after', {})
        volume_type = config.get('type', 'gp2')
        size = config.get('size', 8)
        
        if not self.pricing_client.is_available():
            return self.get_offline_estimate(resource_change, region)
        
        try:
            filters = (
                ('TERM_MATCH', 'location', self._region_to_location(region)),
                ('TERM_MATCH', 'volumeApiName', volume_type),
                ('TERM_MATCH', 'productFamily', 'Storage')
            )
            
            products = self.pricing_client.get_products(
                self.get_service_code(), filters
            )
            
            if products:
                gb_month_cost = self._extract_hourly_cost(products[0])
                monthly_cost = size * gb_month_cost
                hourly_cost = monthly_cost / (24 * 30)
                
                return self._create_resource_cost(
                    resource_change, volume_type, region, 
                    hourly_cost, 'high'
                )
        except Exception as e:
            logger.warning(f"API pricing failed for EBS: {e}")
        
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for EBS"""
        config = resource_change['change'].get('after', {})
        volume_type = config.get('type', 'gp2')
        size = config.get('size', 8)  # GB
        
        cost_per_gb = self.ebs_costs.get(volume_type, 0.10)
        monthly_cost = size * cost_per_gb
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, f"{volume_type}-{size}GB", region, 
            hourly_cost, 'high'
        )
    
    def _create_resource_cost(self, resource_change: Dict, volume_config: str,
                            region: str, hourly_cost: float, 
                            confidence: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type='aws_ebs_volume',
            service_name='EBS',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'volume_config': volume_config},
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
