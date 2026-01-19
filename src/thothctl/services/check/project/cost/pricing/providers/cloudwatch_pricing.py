"""CloudWatch pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class CloudWatchPricingProvider(BasePricingProvider):
    """CloudWatch pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # CloudWatch pricing
        self.metric_cost = 0.30  # $0.30 per metric per month
        self.alarm_cost = 0.10   # $0.10 per alarm per month
    
    def get_service_code(self) -> str:
        return 'AmazonCloudWatch'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_cloudwatch_metric_alarm', 'aws_cloudwatch_log_group']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate CloudWatch cost with real-time pricing"""
        if not self.pricing_client.is_available():
            return self.get_offline_estimate(resource_change, region)
        
        try:
            resource_type = resource_change['type']
            
            # Map resource type to CloudWatch group
            group_map = {
                'aws_cloudwatch_metric_alarm': 'Alarms',
                'aws_cloudwatch_log_group': 'Logs'
            }
            
            group = group_map.get(resource_type)
            if not group:
                return self.get_offline_estimate(resource_change, region)
            
            filters = (
                ('TERM_MATCH', 'location', self._region_to_location(region)),
                ('TERM_MATCH', 'group', group)
            )
            
            products = self.pricing_client.get_products(self.get_service_code(), filters)
            
            if products:
                # CloudWatch pricing is often per-unit, convert to monthly
                unit_cost = self._extract_hourly_cost(products[0])
                
                if resource_type == 'aws_cloudwatch_metric_alarm':
                    monthly_cost = self.alarm_cost  # Use fixed alarm cost
                else:
                    monthly_cost = 0.50  # Base log group cost
                
                hourly_cost = monthly_cost / (24 * 30)
                
                return self._create_resource_cost(
                    resource_change, resource_type, region, 
                    hourly_cost, 'high'
                )
        except Exception as e:
            logger.warning(f"CloudWatch API pricing failed: {e}")
        
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for CloudWatch"""
        resource_type = resource_change['type']
        
        if resource_type == 'aws_cloudwatch_metric_alarm':
            monthly_cost = self.alarm_cost
        elif resource_type == 'aws_cloudwatch_log_group':
            monthly_cost = 0.50  # Base cost for log group
        else:
            monthly_cost = 0.30
        
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, resource_type, region, 
            hourly_cost, 'medium'
        )
    
    def _create_resource_cost(self, resource_change: Dict, cw_type: str,
                            region: str, hourly_cost: float, 
                            confidence: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type=resource_change['type'],
            service_name='CloudWatch',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'cloudwatch_type': cw_type},
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
