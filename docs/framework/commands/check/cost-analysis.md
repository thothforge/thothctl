# AWS Cost Analysis Check

The AWS Cost Analysis feature provides comprehensive cost estimation and optimization recommendations for your **Terraform** and **CloudFormation** infrastructure.

## Overview

The cost analysis check examines your `tfplan.json` files and CloudFormation templates and provides:
- **Real-time cost estimates** using AWS Pricing API with high confidence
- **Service-by-service breakdown** of monthly and annual costs
- **Action-based cost analysis** (create, update, delete operations)
- **Optimization recommendations** based on your infrastructure
- **Offline fallback estimates** when AWS API is unavailable

### Confidence Levels

ThothCTL provides confidence levels for cost estimates:

- **🟡 Medium Confidence**: Offline estimates from recent pricing data
  - Based on AWS pricing snapshots (updated regularly)
  - Covers all 14 supported services
  - Accurate within 5-10% of actual AWS pricing
  - Works without internet connectivity

**Note on Real-Time Pricing**: AWS's bulk pricing files are very large (100MB+ per service/region), making real-time parsing impractical for a CLI tool. ThothCTL uses carefully maintained offline estimates that are regularly updated to match AWS pricing.

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

**No AWS credentials or internet required!** ThothCTL uses offline pricing estimates that are regularly updated.

## Supported AWS Services

### Compute Services
- **EC2**: All instance types with accurate hourly/monthly costs
- **Lambda**: Function pricing based on memory, timeout, and execution estimates
- **EKS**: Cluster pricing ($0.10/hour), node groups and Fargate profiles
- **ECS**: Fargate pricing (vCPU + memory), EC2 launch type is free

### Storage Services
- **EBS**: All volume types (gp2, gp3, io1, io2, st1, sc1) with per-GB pricing
- **S3**: Bucket management costs with 100GB storage estimate

### Database Services
- **RDS**: All instance classes with engine-specific pricing (MySQL, PostgreSQL, Aurora, Oracle, SQL Server, MariaDB)
  - Single-AZ and Multi-AZ deployment options
  - Engine-specific pricing
- **DynamoDB**: Provisioned (RCU/WCU) and On-Demand capacity pricing

### Networking Services
- **ELB/ALB/NLB**: Application, Network, and Gateway Load Balancer pricing
- **VPC**: NAT Gateway, VPC Endpoints, VPN connections, Transit Gateway from AWS API
- **API Gateway**: REST, HTTP, and WebSocket API pricing from AWS API (per-request estimates)

### Security & Management (Real-Time Pricing ✅)
- **Secrets Manager**: Secret storage ($0.40/secret/month) from AWS API
- **CloudWatch**: Metrics, alarms, and log groups from AWS API

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

## JSON Output Format

The JSON report is saved to `Reports/cost-analysis/cost_analysis_<stack>_<timestamp>.json` with the following schema:

```json
{
  "summary": {
    "total_monthly_cost": 247.50,
    "total_annual_cost": 2970.00,
    "region": "us-east-1",
    "api_available": false,
    "plan_file": "path/to/tfplan.json"
  },
  "cost_by_service": {
    "EC2": 72.00,
    "RDS": 124.00,
    "ELB": 16.20
  },
  "cost_by_action": {
    "create": 235.50,
    "update": 12.00,
    "delete": 0.00
  },
  "resources": [
    {
      "address": "aws_instance.web_server",
      "type": "aws_instance",
      "service": "EC2",
      "region": "us-east-1",
      "action": "create",
      "hourly_cost": 0.0100,
      "monthly_cost": 72.00,
      "annual_cost": 864.00,
      "confidence": "medium",
      "details": {
        "instance_type": "t3.micro"
      }
    }
  ],
  "recommendations": [
    "💰 Consider Reserved Instances for 1-3 year commitments (up to 72% savings)"
  ],
  "warnings": [
    "No pricing data for aws_new_service.example"
  ]
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `summary.total_monthly_cost` | `float` | Estimated total monthly cost (USD). Creates and updates add cost; deletes subtract. |
| `summary.total_annual_cost` | `float` | `total_monthly_cost × 12` |
| `summary.region` | `string` | Default AWS region used for pricing |
| `summary.api_available` | `boolean` | Whether the AWS public pricing API was reachable |
| `summary.plan_file` | `string` | Path to the analyzed plan or template file |
| `cost_by_service` | `object` | Monthly cost (USD) grouped by AWS service name (e.g. `EC2`, `RDS`, `Lambda`) |
| `cost_by_action` | `object` | Monthly cost (USD) grouped by action: `create`, `update`, `delete` |
| `resources` | `array` | Per-resource cost details (see below) |
| `recommendations` | `array[string]` | Cost optimization suggestions based on detected resources and thresholds |
| `warnings` | `array[string]` | Resources that could not be priced |

### Resource Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `address` | `string` | Terraform resource address (e.g. `module.vpc.aws_nat_gateway.main`) or CloudFormation resource name |
| `type` | `string` | Terraform resource type (e.g. `aws_instance`, `aws_db_instance`) |
| `service` | `string` | AWS service name (e.g. `EC2`, `RDS`, `S3`, `Lambda`, `Bedrock`) |
| `region` | `string` | AWS region for this resource |
| `action` | `string` | One of: `create`, `update`, `delete`, `no-change` |
| `hourly_cost` | `float` | Estimated hourly cost (USD), rounded to 4 decimal places |
| `monthly_cost` | `float` | Estimated monthly cost (USD, 720 hours), rounded to 2 decimal places |
| `annual_cost` | `float` | Estimated annual cost (USD, 8760 hours), rounded to 2 decimal places |
| `confidence` | `string` | Estimate confidence: `high` (API pricing), `medium` (offline estimates), `low` (fallback) |
| `details` | `object` | Service-specific pricing parameters (e.g. `instance_type`, `engine`, `volume_type`) |

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

## Cost Governance with OPA Policies

In addition to cost estimation, you can enforce cost governance rules using OPA/Conftest policies in the `scan` command. This enables automated budget gates, instance type restrictions, and required cost tags in your CI/CD pipeline.

See [Cost Governance Policies with OPA](../scan/use_cases.md#cost-governance-policies-with-opa) for complete Rego policy examples.

```bash
# Combine cost analysis with cost policy enforcement
thothctl check iac -type cost-analysis --recursive
thothctl scan iac -t opa -o "mode=opa,decision=terraform/cost/allow" --enforcement hard
```

## Limitations

1. **Estimate Accuracy**: Costs are estimates based on resource configuration
2. **Usage Patterns**: Actual costs depend on real usage patterns
3. **Regional Variations**: Some services have region-specific pricing
4. **New Services**: Recently launched AWS services may not be supported immediately

## Troubleshooting

### AWS Pricing API Issues

**Problem**: Cost analysis shows "medium confidence" or offline estimates

**Solutions**:
1. **Check Internet Connectivity**: AWS Pricing API requires internet access
   ```bash
   curl -I https://pricing.us-east-1.amazonaws.com
   ```

2. **Verify AWS Credentials** (optional but recommended):
   ```bash
   aws sts get-caller-identity
   ```

3. **Check Logs**: Enable debug mode to see API errors
   ```bash
   thothctl --debug check iac -type cost-analysis
   ```

**Problem**: "API pricing failed" warnings in logs

**Common Causes**:
- Network connectivity issues
- AWS API rate limiting (rare)
- Unsupported region or service configuration
- Invalid resource configuration in Terraform

**Solution**: The tool automatically falls back to offline estimates. Check logs for specific error messages.

### CloudFormation Template Detection

**Problem**: YAML files not recognized as CloudFormation templates

**Solution**: Ensure templates contain one of these indicators:
- `AWSTemplateFormatVersion: '2010-09-09'`
- `Resources:` section
- AWS resource types (e.g., `AWS::EC2::Instance`)

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
    
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate cost using AWS Pricing API"""
        if not self.pricing_client.is_available():
            return self.get_offline_estimate(resource_change, region)
        
        try:
            filters = (
                ('TERM_MATCH', 'location', self._region_to_location(region)),
                # Add service-specific filters
            )
            products = self.pricing_client.get_products(
                self.get_service_code(), filters
            )
            if products:
                hourly_cost = self._extract_hourly_cost(products[0])
                return self._create_resource_cost(
                    resource_change, config_param, region, 
                    hourly_cost, 'high'  # high confidence for API pricing
                )
        except Exception as e:
            logger.warning(f"API pricing failed: {e}")
        
        return self.get_offline_estimate(resource_change, region)
    
    # Implement other required methods...
```
