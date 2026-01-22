"""Main cost analysis service."""

import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from .models.cost_models import CostAnalysis, ResourceCost
from .models.cloudformation_mapper import CloudFormationResourceMapper
from .pricing.aws_pricing_client import AWSPricingClient
from .pricing.providers.ec2_pricing import EC2PricingProvider
from .pricing.providers.rds_pricing import RDSPricingProvider
from .pricing.providers.s3_pricing import S3PricingProvider
from .pricing.providers.lambda_pricing import LambdaPricingProvider
from .pricing.providers.elb_pricing import ELBPricingProvider
from .pricing.providers.vpc_pricing import VPCPricingProvider
from .pricing.providers.ebs_pricing import EBSPricingProvider
from .pricing.providers.cloudwatch_pricing import CloudWatchPricingProvider
from .pricing.providers.eks_pricing import EKSPricingProvider
from .pricing.providers.ecs_pricing import ECSPricingProvider
from .pricing.providers.secrets_manager_pricing import SecretsManagerPricingProvider
from .pricing.providers.bedrock_pricing import BedrockPricingProvider
from .pricing.providers.dynamodb_pricing import DynamoDBPricingProvider
from .pricing.providers.apigateway_pricing import APIGatewayPricingProvider
from .pricing.providers.msk_pricing import MSKPricingProvider
from .pricing.providers.kms_pricing import KMSPricingProvider
from .pricing.providers.eip_pricing import EIPPricingProvider
from .pricing.providers.free_resources_pricing import FreeResourcesPricingProvider

logger = logging.getLogger(__name__)


class CostAnalyzer:
    """Main cost analysis service"""
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.pricing_client = AWSPricingClient(region)
        self.cf_mapper = CloudFormationResourceMapper()
        self._providers = self._initialize_providers()
    
    def _initialize_providers(self) -> Dict[str, Any]:
        """Initialize pricing providers"""
        providers = {}
        
        # EC2 and compute
        ec2_provider = EC2PricingProvider(self.pricing_client)
        for resource in ec2_provider.get_supported_resources():
            providers[resource] = ec2_provider
        
        # RDS
        rds_provider = RDSPricingProvider(self.pricing_client)
        for resource in rds_provider.get_supported_resources():
            providers[resource] = rds_provider
        
        # S3
        s3_provider = S3PricingProvider(self.pricing_client)
        for resource in s3_provider.get_supported_resources():
            providers[resource] = s3_provider
        
        # Lambda
        lambda_provider = LambdaPricingProvider(self.pricing_client)
        for resource in lambda_provider.get_supported_resources():
            providers[resource] = lambda_provider
        
        # ELB/ALB
        elb_provider = ELBPricingProvider(self.pricing_client)
        for resource in elb_provider.get_supported_resources():
            providers[resource] = elb_provider
        
        # VPC components
        vpc_provider = VPCPricingProvider(self.pricing_client)
        for resource in vpc_provider.get_supported_resources():
            providers[resource] = vpc_provider
        
        # EBS
        ebs_provider = EBSPricingProvider(self.pricing_client)
        for resource in ebs_provider.get_supported_resources():
            providers[resource] = ebs_provider
        
        # CloudWatch
        cw_provider = CloudWatchPricingProvider(self.pricing_client)
        for resource in cw_provider.get_supported_resources():
            providers[resource] = cw_provider
        
        # EKS
        eks_provider = EKSPricingProvider(self.pricing_client)
        for resource in eks_provider.get_supported_resources():
            providers[resource] = eks_provider
        
        # ECS
        ecs_provider = ECSPricingProvider(self.pricing_client)
        for resource in ecs_provider.get_supported_resources():
            providers[resource] = ecs_provider
        
        # Secrets Manager
        sm_provider = SecretsManagerPricingProvider(self.pricing_client)
        for resource in sm_provider.get_supported_resources():
            providers[resource] = sm_provider
        
        # Bedrock
        bedrock_provider = BedrockPricingProvider(self.pricing_client)
        for resource in bedrock_provider.get_supported_resources():
            providers[resource] = bedrock_provider
        
        # DynamoDB
        dynamodb_provider = DynamoDBPricingProvider(self.pricing_client)
        for resource in dynamodb_provider.get_supported_resources():
            providers[resource] = dynamodb_provider
        
        # API Gateway
        apigw_provider = APIGatewayPricingProvider(self.pricing_client)
        for resource in apigw_provider.get_supported_resources():
            providers[resource] = apigw_provider
        
        # MSK
        msk_provider = MSKPricingProvider(self.pricing_client)
        for resource in msk_provider.get_supported_resources():
            providers[resource] = msk_provider
        
        # KMS
        kms_provider = KMSPricingProvider(self.pricing_client)
        for resource in kms_provider.get_supported_resources():
            providers[resource] = kms_provider
        
        # EIP
        eip_provider = EIPPricingProvider(self.pricing_client)
        for resource in eip_provider.get_supported_resources():
            providers[resource] = eip_provider
        
        # Free resources (IAM, VPC components, etc.)
        free_provider = FreeResourcesPricingProvider(self.pricing_client)
        for resource in free_provider.get_supported_resources():
            providers[resource] = free_provider
        
        return providers
    
    def analyze_terraform_plan(self, plan_file: str) -> CostAnalysis:
        """Analyze costs from terraform plan file"""
        with open(plan_file, 'r') as f:
            plan_data = json.load(f)
        
        resource_costs = []
        warnings = []
        
        for change in plan_data.get('resource_changes', []):
            if change['change']['actions'] == ['no-op']:
                continue
            
            cost = self._calculate_resource_cost(change)
            if cost:
                resource_costs.append(cost)
            else:
                warnings.append(f"No pricing data for {change['address']}")
        
        return self._create_analysis(resource_costs, warnings, plan_file)
    
    def analyze_cloudformation_template(self, template_file: str) -> CostAnalysis:
        """Analyze costs from CloudFormation template"""
        with open(template_file, 'r') as f:
            if template_file.endswith('.yaml') or template_file.endswith('.yml'):
                import yaml
                template_data = yaml.safe_load(f)
            else:
                template_data = json.load(f)
        
        resource_costs = []
        warnings = []
        
        resources = template_data.get('Resources', {})
        for resource_name, resource_config in resources.items():
            resource_type = resource_config.get('Type')
            if not resource_type:
                continue
            
            # Convert CloudFormation resource to Terraform equivalent
            terraform_equivalent = self.cf_mapper.get_terraform_equivalent(resource_type)
            if not terraform_equivalent:
                warnings.append(f"Unsupported CloudFormation resource: {resource_type}")
                continue
            
            # Create a mock resource change for cost calculation
            mock_change = {
                'address': resource_name,
                'type': terraform_equivalent,
                'change': {
                    'actions': ['create'],
                    'after': resource_config.get('Properties', {})
                }
            }
            
            cost = self._calculate_resource_cost(mock_change)
            if cost:
                # Update resource address to show CloudFormation resource name
                cost.resource_address = f"{resource_name} ({resource_type})"
                resource_costs.append(cost)
            else:
                warnings.append(f"No pricing data for {resource_name} ({resource_type})")
        
        return self._create_analysis(resource_costs, warnings, template_file)
    
    def _calculate_resource_cost(self, resource_change: Dict) -> Optional[ResourceCost]:
        """Calculate cost for a single resource"""
        resource_type = resource_change['type']
        provider = self._providers.get(resource_type)
        
        if not provider:
            logger.debug(f"No provider for resource type: {resource_type}")
            return None
        
        region = self._extract_region(resource_change)
        return provider.calculate_cost(resource_change, region)
    
    def _extract_region(self, resource_change: Dict) -> str:
        """Extract region from resource configuration"""
        config = resource_change['change'].get('after', {})
        # Try various ways to get region
        region = (config.get('availability_zone', '')[:9] or 
                 config.get('region') or 
                 self.region)
        return region
    
    def _create_analysis(self, resource_costs: List[ResourceCost], 
                        warnings: List[str], plan_file: str) -> CostAnalysis:
        """Create comprehensive cost analysis"""
        total_monthly = sum(
            cost.monthly_cost for cost in resource_costs 
            if cost.action.value in ['create', 'update']
        ) - sum(
            cost.monthly_cost for cost in resource_costs 
            if cost.action.value == 'delete'
        )
        
        return CostAnalysis(
            total_monthly_cost=total_monthly,
            total_annual_cost=total_monthly * 12,
            resource_costs=resource_costs,
            cost_breakdown_by_service=self._breakdown_by_service(resource_costs),
            cost_breakdown_by_action=self._breakdown_by_action(resource_costs),
            recommendations=self._generate_recommendations(total_monthly, resource_costs),
            warnings=warnings,
            analysis_metadata={
                'plan_file': plan_file,
                'region': self.region,
                'api_available': self.pricing_client.is_available()
            }
        )
    
    def _breakdown_by_service(self, costs: List[ResourceCost]) -> Dict[str, float]:
        """Group costs by AWS service"""
        breakdown = {}
        for cost in costs:
            service = cost.service_name
            if service not in breakdown:
                breakdown[service] = 0
            breakdown[service] += cost.monthly_cost
        return breakdown
    
    def _breakdown_by_action(self, costs: List[ResourceCost]) -> Dict[str, float]:
        """Group costs by action type"""
        breakdown = {}
        for cost in costs:
            action = cost.action.value
            if action not in breakdown:
                breakdown[action] = 0
            breakdown[action] += cost.monthly_cost
        return breakdown
    
    def _generate_recommendations(self, total_cost: float, 
                                costs: List[ResourceCost]) -> List[str]:
        """Generate cost optimization recommendations based on actual resources"""
        recommendations = []
        
        # Always provide baseline recommendations
        if total_cost > 0:
            recommendations.append("💡 Review this cost estimate against your actual usage patterns")
            
        # General cost recommendations based on total
        if total_cost > 1000:
            recommendations.append("💰 Consider Reserved Instances or Savings Plans for 1-3 year commitments (up to 72% savings)")
        if total_cost > 500:
            recommendations.append("📊 Right-size resources based on actual utilization metrics")
        if total_cost > 100:
            recommendations.append("🔍 Set up AWS Cost Explorer, budgets, and billing alerts")
        elif total_cost > 10:
            recommendations.append("📈 Monitor costs monthly to identify trends and anomalies")
        
        # Service-specific recommendations
        service_costs = self._breakdown_by_service(costs)
        
        # EC2 recommendations
        if service_costs.get('EC2', 0) > 200:
            recommendations.append("🖥️ Consider Spot Instances for non-critical workloads")
            recommendations.append("⚡ Use Auto Scaling to optimize EC2 usage")
        
        # RDS recommendations
        if service_costs.get('RDS', 0) > 100:
            recommendations.append("🗄️ Consider RDS Reserved Instances for production databases")
            recommendations.append("📈 Monitor RDS performance insights for optimization")
        
        # S3 recommendations
        if service_costs.get('S3', 0) > 50:
            recommendations.append("📦 Use S3 Intelligent Tiering for automatic cost optimization")
            recommendations.append("🗂️ Review S3 lifecycle policies for older data")
        
        # Lambda recommendations
        lambda_cost = service_costs.get('Lambda', 0)
        if lambda_cost > 0:
            recommendations.append("⚠️ Lambda costs are estimated at 1,000 executions/month per function")
            recommendations.append("💡 Actual Lambda costs depend on invocation rate and execution duration")
        if lambda_cost > 20:
            recommendations.append("⚡ Optimize Lambda memory allocation and timeout settings")
            recommendations.append("📊 Review CloudWatch metrics for actual usage patterns")
        
        # EBS recommendations
        if service_costs.get('EBS', 0) > 100:
            recommendations.append("💾 Consider gp3 volumes instead of gp2 for better price/performance")
            recommendations.append("📊 Monitor EBS utilization and resize volumes accordingly")
        
        # VPC recommendations
        if service_costs.get('VPC', 0) > 50:
            recommendations.append("🌐 Review NAT Gateway usage - consider NAT instances for lower traffic")
        
        # EKS recommendations
        if service_costs.get('EKS', 0) > 100:
            recommendations.append("☸️ Use Fargate for serverless containers or Spot instances for node groups")
            recommendations.append("🔧 Optimize EKS cluster autoscaling and right-size node groups")
        
        # ECS recommendations
        if service_costs.get('ECS', 0) > 50:
            recommendations.append("🐳 Consider Fargate Spot for cost-effective container workloads")
        
        # Secrets Manager recommendations
        if service_costs.get('SecretsManager', 0) > 20:
            recommendations.append("🔐 Review secret rotation frequency and consolidate secrets where possible")
        
        # Bedrock recommendations
        if service_costs.get('Bedrock', 0) > 100:
            recommendations.append("🤖 Optimize Bedrock model usage and consider batch processing")
            recommendations.append("📊 Monitor token usage and choose cost-effective models (Haiku vs Sonnet)")
            recommendations.append("🎯 Use knowledge bases efficiently and optimize vector storage")
        
        # DynamoDB recommendations
        if service_costs.get('DynamoDB', 0) > 50:
            recommendations.append("🗄️ Consider DynamoDB On-Demand vs Provisioned based on usage patterns")
            recommendations.append("📈 Use DynamoDB auto-scaling for variable workloads")
            recommendations.append("🔍 Monitor read/write capacity utilization and adjust accordingly")
        
        # API Gateway recommendations
        if service_costs.get('API Gateway', 0) > 20:
            recommendations.append("🌐 Consider HTTP APIs instead of REST APIs for lower costs")
            recommendations.append("📊 Implement API caching to reduce backend calls")
            recommendations.append("🔧 Use request/response compression to reduce data transfer costs")
        
        # MSK recommendations
        if service_costs.get('MSK', 0) > 200:
            recommendations.append("📡 Right-size MSK broker instances based on throughput requirements")
            recommendations.append("💾 Optimize storage allocation per broker to avoid over-provisioning")
            recommendations.append("🔄 Consider MSK Serverless for variable workloads")
        
        # Multi-service recommendations based on resource counts
        ec2_count = len([c for c in costs if c.service_name == 'EC2'])
        lambda_count = len([c for c in costs if c.service_name == 'Lambda'])
        rds_count = len([c for c in costs if c.service_name == 'RDS'])
        
        if ec2_count > 5:
            recommendations.append("🏗️ Consider containerization with ECS/EKS for better resource utilization")
        
        if lambda_count > 10:
            recommendations.append("⚡ Consider consolidating Lambda functions to reduce cold starts and costs")
        
        if rds_count > 3:
            recommendations.append("🗄️ Evaluate database consolidation opportunities to reduce RDS instance count")
        
        # Always add general best practices if no specific recommendations
        if len(recommendations) == 0:
            recommendations.append("✅ Infrastructure costs look reasonable for current configuration")
            recommendations.append("📊 Continue monitoring usage patterns for optimization opportunities")
        
        return recommendations
    
    def generate_json_report(self, analysis: CostAnalysis, output_path: Path) -> None:
        """Generate JSON cost analysis report"""
        report_data = {
            'summary': {
                'total_monthly_cost': round(analysis.total_monthly_cost, 2),
                'total_annual_cost': round(analysis.total_annual_cost, 2),
                'region': analysis.analysis_metadata.get('region', 'us-east-1'),
                'api_available': analysis.analysis_metadata.get('api_available', False),
                'plan_file': analysis.analysis_metadata.get('plan_file', 'N/A')
            },
            'cost_by_service': {
                service: round(cost, 2) 
                for service, cost in analysis.cost_breakdown_by_service.items()
            },
            'cost_by_action': {
                action: round(cost, 2) 
                for action, cost in analysis.cost_breakdown_by_action.items()
            },
            'resources': [
                {
                    'address': cost.resource_address,
                    'type': cost.resource_type,
                    'service': cost.service_name,
                    'region': cost.region,
                    'action': cost.action.value,
                    'hourly_cost': round(cost.hourly_cost, 4),
                    'monthly_cost': round(cost.monthly_cost, 2),
                    'annual_cost': round(cost.annual_cost, 2),
                    'confidence': cost.confidence_level,
                    'details': cost.pricing_details
                }
                for cost in analysis.resource_costs
            ],
            'recommendations': analysis.recommendations,
            'warnings': analysis.warnings
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"JSON report saved to: {output_path}")
    
    def generate_html_report(self, analysis: CostAnalysis, output_path: Path) -> None:
        """Generate HTML cost analysis report"""
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AWS Cost Analysis Report</title>
    <style>
        :root {{
            --thoth-primary: #667eea;
            --thoth-secondary: #764ba2;
            --status-success: #10b981;
            --status-warning: #f59e0b;
            --status-error: #ef4444;
            --status-info: #3b82f6;
            --action-create: #06b6d4;
            --action-update: #f59e0b;
            --action-delete: #ef4444;
            --confidence-high: #10b981;
            --confidence-medium: #f59e0b;
            --confidence-low: #ef4444;
            
            /* Light theme (default) */
            --bg-body: #f5f7fa;
            --bg-primary: #ffffff;
            --bg-secondary: #f9fafb;
            --bg-tertiary: #f3f4f6;
            --text-primary: #111827;
            --text-secondary: #6b7280;
            --text-tertiary: #9ca3af;
            --border-light: #e5e7eb;
            --border-medium: #d1d5db;
        }}
        
        /* Dark theme */
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-body: #0f172a;
                --bg-primary: #1e293b;
                --bg-secondary: #334155;
                --bg-tertiary: #475569;
                --text-primary: #f1f5f9;
                --text-secondary: #cbd5e1;
                --border-light: #334155;
                --border-medium: #475569;
            }}
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-body);
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{ 
            max-width: 1600px; 
            margin: 0 auto; 
            background: var(--bg-primary);
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{ 
            background: linear-gradient(135deg, var(--thoth-primary) 0%, var(--thoth-secondary) 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header p {{ font-size: 1.1em; opacity: 0.9; }}
        .content {{ padding: 40px; }}
        .summary {{ 
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .summary-card {{ 
            background: linear-gradient(135deg, var(--thoth-primary) 0%, var(--thoth-secondary) 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .summary-card h3 {{ font-size: 0.9em; opacity: 0.9; margin-bottom: 10px; }}
        .summary-card .value {{ font-size: 2em; font-weight: bold; }}
        .section {{ margin-bottom: 40px; }}
        .section h2 {{ 
            color: var(--thoth-primary);
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--thoth-primary);
        }}
        table {{ 
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{ 
            background: var(--thoth-primary);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        td {{ 
            padding: 12px 15px;
            border-bottom: 1px solid var(--border-light);
            color: var(--text-primary);
        }}
        tr:hover {{ background: var(--bg-tertiary); }}
        .badge {{ 
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        .badge-high {{ background: var(--confidence-high); color: white; }}
        .badge-medium {{ background: var(--confidence-medium); color: white; }}
        .badge-low {{ background: var(--confidence-low); color: white; }}
        .badge-create {{ background: var(--action-create); color: white; }}
        .badge-update {{ background: var(--action-update); color: white; }}
        .badge-delete {{ background: var(--action-delete); color: white; }}
        .recommendations {{ 
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid var(--thoth-primary);
            color: var(--text-primary);
        }}
        .recommendations li {{ 
            margin: 10px 0;
            padding-left: 10px;
            color: var(--text-primary);
        }}
        .chart-container {{ 
            margin: 20px 0;
            padding: 20px;
            background: var(--bg-secondary);
            border-radius: 8px;
            color: var(--text-primary);
        }}
        .bar {{ 
            display: flex;
            align-items: center;
            margin: 10px 0;
        }}
        .bar-label {{ 
            width: 150px;
            font-weight: 600;
            color: var(--text-primary);
        }}
        .bar-fill {{ 
            height: 30px;
            background: linear-gradient(90deg, var(--thoth-primary) 0%, var(--thoth-secondary) 100%);
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            color: white;
            font-weight: 600;
            min-width: 60px;
        }}
        /* Table wrapper for horizontal scroll */
        .table-wrapper {{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin: 20px 0;
            background: var(--bg-primary);
        }}
        /* Responsive adjustments */
        @media (max-width: 1650px) {{
            .container {{ max-width: 95%; }}
        }}
        @media (max-width: 768px) {{
            body {{ padding: 10px; }}
            .container {{ max-width: 100%; border-radius: 8px; }}
            table {{ font-size: 0.85em; min-width: 600px; }}
            th, td {{ padding: 8px 10px; white-space: nowrap; }}
            .bar-label {{ width: 100px; font-size: 0.9em; }}
            .summary-card .value {{ font-size: 1.5em; }}
            code {{ font-size: 0.8em; }}
        }}
        @media print {{
            body {{ background: var(--bg-primary); padding: 0; }}
            .container {{ box-shadow: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💰 AWS Cost Analysis Report</h1>
            <p>Infrastructure Cost Estimation</p>
        </div>
        
        <div class="content">
            <div class="summary">
                <div class="summary-card">
                    <h3>📊 Monthly Cost</h3>
                    <div class="value">${analysis.total_monthly_cost:,.2f}</div>
                </div>
                <div class="summary-card">
                    <h3>📅 Annual Cost</h3>
                    <div class="value">${analysis.total_annual_cost:,.2f}</div>
                </div>
                <div class="summary-card">
                    <h3>🏗️ Resources</h3>
                    <div class="value">{len(analysis.resource_costs)}</div>
                </div>
                <div class="summary-card">
                    <h3>🌍 Region</h3>
                    <div class="value">{analysis.analysis_metadata.get('region', 'N/A')}</div>
                </div>
            </div>
            
            <div class="section">
                <h2>🏗️ Cost by Service</h2>
                <div class="chart-container">
                    {''.join(f'''
                    <div class="bar">
                        <div class="bar-label">{service}</div>
                        <div class="bar-fill" style="width: {max(min(cost / max(analysis.cost_breakdown_by_service.values()) * 100, 100), 15)}%">
                            ${cost:,.2f}/mo
                        </div>
                    </div>
                    ''' for service, cost in sorted(analysis.cost_breakdown_by_service.items(), key=lambda x: x[1], reverse=True))}
                </div>
            </div>
            
            <div class="section">
                <h2>⚡ Cost by Action</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Action</th>
                            <th>Monthly Cost</th>
                            <th>Annual Cost</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(f'''
                        <tr>
                            <td><span class="badge badge-{action}">{action.upper()}</span></td>
                            <td>${cost:,.2f}</td>
                            <td>${cost * 12:,.2f}</td>
                        </tr>
                        ''' for action, cost in analysis.cost_breakdown_by_action.items())}
                    </tbody>
                </table>
                </div>
            </div>
            
            <div class="section">
                <h2>📋 Resource Details</h2>
                <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Resource</th>
                            <th>Service</th>
                            <th>Action</th>
                            <th>Monthly Cost</th>
                            <th>Confidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(f'''
                        <tr>
                            <td data-label="Resource"><code>{cost.resource_address}</code></td>
                            <td data-label="Service">{cost.service_name}</td>
                            <td data-label="Action"><span class="badge badge-{cost.action.value}">{cost.action.value}</span></td>
                            <td data-label="Monthly Cost">${cost.monthly_cost:,.2f}</td>
                            <td data-label="Confidence"><span class="badge badge-{cost.confidence_level}">{cost.confidence_level}</span></td>
                        </tr>
                        ''' for cost in analysis.resource_costs)}
                    </tbody>
                </table>
                </div>
            </div>
            
            <div class="section">
                <h2>💡 Recommendations</h2>
                <div class="recommendations">
                    <ul>
                        {''.join(f'<li>{rec}</li>' for rec in analysis.recommendations)}
                    </ul>
                </div>
            </div>
            
            {'<div class="section"><h2>⚠️ Warnings</h2><div class="recommendations"><ul>' + ''.join(f'<li>{warning}</li>' for warning in analysis.warnings) + '</ul></div></div>' if analysis.warnings else ''}
            
            <div class="section" style="text-align: center; color: #666; font-size: 0.9em; margin-top: 40px;">
                <p>Generated by ThothCTL Cost Analysis</p>
                <p>API Status: {'✅ Online' if analysis.analysis_metadata.get('api_available') else '⚠️ Offline'}</p>
            </div>
        </div>
    </div>
</body>
</html>"""
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        logger.info(f"HTML report saved to: {output_path}")
