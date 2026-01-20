"""MSK (Managed Streaming for Apache Kafka) pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class MSKPricingProvider(BasePricingProvider):
    """MSK pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # MSK pricing (monthly USD per broker)
        self.broker_costs = {
            'kafka.t3.small': 36.00,
            'kafka.m5.large': 146.00,
            'kafka.m5.xlarge': 292.00,
            'kafka.m5.2xlarge': 584.00,
            'kafka.m5.4xlarge': 1168.00,
            'kafka.m5.8xlarge': 2336.00,
            'kafka.m5.12xlarge': 3504.00,
            'kafka.m5.16xlarge': 4672.00,
            'kafka.m5.24xlarge': 7008.00
        }
        
        # Storage costs per GB per month
        self.storage_cost = 0.10  # $0.10 per GB per month
    
    def get_service_code(self) -> str:
        return 'AmazonMSK'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_msk_cluster', 'aws_msk_configuration']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate MSK cost"""
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for MSK"""
        resource_type = resource_change['type']
        config = resource_change['change'].get('after', {})
        
        if resource_type == 'aws_msk_cluster':
            # Get broker configuration
            broker_node_group_info = config.get('broker_node_group_info', [])
            
            # Handle both list and dict formats
            if isinstance(broker_node_group_info, list):
                broker_info = broker_node_group_info[0] if broker_node_group_info else {}
            else:
                broker_info = broker_node_group_info
            
            instance_type = broker_info.get('instance_type', 'kafka.m5.large')
            number_of_broker_nodes = config.get('number_of_broker_nodes', 3)
            
            # Calculate broker costs
            broker_cost_per_node = self.broker_costs.get(instance_type, 146.00)
            total_broker_cost = broker_cost_per_node * number_of_broker_nodes
            
            # Estimate storage costs
            storage_info = broker_info.get('storage_info', {})
            if isinstance(storage_info, list):
                storage_info = storage_info[0] if storage_info else {}
            
            ebs_storage_info = storage_info.get('ebs_storage_info', {})
            if isinstance(ebs_storage_info, list):
                ebs_storage_info = ebs_storage_info[0] if ebs_storage_info else {}
            
            storage_per_broker = ebs_storage_info.get('volume_size', 100)
            total_storage_cost = storage_per_broker * number_of_broker_nodes * self.storage_cost
            
            monthly_cost = total_broker_cost + total_storage_cost
            component_type = f"{instance_type}_{number_of_broker_nodes}nodes"
            
        elif resource_type == 'aws_msk_configuration':
            # Configuration itself has no cost
            monthly_cost = 0.0
            component_type = 'configuration'
        else:
            monthly_cost = 146.00  # Default estimate
            component_type = 'msk_cluster'
        
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, component_type, region, 
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
            service_name='MSK',
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
