# AWS Cost Analysis Check

The AWS Cost Analysis feature provides comprehensive cost estimation and optimization recommendations for your **Terraform** and **CloudFormation** infrastructure.

## Overview

The cost analysis check examines your `tfplan.json` files and CloudFormation templates and provides:
- **Real-time cost estimates** using AWS Pricing API
- **Service-by-service breakdown** of monthly and annual costs
- **Action-based cost analysis** (create, update, delete operations)
- **Optimization recommendations** based on your infrastructure
- **Offline fallback estimates** when AWS API is unavailable

## Usage

```bash
# Basic cost analysis (supports both Terraform and CloudFormation)
thothctl check iac -type cost-analysis

# Recursive analysis across multiple directories
thothctl check iac --recursive -type cost-analysis

# With specific directory
thothctl check iac -type cost-analysis -d /path/to/infrastructure
```

## Prerequisites

1. **Terraform Plan Files**: Generate JSON plan files first
   ```bash
   terraform plan -out=tfplan
   terraform show -json tfplan > tfplan.json
   ```

2. **CloudFormation Templates**: Ensure template files are present
   ```bash
   # CloudFormation templates (.yaml, .yml, .json)
   # Must contain AWSTemplateFormatVersion or Resources section
   ```

3. **AWS Credentials** (optional): For real-time pricing
   - Configure AWS CLI or use IAM roles
   - Pricing API access (usually available by default)

## Supported AWS Services

### Compute Services
- **EC2**: All instance types with accurate hourly/monthly costs
- **Lambda**: Function pricing based on memory, timeout, and execution estimates
- **EKS**: Cluster, node groups, and Fargate profiles
- **ECS**: Container services with Fargate pricing

### Storage Services
- **EBS**: All volume types (gp2, gp3, io1, io2, st1, sc1)
- **S3**: Bucket management costs

### Database Services
- **RDS**: All instance classes with detailed pricing
- **DynamoDB**: On-demand and provisioned capacity pricing

### Networking Services
- **ELB/ALB/NLB**: Load balancer costs
- **VPC**: NAT Gateway, VPC Endpoints, VPN connections, Transit Gateway
- **API Gateway**: REST, HTTP, and WebSocket API pricing

### Security & Management
- **Secrets Manager**: Secret storage and API costs
- **CloudWatch**: Metrics, alarms, and log groups

### AI/ML Services
- **Bedrock**: Foundation models, knowledge bases, agents, custom models

### Streaming Services
- **MSK**: Managed Streaming for Apache Kafka clusters

## Sample Output

```
================================================================================
💰 AWS COST ANALYSIS
================================================================================

📊 Total Monthly Cost: $247.50
📅 Total Annual Cost: $2,970.00

🏗️ Cost by Service:
  • EC2: $72.00/month
  • RDS: $124.00/month
  • ELB: $16.20/month
  • EBS: $8.00/month
  • Bedrock: $25.00/month
  • Secrets Manager: $2.30/month

⚡ Cost by Action:
  • create: $235.50/month
  • update: $12.00/month
  • delete: $0.00/month

📋 Resource Details:
  • aws_instance.web_server
    Type: aws_instance | Cost: $72.00/month | Confidence: high
  • aws_db_instance.main_db
    Type: aws_db_instance | Cost: $124.00/month | Confidence: medium

💡 Recommendations:
  💰 Consider Reserved Instances for 1-3 year commitments
  📊 Review instance sizing - right-size resources
  🔍 Set up AWS Cost Explorer and billing alerts
  🤖 Optimize Bedrock model usage and consider batch processing
  🔐 Review secret rotation frequency and consolidate secrets where possible

📈 Analysis Info: Region: us-east-1 | API: ✅ Online
================================================================================
```

## Configuration

### Region Configuration
The analyzer uses the following region detection order:
1. Resource-specific region from Terraform configuration
2. Availability zone prefix (e.g., `us-east-1a` → `us-east-1`)
3. Default region (`us-east-1`)

### Confidence Levels
- **High**: Real-time AWS API pricing data
- **Medium**: Offline estimates based on current AWS pricing
- **Low**: Fallback estimates for unsupported resources

## Cost Optimization Recommendations

The analyzer provides intelligent recommendations based on your infrastructure:

### General Recommendations
- **$100+**: Set up Cost Explorer and billing alerts
- **$500+**: Review instance sizing and right-sizing
- **$1000+**: Consider Reserved Instances for long-term savings

### Service-Specific Recommendations
- **EC2**: Spot instances, Auto Scaling, Reserved Instances
- **RDS**: Reserved Instances, performance insights monitoring
- **S3**: Intelligent Tiering, lifecycle policies
- **EBS**: gp3 optimization, volume right-sizing
- **Bedrock**: Model optimization, batch processing, token monitoring
- **EKS/ECS**: Fargate Spot, cluster autoscaling

## Troubleshooting

### No tfplan.json Files or CloudFormation Templates Found
```bash
# For Terraform: Generate plan files first
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json

# For CloudFormation: Ensure templates are present
# Templates must be .yaml, .yml, or .json files
# Must contain AWSTemplateFormatVersion or Resources section

# Then run cost analysis
thothctl check iac -type cost-analysis
```

### AWS API Unavailable
The analyzer automatically falls back to offline estimates when:
- AWS credentials are not configured
- Pricing API is unavailable
- Network connectivity issues occur

### Unsupported Resources
Resources not yet supported will show in warnings:
```
⚠️ Warnings:
  • No pricing data for aws_new_service.example
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: Infrastructure Cost Analysis
on: [pull_request]

jobs:
  cost-analysis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
      - name: Terraform Plan
        run: |
          terraform init
          terraform plan -out=tfplan
          terraform show -json tfplan > tfplan.json
      - name: Install ThothCTL
        run: pip install thothctl
      - name: Cost Analysis
        run: thothctl check iac -type cost-analysis
```

### GitLab CI Example
```yaml
cost-analysis:
  stage: validate
  script:
    - terraform plan -out=tfplan
    - terraform show -json tfplan > tfplan.json
    - thothctl check iac -type cost-analysis
  artifacts:
    reports:
      junit: cost-analysis-report.xml
```

## Advanced Usage

### Custom Region Analysis
```bash
# Analyze costs for specific region
AWS_DEFAULT_REGION=eu-west-1 thothctl check iac -type cost-analysis
```

### Batch Analysis
```bash
# Analyze multiple Terraform directories
find . -name "tfplan.json" -execdir thothctl check iac -type cost-analysis \;
```

## API Reference

The cost analysis integrates with existing ThothCTL check command:

```bash
thothctl check iac [OPTIONS]

Options:
  -type, --check_type [tfplan|module|deps|blast-radius|cost-analysis]
                        Check type to perform (default: tfplan)
  --recursive           Search for tfplan files recursively
  -d, --code-directory PATH
                        Directory to analyze
```

## Limitations

1. **Estimate Accuracy**: Costs are estimates based on resource configuration
2. **Usage Patterns**: Actual costs depend on real usage patterns
3. **Regional Variations**: Some services have region-specific pricing
4. **New Services**: Recently launched AWS services may not be supported immediately

## Contributing

To add support for new AWS services:

1. Create a new pricing provider in `pricing/providers/`
2. Implement the `BasePricingProvider` interface
3. Add resource mappings to `CostAnalyzer._initialize_providers()`
4. Add unit tests for the new provider

Example:
```python
class NewServicePricingProvider(BasePricingProvider):
    def get_service_code(self) -> str:
        return 'AmazonNewService'
    
    def get_supported_resources(self) -> List[str]:
        return ['aws_new_service_resource']
    
    # Implement other required methods...
```
