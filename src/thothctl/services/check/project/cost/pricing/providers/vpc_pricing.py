"""VPC and networking pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class VPCPricingProvider(BasePricingProvider):
    """VPC and networking pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # Offline pricing estimates (monthly USD)
        self.vpc_costs = {
            'nat_gateway': 32.40,      # NAT Gateway
            'vpc_endpoint': 7.20,      # VPC Endpoint
            'vpn_connection': 36.50,   # VPN Connection
            'transit_gateway': 36.00   # Transit Gateway
        }
    
    def get_service_code(self) -> str:
        return 'AmazonVPC'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_nat_gateway', 'aws_vpc_endpoint', 'aws_vpn_connection', 'aws_ec2_transit_gateway']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate VPC component cost"""
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for VPC components"""
        resource_type = resource_change['type']
        
        # Map resource type to cost
        cost_map = {
            'aws_nat_gateway': self.vpc_costs['nat_gateway'],
            'aws_vpc_endpoint': self.vpc_costs['vpc_endpoint'],
            'aws_vpn_connection': self.vpc_costs['vpn_connection'],
            'aws_ec2_transit_gateway': self.vpc_costs['transit_gateway']
        }
        
        monthly_cost = cost_map.get(resource_type, 0.0)
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, resource_type, region, 
            hourly_cost, 'medium'
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
            service_name='VPC',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'component_type': component_type},
            confidence_level=confidence
        )
