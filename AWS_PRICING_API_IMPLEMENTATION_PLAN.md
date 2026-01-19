# AWS Pricing API Implementation Plan

## Current Status

### ✅ Implemented (Real AWS API)
- **EC2** - Fully functional with real-time pricing

### ❌ Using Offline Estimates Only
All other services currently bypass AWS API and use hardcoded estimates:
- RDS/Aurora
- Lambda
- S3
- ELB/ALB
- VPC (NAT Gateway, VPC Endpoints)
- EBS
- CloudWatch (Metrics, Logs)
- EKS
- ECS
- Secrets Manager
- Bedrock
- DynamoDB
- API Gateway
- MSK

## Implementation Pattern

Each service needs to follow the EC2 pattern:

```python
def calculate_cost(self, resource_change: Dict[str, Any], 
                  region: str) -> Optional[ResourceCost]:
    """Calculate cost using AWS API"""
    config = resource_change['change'].get('after', {})
    
    # 1. Check API availability
    if not self.pricing_client.is_available():
        return self.get_offline_estimate(resource_change, region)
    
    try:
        # 2. Build service-specific filters
        filters = (
            ('TERM_MATCH', 'location', self._region_to_location(region)),
            # Add service-specific filters here
        )
        
        # 3. Query AWS Pricing API
        products = self.pricing_client.get_products(
            self.get_service_code(), filters
        )
        
        # 4. Extract pricing
        if products:
            hourly_cost = self._extract_hourly_cost(products[0])
            return self._create_resource_cost(
                resource_change, config_param, region, 
                hourly_cost, 'high'  # high confidence for API pricing
            )
    except Exception as e:
        logger.warning(f"API pricing failed: {e}")
    
    # 5. Fallback to offline estimates
    return self.get_offline_estimate(resource_change, region)
```

## Service-Specific Implementation Details

### 1. RDS/Aurora (`rds_pricing.py`)

**Priority:** HIGH (commonly used, complex pricing)

**AWS Pricing Dimensions:**
- `instanceType` - db.t3.micro, db.m5.large, etc.
- `databaseEngine` - MySQL, PostgreSQL, Aurora MySQL, Aurora PostgreSQL, Oracle, SQL Server, MariaDB
- `deploymentOption` - Single-AZ, Multi-AZ
- `licenseModel` - License included, BYOL (for Oracle/SQL Server)
- `location` - Region

**Terraform Config Mapping:**
```python
config = resource_change['change'].get('after', {})
instance_class = config.get('instance_class', 'db.t3.micro')
engine = config.get('engine', 'mysql')
multi_az = config.get('multi_az', False)
license_model = config.get('license_model', 'general-public-license')
```

**Engine Mapping:**
```python
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
```

**Filters:**
```python
filters = (
    ('TERM_MATCH', 'instanceType', instance_class),
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'databaseEngine', engine_map.get(engine, 'MySQL')),
    ('TERM_MATCH', 'deploymentOption', 'Multi-AZ' if multi_az else 'Single-AZ')
)
```

**Special Considerations:**
- Aurora pricing is per vCPU-hour, not per instance
- Storage is billed separately (not included in instance pricing)
- I/O operations are billed separately for Aurora

---

### 2. Lambda (`lambda_pricing.py`)

**Priority:** HIGH (serverless, usage-based)

**AWS Pricing Dimensions:**
- `group` - AWS-Lambda-Requests, AWS-Lambda-Duration
- `location` - Region

**Pricing Model:**
- **Requests:** $0.20 per 1M requests
- **Duration:** $0.00001667 per GB-second

**Terraform Config Mapping:**
```python
config = resource_change['change'].get('after', {})
memory_size = config.get('memory_size', 128)  # MB
timeout = config.get('timeout', 3)  # seconds
```

**Implementation Approach:**
```python
# Get request pricing
request_filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'group', 'AWS-Lambda-Requests')
)

# Get duration pricing
duration_filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'group', 'AWS-Lambda-Duration')
)

# Estimate based on typical usage
# Assumption: 1M requests/month, average duration
monthly_requests = 1000000
duration_seconds = timeout
gb_seconds = (memory_size / 1024) * duration_seconds * monthly_requests

monthly_cost = (monthly_requests * request_cost) + (gb_seconds * gb_second_cost)
```

**Special Considerations:**
- Free tier: 1M requests + 400,000 GB-seconds per month
- Pricing varies by architecture (x86 vs ARM/Graviton2)

---

### 3. S3 (`s3_pricing.py`)

**Priority:** HIGH (storage, highly variable)

**AWS Pricing Dimensions:**
- `storageClass` - Standard, Intelligent-Tiering, Standard-IA, One Zone-IA, Glacier, etc.
- `volumeType` - Standard, Intelligent-Tiering, etc.
- `location` - Region

**Terraform Config Mapping:**
```python
# S3 buckets don't specify size in Terraform
# Need to estimate or use default
storage_gb = 100  # Default estimate
```

**Filters:**
```python
filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'storageClass', 'General Purpose'),
    ('TERM_MATCH', 'volumeType', 'Standard')
)
```

**Special Considerations:**
- Storage is per GB-month
- Requests (PUT, GET, etc.) are billed separately
- Data transfer is billed separately
- Cannot determine actual storage size from Terraform

---

### 4. ELB/ALB (`elb_pricing.py`)

**Priority:** MEDIUM

**AWS Pricing Dimensions:**
- `productFamily` - Load Balancer, Load Balancer-Application, Load Balancer-Network
- `location` - Region

**Terraform Resources:**
- `aws_lb` (ALB/NLB)
- `aws_elb` (Classic LB)

**Filters:**
```python
lb_type = config.get('load_balancer_type', 'application')
product_family_map = {
    'application': 'Load Balancer-Application',
    'network': 'Load Balancer-Network',
    'classic': 'Load Balancer'
}

filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'productFamily', product_family_map.get(lb_type))
)
```

**Special Considerations:**
- ALB charges per hour + per LCU (Load Balancer Capacity Unit)
- NLB charges per hour + per NLCU
- LCU/NLCU based on traffic (cannot estimate from Terraform)

---

### 5. EBS (`ebs_pricing.py`)

**Priority:** MEDIUM

**AWS Pricing Dimensions:**
- `volumeApiName` - gp2, gp3, io1, io2, st1, sc1, standard
- `location` - Region

**Terraform Config Mapping:**
```python
config = resource_change['change'].get('after', {})
volume_type = config.get('type', 'gp2')
size_gb = config.get('size', 8)
iops = config.get('iops', 0)  # For io1/io2
```

**Filters:**
```python
filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'volumeApiName', volume_type)
)
```

**Special Considerations:**
- gp3 has separate pricing for storage, IOPS, and throughput
- io1/io2 charge for provisioned IOPS separately
- Snapshots are billed separately

---

### 6. VPC (`vpc_pricing.py`)

**Priority:** MEDIUM

**AWS Pricing Dimensions:**
- NAT Gateway: Per hour + per GB processed
- VPC Endpoints: Per hour + per GB processed
- `location` - Region

**Terraform Resources:**
- `aws_nat_gateway`
- `aws_vpc_endpoint`

**Filters:**
```python
# NAT Gateway
filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'productFamily', 'NAT Gateway')
)

# VPC Endpoint
filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'productFamily', 'VpcEndpoint')
)
```

**Special Considerations:**
- Data processing charges vary by volume (cannot estimate from Terraform)

---

### 7. CloudWatch (`cloudwatch_pricing.py`)

**Priority:** MEDIUM

**AWS Pricing Dimensions:**
- `group` - Metrics, Logs, Alarms, API Requests
- `location` - Region

**Terraform Resources:**
- `aws_cloudwatch_log_group`
- `aws_cloudwatch_metric_alarm`

**Filters:**
```python
# Logs
filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'group', 'Logs')
)

# Metrics
filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'group', 'Metrics')
)
```

**Special Considerations:**
- Logs: Per GB ingested + per GB stored
- Metrics: Per custom metric
- First 10 metrics and alarms are free

---

### 8. EKS (`eks_pricing.py`)

**Priority:** MEDIUM

**AWS Pricing Dimensions:**
- Cluster: $0.10 per hour per cluster
- Nodes: EC2 pricing (separate)
- `location` - Region

**Filters:**
```python
filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'productFamily', 'Compute')
)
```

**Special Considerations:**
- EKS cluster is flat $0.10/hour
- Worker nodes are billed as EC2 instances
- Fargate pods are billed separately

---

### 9. ECS (`ecs_pricing.py`)

**Priority:** LOW

**AWS Pricing:**
- ECS itself is free
- Pay for underlying resources (EC2 or Fargate)

**Implementation:**
- Return minimal cost for ECS service/task definition
- Actual cost comes from EC2 instances or Fargate

---

### 10. Secrets Manager (`secrets_manager_pricing.py`)

**Priority:** LOW

**AWS Pricing:**
- $0.40 per secret per month
- $0.05 per 10,000 API calls

**Filters:**
```python
filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'productFamily', 'Secret')
)
```

---

### 11. DynamoDB (`dynamodb_pricing.py`)

**Priority:** MEDIUM

**AWS Pricing Dimensions:**
- `group` - Provisioned IOPS, On-Demand
- `location` - Region

**Terraform Config Mapping:**
```python
billing_mode = config.get('billing_mode', 'PROVISIONED')
read_capacity = config.get('read_capacity', 5)
write_capacity = config.get('write_capacity', 5)
```

**Special Considerations:**
- On-Demand: Per request
- Provisioned: Per RCU/WCU hour
- Storage is billed separately

---

### 12. API Gateway (`apigateway_pricing.py`)

**Priority:** LOW

**AWS Pricing:**
- REST API: Per million requests
- HTTP API: Per million requests (cheaper)
- WebSocket API: Per million messages + connection minutes

**Filters:**
```python
filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'group', 'API Calls')
)
```

---

### 13. Bedrock (`bedrock_pricing.py`)

**Priority:** LOW (new service)

**AWS Pricing:**
- Per model
- Per input/output tokens or images

**Special Considerations:**
- Highly variable by model
- Cannot estimate without usage patterns

---

### 14. MSK (`msk_pricing.py`)

**Priority:** LOW

**AWS Pricing Dimensions:**
- Broker instance type
- Storage per GB-month
- `location` - Region

**Filters:**
```python
filters = (
    ('TERM_MATCH', 'location', self._region_to_location(region)),
    ('TERM_MATCH', 'instanceType', broker_instance_type)
)
```

---

## Required Helper Methods

All providers need these two methods:

```python
def _extract_hourly_cost(self, product: Dict) -> float:
    """Extract hourly cost from AWS pricing product"""
    try:
        terms = product.get('terms', {}).get('OnDemand', {})
        for term in terms.values():
            price_dimensions = term.get('priceDimensions', {})
            for dimension in price_dimensions.values():
                price_per_unit = dimension.get('pricePerUnit', {})
                return float(price_per_unit.get('USD', 0))
    except Exception as e:
        logger.warning(f"Failed to extract hourly cost: {e}")
    return 0.0

def _region_to_location(self, region: str) -> str:
    """Convert AWS region code to pricing API location name"""
    region_map = {
        'us-east-1': 'US East (N. Virginia)',
        'us-east-2': 'US East (Ohio)',
        'us-west-1': 'US West (N. California)',
        'us-west-2': 'US West (Oregon)',
        'eu-west-1': 'EU (Ireland)',
        'eu-west-2': 'EU (London)',
        'eu-west-3': 'EU (Paris)',
        'eu-central-1': 'EU (Frankfurt)',
        'ap-southeast-1': 'Asia Pacific (Singapore)',
        'ap-southeast-2': 'Asia Pacific (Sydney)',
        'ap-northeast-1': 'Asia Pacific (Tokyo)',
        'ap-northeast-2': 'Asia Pacific (Seoul)',
        'ap-south-1': 'Asia Pacific (Mumbai)',
        'sa-east-1': 'South America (Sao Paulo)',
        'ca-central-1': 'Canada (Central)'
    }
    return region_map.get(region, 'US East (N. Virginia)')
```

## Implementation Priority

### Phase 1 (Critical - Week 1)
1. **RDS/Aurora** - Complex but commonly used
2. **Lambda** - Serverless, high usage
3. **S3** - Storage, universal

### Phase 2 (Important - Week 2)
4. **ELB/ALB** - Load balancing
5. **EBS** - Block storage
6. **DynamoDB** - NoSQL database

### Phase 3 (Nice to Have - Week 3)
7. **VPC** - NAT Gateway, Endpoints
8. **CloudWatch** - Monitoring
9. **EKS** - Kubernetes

### Phase 4 (Low Priority - Week 4)
10. **ECS** - Container orchestration
11. **Secrets Manager** - Secrets storage
12. **API Gateway** - API management
13. **MSK** - Kafka
14. **Bedrock** - AI/ML

## Testing Strategy

For each service:

1. **Unit Tests:**
   - Mock AWS Pricing API responses
   - Test filter construction
   - Test cost extraction
   - Test fallback to offline estimates

2. **Integration Tests:**
   - Real AWS API calls (requires credentials)
   - Verify pricing accuracy
   - Test error handling

3. **Terraform Plan Tests:**
   - Create sample Terraform plans
   - Run cost analysis
   - Verify results match AWS Calculator

## Documentation Updates

After implementation:

1. Update `docs/framework/commands/check/cost-analysis.md`
2. Add supported services list
3. Document confidence levels (high for API, medium for offline)
4. Add troubleshooting section for API failures

## Success Criteria

- ✅ All services attempt AWS API before offline estimates
- ✅ Confidence level is 'high' for API pricing, 'medium' for offline
- ✅ Graceful fallback when API unavailable
- ✅ Comprehensive error logging
- ✅ Unit test coverage >80%
- ✅ Documentation updated
