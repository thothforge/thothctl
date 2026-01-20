"""RDS instance pricing provider."""

import logging
from typing import Dict, Optional, Any, List
from ..base_pricing import BasePricingProvider
from ..aws_pricing_client import AWSPricingClient
from ...models.cost_models import ResourceCost, CostAction

logger = logging.getLogger(__name__)


class RDSPricingProvider(BasePricingProvider):
    """RDS instance pricing provider"""
    
    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client
        
        # Offline pricing estimates (monthly USD)
        self.offline_estimates = {
            # Standard RDS
            'db.t3.micro': 12.4, 'db.t3.small': 24.8, 'db.t3.medium': 49.6,
            'db.t3.large': 99.2, 'db.m5.large': 140.2, 'db.m5.xlarge': 280.4,
            'db.r5.large': 162.0, 'db.r5.xlarge': 324.0,
            # Aurora (Graviton)
            'db.t4g.micro': 14.6, 'db.t4g.small': 29.2, 'db.t4g.medium': 58.4,
            'db.t4g.large': 116.8, 'db.r6g.large': 158.4, 'db.r6g.xlarge': 316.8,
            # Aurora (x86)
            'db.t3.medium': 49.6, 'db.r5.large': 162.0, 'db.r5.xlarge': 324.0
        }
    
    def get_service_code(self) -> str:
        return 'AmazonRDS'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_db_instance', 'aws_rds_cluster_instance', 'aws_rds_cluster']
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate RDS instance cost using AWS Pricing API"""
        config = resource_change['change'].get('after', {})
        instance_class = config.get('instance_class', 'db.t3.micro')
        engine = config.get('engine', 'mysql')
        multi_az = config.get('multi_az', False)
        
        if not self.pricing_client.is_available():
            return self.get_offline_estimate(resource_change, region)
        
        try:
            # Map engine to AWS pricing engine name
            engine_map = {
                'mysql': 'MySQL',
                'postgres': 'PostgreSQL',
                'mariadb': 'MariaDB',
                'oracle-se2': 'Oracle',
                'oracle-ee': 'Oracle',
                'sqlserver-ex': 'SQL Server',
                'sqlserver-web': 'SQL Server',
                'sqlserver-se': 'SQL Server',
                'sqlserver-ee': 'SQL Server',
                'aurora-mysql': 'Aurora MySQL',
                'aurora-postgresql': 'Aurora PostgreSQL',
                'aurora': 'Aurora MySQL'
            }
            
            database_engine = engine_map.get(engine, 'MySQL')
            deployment_option = 'Multi-AZ' if multi_az else 'Single-AZ'
            
            filters = (
                ('TERM_MATCH', 'instanceType', instance_class),
                ('TERM_MATCH', 'location', self._region_to_location(region)),
                ('TERM_MATCH', 'databaseEngine', database_engine),
                ('TERM_MATCH', 'deploymentOption', deployment_option)
            )
            
            products = self.pricing_client.get_products(
                self.get_service_code(), filters
            )
            
            if products:
                hourly_cost = self._extract_hourly_cost(products[0])
                return self._create_resource_cost(
                    resource_change, instance_class, region, 
                    hourly_cost, 'high'
                )
        except Exception as e:
            logger.warning(f"API pricing failed for RDS {instance_class}: {e}")
        
        return self.get_offline_estimate(resource_change, region)
    
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline estimate"""
        resource_type = resource_change['type']
        config = resource_change['change'].get('after', {})
        
        # Aurora cluster itself has no cost (only instances do)
        if resource_type == 'aws_rds_cluster':
            return self._create_resource_cost(
                resource_change, 'cluster', region, 0.0, 'high'
            )
        
        instance_class = config.get('instance_class', 'db.t3.micro')
        
        monthly_cost = self.offline_estimates.get(instance_class, 12.4)
        hourly_cost = monthly_cost / (24 * 30)
        
        return self._create_resource_cost(
            resource_change, instance_class, region, 
            hourly_cost, 'medium'
        )
    
    def _create_resource_cost(self, resource_change: Dict, instance_class: str,
                            region: str, hourly_cost: float, 
                            confidence: str) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change['change']['actions']
        action = CostAction(actions[0] if actions else 'no-change')
        
        return ResourceCost(
            resource_address=resource_change['address'],
            resource_type='aws_db_instance',
            service_name='RDS',
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={'instance_class': instance_class},
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
