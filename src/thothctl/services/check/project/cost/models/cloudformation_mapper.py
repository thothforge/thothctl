"""CloudFormation to AWS resource mapping."""

from typing import Dict, Optional


class CloudFormationResourceMapper:
    """Maps CloudFormation resource types to AWS services and Terraform equivalents"""
    
    def __init__(self):
        self.cf_to_terraform_mapping = {
            # Compute
            'AWS::EC2::Instance': 'aws_instance',
            'AWS::Lambda::Function': 'aws_lambda_function',
            'AWS::ECS::Cluster': 'aws_ecs_cluster',
            'AWS::ECS::Service': 'aws_ecs_service',
            'AWS::ECS::TaskDefinition': 'aws_ecs_task_definition',
            'AWS::EKS::Cluster': 'aws_eks_cluster',
            'AWS::EKS::Nodegroup': 'aws_eks_node_group',
            
            # Storage
            'AWS::S3::Bucket': 'aws_s3_bucket',
            'AWS::EC2::Volume': 'aws_ebs_volume',
            
            # Database
            'AWS::RDS::DBInstance': 'aws_db_instance',
            'AWS::DynamoDB::Table': 'aws_dynamodb_table',
            'AWS::DynamoDB::GlobalTable': 'aws_dynamodb_global_table',
            
            # Networking
            'AWS::ElasticLoadBalancingV2::LoadBalancer': 'aws_lb',
            'AWS::ElasticLoadBalancing::LoadBalancer': 'aws_elb',
            'AWS::EC2::NatGateway': 'aws_nat_gateway',
            'AWS::EC2::VPCEndpoint': 'aws_vpc_endpoint',
            'AWS::EC2::VPNConnection': 'aws_vpn_connection',
            'AWS::EC2::TransitGateway': 'aws_ec2_transit_gateway',
            
            # API Gateway
            'AWS::ApiGateway::RestApi': 'aws_api_gateway_rest_api',
            'AWS::ApiGateway::Deployment': 'aws_api_gateway_deployment',
            'AWS::ApiGatewayV2::Api': 'aws_apigatewayv2_api',
            'AWS::ApiGatewayV2::Stage': 'aws_apigatewayv2_stage',
            
            # Monitoring
            'AWS::CloudWatch::Alarm': 'aws_cloudwatch_metric_alarm',
            'AWS::Logs::LogGroup': 'aws_cloudwatch_log_group',
            
            # Security
            'AWS::SecretsManager::Secret': 'aws_secretsmanager_secret',
            
            # AI/ML
            'AWS::Bedrock::Agent': 'aws_bedrock_agent',
            'AWS::Bedrock::KnowledgeBase': 'aws_bedrock_knowledge_base',
            
            # Streaming
            'AWS::MSK::Cluster': 'aws_msk_cluster',
        }
    
    def get_terraform_equivalent(self, cf_resource_type: str) -> Optional[str]:
        """Get Terraform resource type equivalent for CloudFormation resource"""
        return self.cf_to_terraform_mapping.get(cf_resource_type)
    
    def is_supported(self, cf_resource_type: str) -> bool:
        """Check if CloudFormation resource type is supported for cost analysis"""
        return cf_resource_type in self.cf_to_terraform_mapping
