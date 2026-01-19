"""EKS cluster pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class EKSPricingProvider(BasePricingProvider):
    """EKS cluster pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # EKS pricing
        self.cluster_cost = 72.00  # $0.10/hour = $72/month per cluster
        self.fargate_vcpu_cost = 0.04048  # per vCPU per hour
        self.fargate_memory_cost = 0.004445  # per GB per hour
    
    def get_service_code(self) -> str:
        return 'AmazonEKS'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_eks_cluster', 'aws_eks_node_group', 'aws_eks_fargate_profile']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate EKS cost with real-time pricing"""
        if not self.pricing_client.is_available():
            return self.get_offline_estimate(resource_change, region)
        
        try:
            resource_type = resource_change['type']
            
            # EKS cluster has fixed hourly rate
            if resource_type == 'aws_eks_cluster':
                filters = (
                    ('TERM_MATCH', 'location', self._region_to_location(region)),
                    ('TERM_MATCH', 'productFamily', 'Compute')
                )
                
                products = self.pricing_client.get_products(self.get_service_code(), filters)
                
                if products:
                    hourly_cost = self._extract_hourly_cost(products[0])
                    if hourly_cost == 0.0:
                        hourly_cost = 0.10  # Fixed $0.10/hour for EKS cluster
                    
                    return self._create_resource_cost(
                        resource_change, 'cluster', region, 
                        hourly_cost, 'high'
                    )
            else:
                # Node groups and Fargate profiles use offline estimates
                return self.get_offline_estimate(resource_change, region)
                
        except Exception as e:
            logger.warning(f"EKS API pricing failed: {e}")
        
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate for EKS"""
        resource_type = resource_change['type']
        config = resource_change['change'].get('after', {})
        
        if resource_type == 'aws_eks_cluster':
            monthly_cost = self.cluster_cost
            component_type = 'cluster'
        elif resource_type == 'aws_eks_node_group':
            # Node group cost depends on EC2 instances (estimated)
            monthly_cost = 150.0  # Estimated for typical node group
            component_type = 'node_group'
        elif resource_type == 'aws_eks_fargate_profile':
            # Fargate profile base cost (actual usage-based)
            monthly_cost = 50.0  # Estimated base cost
            component_type = 'fargate_profile'
        else:
            monthly_cost = 72.0
            component_type = 'cluster'
        
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
            service_name='EKS',
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
