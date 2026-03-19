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
