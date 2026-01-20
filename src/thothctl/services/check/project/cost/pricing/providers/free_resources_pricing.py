"""Free AWS resources pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class FreeResourcesPricingProvider(BasePricingProvider):
    """Pricing provider for AWS resources that are free or have no direct cost"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
    
    def get_service_code(self) -> str:
        return 'AWSFreeResources'
    
    def get_supported_resources(self) -> List[str]:
        return [
            # IAM resources (free)
            'aws_iam_role',
            'aws_iam_policy',
            'aws_iam_role_policy_attachment',
            'aws_iam_instance_profile',
            'aws_iam_user',
            'aws_iam_group',
            'aws_iam_access_key',
            
            # VPC networking (free)
            'aws_route_table',
            'aws_route',
            'aws_route_table_association',
            'aws_subnet',
            'aws_vpc',
            'aws_security_group',
            'aws_security_group_rule',
            'aws_network_acl',
            'aws_network_acl_rule',
            'aws_default_security_group',
            'aws_default_network_acl',
            'aws_vpc_ipv4_cidr_block_association',
            'aws_internet_gateway',
            
            # VPC Flow Logs (CloudWatch costs apply separately)
            'aws_flow_log',
            
            # Resource management (free)
            'aws_resourcegroups_group',
            
            # EBS settings (free)
            'aws_ebs_encryption_by_default',
            'aws_ebs_default_kms_key',
            
            # CloudWatch resources (log storage costs apply separately)
            'aws_cloudwatch_log_resource_policy',
        ]
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate cost for free resources (always $0)"""
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for free resources"""
        resource_type = resource_change['type']
        
        # Determine service name
        service_map = {
            'aws_iam_': 'IAM',
            'aws_route': 'VPC',
            'aws_subnet': 'VPC',
            'aws_vpc': 'VPC',
            'aws_security_group': 'VPC',
            'aws_network_acl': 'VPC',
            'aws_flow_log': 'VPC',
            'aws_internet_gateway': 'VPC',
            'aws_resourcegroups': 'Resource Groups',
            'aws_ebs_': 'EBS',
            'aws_cloudwatch': 'CloudWatch',
        }
        
        service_name = 'AWS'
        for prefix, service in service_map.items():
            if resource_type.startswith(prefix):
                service_name = service
                break
        
        return self._create_resource_cost(
            resource_change, resource_type, region, 
            0.0, 'high', service_name
        )
    
    def _create_resource_cost(self, resource_change: Dict, resource_type: str,
                            region: str, hourly_cost: float, 
                            confidence: str, service_name: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type=resource_type,
            service_name=service_name,
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'note': 'No direct cost for this resource type'},
            confidence_level=confidence
        )
