"""DynamoDB pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class DynamoDBPricingProvider(BasePricingProvider):
    """DynamoDB pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # DynamoDB pricing (monthly USD)
        self.on_demand_costs = {
            'write_request_units': 1.25,  # per million WRUs
            'read_request_units': 0.25,   # per million RRUs
            'storage': 0.25               # per GB per month
        }
        
        self.provisioned_costs = {
            'write_capacity_units': 0.47,  # per WCU per month
            'read_capacity_units': 0.09,   # per RCU per month
            'storage': 0.25                # per GB per month
        }
    
    def get_service_code(self) -> str:
        return 'AmazonDynamoDB'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_dynamodb_table', 'aws_dynamodb_global_table']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate DynamoDB cost"""
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for DynamoDB"""
        config = resource_change['change'].get('after', {})
        billing_mode = config.get('billing_mode', 'PAY_PER_REQUEST')
        
        if billing_mode == 'PROVISIONED':
            # Provisioned capacity mode
            read_capacity = config.get('read_capacity', 5)
            write_capacity = config.get('write_capacity', 5)
            
            monthly_cost = (
                read_capacity * self.provisioned_costs['read_capacity_units'] +
                write_capacity * self.provisioned_costs['write_capacity_units'] +
                1.0 * self.provisioned_costs['storage']  # Estimate 1GB storage
            )
            pricing_mode = f"provisioned_{read_capacity}RCU_{write_capacity}WCU"
        else:
            # On-demand mode (default)
            # Estimate: 1M reads, 100K writes per month, 1GB storage
            monthly_cost = (
                1.0 * self.on_demand_costs['read_request_units'] +
                0.1 * self.on_demand_costs['write_request_units'] +
                1.0 * self.on_demand_costs['storage']
            )
            pricing_mode = "on_demand"
        
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, pricing_mode, region, 
            hourly_cost, 'medium'
        )
    
    def _create_resource_cost(self, resource_change: Dict, pricing_mode: str,
                            region: str, hourly_cost: float, 
                            confidence: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type=resource_change['type'],
            service_name='DynamoDB',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'pricing_mode': pricing_mode},
            confidence_level=confidence
        )
