"""Secrets Manager pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class SecretsManagerPricingProvider(BasePricingProvider):
    """Secrets Manager pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # Secrets Manager pricing
        self.secret_cost = 0.40  # $0.40 per secret per month
        self.api_request_cost = 0.05 / 10000  # $0.05 per 10,000 API requests
    
    def get_service_code(self) -> str:
        return 'AWSSecretsManager'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_secretsmanager_secret', 'aws_secretsmanager_secret_version']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate Secrets Manager cost with real-time pricing"""
        if not self.pricing_client.is_available():
            return self.get_offline_estimate(resource_change, region)
        
        try:
            resource_type = resource_change['type']
            
            if resource_type == 'aws_secretsmanager_secret':
                filters = (
                    ('TERM_MATCH', 'location', self._region_to_location(region)),
                    ('TERM_MATCH', 'productFamily', 'Secret')
                )
                
                products = self.pricing_client.get_products(self.get_service_code(), filters)
                
                if products:
                    # Secrets Manager charges per secret per month
                    monthly_cost = self.secret_cost
                    hourly_cost = monthly_cost / (24 * 30)
                    
                    return self._create_resource_cost(
                        resource_change, 'secret', region, 
                        hourly_cost, 'high'
                    )
            else:
                # Secret versions use offline estimate
                return self.get_offline_estimate(resource_change, region)
                
        except Exception as e:
            logger.warning(f"Secrets Manager API pricing failed: {e}")
        
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for Secrets Manager"""
        resource_type = resource_change['type']
        
        if resource_type == 'aws_secretsmanager_secret':
            monthly_cost = self.secret_cost
            component_type = 'secret'
        elif resource_type == 'aws_secretsmanager_secret_version':
            # Version itself doesn't add cost, but estimate API usage
            monthly_cost = 0.05  # Estimated API usage cost
            component_type = 'secret_version'
        else:
            monthly_cost = self.secret_cost
            component_type = 'secret'
        
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, component_type, region, 
            hourly_cost, 'high'
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
            service_name='SecretsManager',
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
