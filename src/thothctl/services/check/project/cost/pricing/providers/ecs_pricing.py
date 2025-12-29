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
        """Calculate ECS/Fargate cost"""
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
