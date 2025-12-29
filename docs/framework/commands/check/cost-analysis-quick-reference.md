# Cost Analysis Quick Reference

## Quick Start

```bash
# 1. For Terraform: Generate plan
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json

# 1. For CloudFormation: Ensure templates exist
# Templates: .yaml, .yml, .json with Resources section

# 2. Run cost analysis (supports both)
thothctl check iac -type cost-analysis

# 3. Recursive analysis
thothctl check iac --recursive -type cost-analysis
```

## Supported AWS Services (15+)

| Service | Resources | Pricing Model |
|---------|-----------|---------------|
| **EC2** | `aws_instance` | Hourly instance costs |
| **RDS** | `aws_db_instance` | Database instance pricing |
| **DynamoDB** | `aws_dynamodb_table`, `aws_dynamodb_global_table` | On-demand/provisioned capacity |
| **S3** | `aws_s3_bucket` | Storage management costs |
| **Lambda** | `aws_lambda_function` | Memory + execution time |
| **API Gateway** | `aws_api_gateway_*`, `aws_apigatewayv2_*` | Request-based pricing |
| **ELB** | `aws_lb`, `aws_alb`, `aws_elb` | Load balancer hourly |
| **VPC** | `aws_nat_gateway`, `aws_vpc_endpoint` | Networking components |
| **EBS** | `aws_ebs_volume` | Storage per GB/month |
| **CloudWatch** | `aws_cloudwatch_*` | Metrics and alarms |
| **EKS** | `aws_eks_cluster`, `aws_eks_node_group` | Cluster + node costs |
| **ECS** | `aws_ecs_*` | Container service costs |
| **Secrets Manager** | `aws_secretsmanager_*` | Secret storage costs |
| **Bedrock** | `aws_bedrock_*` | AI/ML model costs |
| **MSK** | `aws_msk_cluster` | Kafka broker + storage costs |

## Cost Breakdown Example

```
💰 Total Monthly Cost: $247.50
🏗️ By Service: EC2 ($72), RDS ($124), DynamoDB ($25), ELB ($16.20)
⚡ By Action: Create ($235.50), Update ($12.00)
```

## Optimization Recommendations

- **$100+**: Set up billing alerts
- **$500+**: Right-size instances  
- **$1000+**: Consider Reserved Instances
- **Bedrock**: Optimize model usage and token consumption
- **DynamoDB**: Choose On-Demand vs Provisioned based on usage patterns
- **API Gateway**: Use HTTP APIs instead of REST APIs for cost savings
- **MSK**: Right-size broker instances and optimize storage allocation
- **EKS**: Use Fargate Spot for cost savings

## Confidence Levels

- **High**: Real-time AWS API data
- **Medium**: Offline estimates
- **Low**: Fallback estimates

## Integration Examples

### GitHub Actions
```yaml
- name: Cost Analysis
  run: |
    terraform show -json tfplan > tfplan.json
    thothctl check iac -type cost-analysis
```

### GitLab CI
```yaml
cost-check:
  script:
    - terraform show -json tfplan > tfplan.json
    - thothctl check iac -type cost-analysis
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No files found | For Terraform: `terraform show -json tfplan > tfplan.json`<br>For CloudFormation: Ensure .yaml/.yml/.json templates exist |
| AWS API unavailable | Tool automatically uses offline estimates |
| Unsupported resource | Check warnings section in output |
