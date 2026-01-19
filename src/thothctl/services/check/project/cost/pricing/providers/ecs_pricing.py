"""ECS and Fargate pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class ECSPricingProvider(BasePricingProvider):
    """ECS and Fargate pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # Fargate pricing (per hour)
        self.fargate_vcpu_cost = 0.04048  # per vCPU per hour
        self.fargate_memory_cost = 0.004445  # per GB per hour
        
        # ECS EC2 has no additional charges beyond EC2 instances
    
    def get_service_code(self) -> str:
        return 'AmazonECS'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_ecs_cluster', 'aws_ecs_service', 'aws_ecs_task_definition']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate ECS/Fargate cost with real-time pricing"""
        if not self.pricing_client.is_available():
            return self.get_offline_estimate(resource_change, region)
        
        try:
            resource_type = resource_change['type']
            config = resource_change['change'].get('after', {})
            
            # Only Fargate has pricing, ECS on EC2 is free
            if resource_type == 'aws_ecs_service':
                launch_type = config.get('launch_type', 'EC2')
                
                if launch_type == 'FARGATE':
                    filters = (
                        ('TERM_MATCH', 'location', self._region_to_location(region)),
                        ('TERM_MATCH', 'productFamily', 'Compute')
                    )
                    
                    products = self.pricing_client.get_products(self.get_service_code(), filters)
                    
                    if products:
                        # Fargate pricing: estimate 0.25 vCPU, 0.5 GB
                        vcpu_cost = 0.25 * self.fargate_vcpu_cost * 24 * 30
                        memory_cost = 0.5 * self.fargate_memory_cost * 24 * 30
                        monthly_cost = vcpu_cost + memory_cost
                        hourly_cost = monthly_cost / (24 * 30)
                        
                        return self._create_resource_cost(
                            resource_change, 'service_fargate', region, 
                            hourly_cost, 'high'
                        )
            
            # ECS cluster and task definitions are free
            return self.get_offline_estimate(resource_change, region)
            
        except Exception as e:
            logger.warning(f"ECS API pricing failed: {e}")
        
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for ECS/Fargate"""
        resource_type = resource_change['type']
        config = resource_change['change'].get('after', {})
        
        if resource_type == 'aws_ecs_cluster':
            # ECS cluster itself is free
            monthly_cost = 0.0
            component_type = 'cluster'
        elif resource_type == 'aws_ecs_service':
            # Service cost depends on launch type
            launch_type = config.get('launch_type', 'EC2')
            if launch_type == 'FARGATE':
                # Estimate: 0.25 vCPU, 0.5 GB memory, running 24/7
                vcpu_cost = 0.25 * self.fargate_vcpu_cost * 24 * 30
                memory_cost = 0.5 * self.fargate_memory_cost * 24 * 30
                monthly_cost = vcpu_cost + memory_cost
            else:
                monthly_cost = 0.0  # EC2 launch type has no additional ECS charges
            component_type = f'service_{launch_type.lower()}'
        elif resource_type == 'aws_ecs_task_definition':
            # Task definition itself is free
            monthly_cost = 0.0
            component_type = 'task_definition'
        else:
            monthly_cost = 0.0
            component_type = 'ecs_component'
        
        hourly_cost = monthly_cost / (24 * 30) if monthly_cost > 0 else 0.0
        
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
            service_name='ECS',
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
