# Scan Command Use Cases

The `thothctl scan` command is designed to support various security scanning use cases for DevSecOps teams and developers. This page outlines common use cases and how to implement them using ThothCTL.

## Pre-commit Security Checks

Run quick security checks before committing code to catch issues early in the development process.

```bash
# Create a pre-commit hook script
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
echo "Running security scan..."
thothctl scan iac -t checkov -t opa --enforcement hard
if [ $? -ne 0 ]; then
  echo "Security issues found. Please fix them before committing."
  exit 1
fi
EOF
chmod +x .git/hooks/pre-commit
```

## CI/CD Pipeline Integration

Integrate security scanning into your CI/CD pipeline with hard enforcement to gate deployments.

### GitHub Actions

```yaml
name: Security Scan

on:
  pull_request:
    branches: [ main ]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install ThothCTL
        run: pip install thothctl

      - name: Install Conftest
        run: |
          LATEST=$(curl -s https://api.github.com/repos/open-policy-agent/conftest/releases/latest | grep tag_name | cut -d '"' -f 4 | sed 's/v//')
          curl -L -o /tmp/conftest.tar.gz https://github.com/open-policy-agent/conftest/releases/download/v${LATEST}/conftest_${LATEST}_Linux_x86_64.tar.gz
          tar xzf /tmp/conftest.tar.gz -C /usr/local/bin conftest

      - name: Run Security Scan
        run: thothctl scan iac -t checkov -t opa --enforcement hard --post-to-pr --reports-dir ./reports
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Upload Scan Results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: security-scan-results
          path: ./reports
```

### GitLab CI

```yaml
stages:
  - test

security-scan:
  stage: test
  image: python:3.10
  script:
    - pip install thothctl
    - thothctl scan iac -t checkov -t trivy --enforcement hard --reports-dir ./reports
  artifacts:
    paths:
      - ./reports
```

### Azure Pipelines

```yaml
- script: |
    pip install thothctl
    thothctl scan iac -t checkov -t opa --enforcement hard --post-to-pr
  displayName: 'Security Scan'
  env:
    AZDO_PERSONAL_ACCESS_TOKEN: $(System.AccessToken)
```

## Custom Policy Enforcement with OPA

Use OPA/Conftest to enforce organization-specific policies written in Rego.

### Static HCL Analysis (Conftest Mode)

Create a `policy/` directory with Rego rules that evaluate `.tf` files directly:

```bash
mkdir -p policy
```

```rego
# policy/s3.rego
package main

deny contains msg if {
    some name, bucket in input.resource.aws_s3_bucket
    not bucket.server_side_encryption_configuration
    msg := sprintf("S3 bucket '%s' must have encryption enabled", [name])
}

warn contains msg if {
    some name, bucket in input.resource.aws_s3_bucket
    not bucket.tags
    msg := sprintf("S3 bucket '%s' should have tags", [name])
}
```

```bash
# Run the scan
thothctl scan iac -t opa --enforcement hard
```

### Plan-Based Evaluation (OPA Mode)

For policies that need to inspect planned changes:

```bash
# Generate plan
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json

# Evaluate with OPA
thothctl scan iac -t opa -o "mode=opa,decision=terraform/analysis/authz" --enforcement hard
```

### Combining Built-in and Custom Rules

Use Checkov for built-in best practices and OPA for custom organizational policies:

```bash
thothctl scan iac -t checkov -t opa --enforcement hard
```

## Cost Governance Policies with OPA

Use OPA/Conftest to enforce cost governance rules on your infrastructure. These policies work with both Conftest mode (static `.tf` analysis) and OPA mode (plan-based `tfplan.json` evaluation).

### Static Cost Policies (Conftest Mode)

These policies evaluate `.tf` files directly — no Terraform plan required.

#### Deny Expensive Instance Types

```rego
# policy/cost_instance_types.rego
package main

# Blocked instance families — too expensive for non-production
blocked_families := {"p4d", "p5", "x2idn", "u-"}

deny contains msg if {
    some name, instance in input.resource.aws_instance
    family := split(instance.instance_type, ".")[0]
    family in blocked_families
    msg := sprintf("EC2 instance '%s' uses expensive family '%s'. Use a smaller instance type or request an exception.", [name, family])
}

# Warn on large instances that may be over-provisioned
warn contains msg if {
    some name, instance in input.resource.aws_instance
    endswith(instance.instance_type, ".metal")
    msg := sprintf("EC2 instance '%s' uses bare metal (%s). Verify this is required.", [name, instance.instance_type])
}
```

#### Enforce RDS Cost Controls

```rego
# policy/cost_rds.rego
package main

deny contains msg if {
    some name, db in input.resource.aws_db_instance
    db.multi_az == true
    not db.tags.Environment == "production"
    msg := sprintf("RDS instance '%s' has Multi-AZ enabled in non-production. Remove multi_az or set Environment=production tag.", [name])
}

deny contains msg if {
    some name, db in input.resource.aws_db_instance
    db.allocated_storage > 500
    msg := sprintf("RDS instance '%s' requests %dGB storage. Max allowed without approval is 500GB.", [name, db.allocated_storage])
}
```

#### Require Cost Tags

```rego
# policy/cost_tags.rego
package main

required_tags := {"CostCenter", "Team", "Environment"}

deny contains msg if {
    some name, instance in input.resource.aws_instance
    missing := required_tags - {key | instance.tags[key]}
    count(missing) > 0
    msg := sprintf("EC2 instance '%s' is missing required cost tags: %v", [name, missing])
}

deny contains msg if {
    some name, db in input.resource.aws_db_instance
    missing := required_tags - {key | db.tags[key]}
    count(missing) > 0
    msg := sprintf("RDS instance '%s' is missing required cost tags: %v", [name, missing])
}
```

#### Enforce S3 Lifecycle Policies

```rego
# policy/cost_s3.rego
package main

warn contains msg if {
    some name, bucket in input.resource.aws_s3_bucket
    not input.resource.aws_s3_bucket_lifecycle_configuration
    msg := sprintf("S3 bucket '%s' has no lifecycle configuration. Add lifecycle rules to control storage costs.", [name])
}

deny contains msg if {
    some name, bucket in input.resource.aws_s3_bucket
    bucket.acl == "public-read"
    msg := sprintf("S3 bucket '%s' is public. Public buckets can incur unexpected data transfer costs.", [name])
}
```

Run static cost policies:

```bash
thothctl scan iac -t opa -o "policy_dir=policy" --enforcement hard
```

### Plan-Based Cost Policies (OPA Mode)

These policies evaluate `tfplan.json` for deeper cost analysis based on planned changes.

#### Budget Gate — Block Deployments Over Threshold

```rego
# policy/cost_budget.rego
package terraform.cost

import input as tfplan

# Monthly budget limit in USD
monthly_budget := 5000

# Estimated monthly costs per resource type (simplified)
cost_estimates := {
    "aws_instance": {"t3.micro": 7.6, "t3.small": 15.2, "t3.medium": 30.4, "t3.large": 60.8, "m5.large": 70.1, "m5.xlarge": 140.2},
    "aws_db_instance": {"db.t3.micro": 12.4, "db.t3.small": 24.8, "db.t3.medium": 49.6, "db.r5.large": 175.2},
    "aws_nat_gateway": {"default": 32.4},
    "aws_eks_cluster": {"default": 73.0},
}

default allow := false

allow if {
    estimated_monthly_cost < monthly_budget
}

deny contains msg if {
    estimated_monthly_cost >= monthly_budget
    msg := sprintf("Estimated monthly cost $%.2f exceeds budget $%.2f. Reduce resources or request budget increase.", [estimated_monthly_cost, monthly_budget])
}

estimated_monthly_cost := sum([cost |
    some rc in tfplan.resource_changes
    rc.change.actions[_] == "create"
    cost := resource_cost(rc)
])

resource_cost(rc) := c if {
    rc.type == "aws_instance"
    instance_type := rc.change.after.instance_type
    c := cost_estimates["aws_instance"][instance_type]
} else := c if {
    rc.type == "aws_db_instance"
    instance_class := rc.change.after.instance_class
    c := cost_estimates["aws_db_instance"][instance_class]
} else := c if {
    costs := cost_estimates[rc.type]
    c := costs["default"]
} else := 0
```

#### Prevent Mass Resource Deletion

```rego
# policy/cost_blast_radius.rego
package terraform.cost

import input as tfplan

max_deletes := 5

deny contains msg if {
    deletes := [rc |
        some rc in tfplan.resource_changes
        rc.change.actions[_] == "delete"
    ]
    count(deletes) > max_deletes
    msg := sprintf("Plan deletes %d resources (max allowed: %d). Review changes carefully.", [count(deletes), max_deletes])
}

warn contains msg if {
    some rc in tfplan.resource_changes
    rc.change.actions[_] == "delete"
    rc.type == "aws_db_instance"
    msg := sprintf("Plan deletes RDS instance '%s'. Ensure backups exist before proceeding.", [rc.address])
}
```

#### Enforce Reserved Instance Coverage

```rego
# policy/cost_reserved.rego
package terraform.cost

import input as tfplan

# Instance types that should use reserved instances in production
ri_required_types := {"m5.xlarge", "m5.2xlarge", "r5.large", "r5.xlarge", "c5.xlarge"}

warn contains msg if {
    some rc in tfplan.resource_changes
    rc.type == "aws_instance"
    rc.change.actions[_] == "create"
    instance_type := rc.change.after.instance_type
    instance_type in ri_required_types
    msg := sprintf("Instance '%s' (%s) should be covered by a Reserved Instance or Savings Plan.", [rc.address, instance_type])
}
```

Run plan-based cost policies:

```bash
# Generate plan
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json

# Evaluate cost policies
thothctl scan iac -t opa -o "mode=opa,decision=terraform/cost/allow" --enforcement hard
```

### Combining Cost Policies with Security Scanning

Run cost governance alongside security scanning in a single command:

```bash
# Full pipeline: security + cost policies
thothctl scan iac -t checkov -t opa --enforcement hard --post-to-pr
```

The `policy/` directory can contain both security and cost policies — Conftest evaluates all `.rego` files in the directory. Organize by concern:

```
policy/
├── security_s3.rego          # S3 encryption, public access
├── security_iam.rego         # IAM least privilege
├── cost_instance_types.rego  # Instance type restrictions
├── cost_tags.rego            # Required cost allocation tags
├── cost_rds.rego             # RDS cost controls
└── cost_budget.rego          # Budget gate (OPA mode)
```

### Cost Policy in CI/CD

```yaml
# GitHub Actions — cost gate before deploy
- name: Cost Policy Check
  run: |
    terraform show -json tfplan.binary > tfplan.json
    thothctl scan iac -t opa -o "mode=opa,policy_dir=policy,decision=terraform/cost/allow" --enforcement hard --post-to-pr
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Enforcement Modes

### Soft Mode (Default)

Report violations without failing the pipeline. Useful during development:

```bash
# Reports issues but exits 0
thothctl scan iac -t checkov -t opa
```

### Hard Mode

Fail the pipeline when any tool finds violations. Use in CI/CD:

```bash
# Exits 1 if any tool finds failures or errors
thothctl scan iac -t checkov -t opa -t trivy --enforcement hard
```

!!! tip
    The `--enforcement` flag applies to **all** tools in the scan. If Checkov finds 1 failure or OPA finds 1 violation, the pipeline fails.

## Compliance Validation

Use terraform-compliance for BDD-style compliance testing:

```bash
mkdir -p features
cat > features/s3_compliance.feature << 'EOF'
Feature: S3 buckets should be secure
  Scenario: Ensure S3 buckets have encryption enabled
    Given I have aws_s3_bucket defined
    Then it must have server_side_encryption_configuration
EOF

thothctl scan iac -t terraform-compliance --enforcement hard
```

## Multi-Tool Scanning

Leverage multiple scanning tools for comprehensive coverage:

```bash
# All available tools
thothctl scan iac -t checkov -t trivy -t opa -t kics --enforcement hard --verbose

# Generate HTML reports
thothctl scan iac -t checkov -t trivy -t opa --html-reports-format simple --reports-dir ./security-reports
```

## Vulnerability Reporting

Every scan generates a `scan_summary.md` in the reports directory:

```bash
thothctl scan iac -t checkov -t trivy -t opa --reports-dir ./security-reports

# View the summary
cat ./security-reports/scan_summary.md
```

The summary includes a table with per-tool breakdown:

```
| Tool    | Status   | Total | Passed | Failed | Warnings | Errors | Skipped | Success Rate |
|---------|----------|-------|--------|--------|----------|--------|---------|--------------|
| checkov | COMPLETE | 55    | 50     | 3      | 0        | 0      | 2       | 90.9%        |
| opa     | COMPLETE | 10    | 8      | 1      | 1        | 0      | 0       | 80.0%        |
| TOTAL   |          | 65    | 58     | 4      | 1        | 0      | 2       | 89.2%        |
```

## Scheduled Security Audits

Set up scheduled security audits to regularly check your infrastructure code:

```bash
# Cron job — weekly scan
(crontab -l 2>/dev/null; echo "0 0 * * 0 cd /path/to/project && thothctl scan iac -t checkov -t opa --reports-dir ./security-reports") | crontab -
```
