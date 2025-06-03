# Scan Command Use Cases

The `thothctl scan` command is designed to support various security scanning use cases for DevSecOps teams and developers. This page outlines common use cases and how to implement them using ThothCTL.

## Pre-commit Security Checks

Run quick security checks before committing code to catch issues early in the development process.

```bash
# Create a pre-commit hook script
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
echo "Running security scan..."
thothctl scan iac -t checkov --output-format text
if [ $? -ne 0 ]; then
  echo "Security issues found. Please fix them before committing."
  exit 1
fi
EOF
chmod +x .git/hooks/pre-commit
```

## CI/CD Pipeline Integration

Integrate security scanning into your CI/CD pipeline to ensure all code changes are scanned before deployment.

### GitHub Actions Example

```yaml
name: Security Scan

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install ThothCTL
        run: pip install thothctl
        
      - name: Run Security Scan
        run: thothctl scan iac -t checkov -t trivy -t tfsec --output-format json --reports-dir ./reports
        
      - name: Upload Scan Results
        uses: actions/upload-artifact@v3
        with:
          name: security-scan-results
          path: ./reports
```

### GitLab CI Example

```yaml
stages:
  - test

security-scan:
  stage: test
  image: python:3.10
  script:
    - pip install thothctl
    - thothctl scan iac -t checkov -t trivy --output-format json --reports-dir ./reports
  artifacts:
    paths:
      - ./reports
```

## Compliance Validation

Use terraform-compliance to validate that your infrastructure code meets specific compliance requirements.

```bash
# Create a compliance feature file
mkdir -p features
cat > features/s3_bucket_compliance.feature << 'EOF'
Feature: S3 buckets should be secure
  Scenario: Ensure S3 buckets have encryption enabled
    Given I have aws_s3_bucket defined
    Then it must have server_side_encryption_configuration

  Scenario: Ensure S3 buckets block public access
    Given I have aws_s3_bucket defined
    Then it must have block_public_acls
    And its value must be true
EOF

# Run compliance check
thothctl scan iac -t terraform-compliance --features-dir ./features
```

## Security Baseline Enforcement

Establish and enforce security baselines across your organization's infrastructure code.

```bash
# Create a baseline configuration
cat > security-baseline.json << 'EOF'
{
  "checkov": {
    "skip_checks": ["CKV_AWS_18", "CKV_AWS_21"],
    "framework": ["terraform", "secrets"]
  },
  "trivy": {
    "severity": ["HIGH", "CRITICAL"]
  }
}
EOF

# Run scan with baseline configuration
thothctl scan iac -t checkov --checkov-options "--framework terraform --framework secrets --skip-check CKV_AWS_18,CKV_AWS_21" -t trivy --trivy-options "--severity HIGH,CRITICAL"
```

## Vulnerability Reporting

Generate comprehensive vulnerability reports for review by security teams.

```bash
# Generate HTML reports
thothctl scan iac -t checkov -t trivy -t tfsec --html-reports-format simple --reports-dir ./security-reports

# Open the report in a browser
open ./security-reports/index.html
```

## Multi-Tool Scanning

Leverage multiple scanning tools to get comprehensive coverage of potential security issues.

```bash
# Run all supported scanning tools
thothctl scan iac -t checkov -t trivy -t tfsec -t terraform-compliance --features-dir ./features --verbose
```

## Custom Tool Configuration

Customize scanning tools to focus on specific types of issues or to ignore known false positives.

```bash
# Customize Checkov to focus on specific frameworks and skip certain checks
thothctl scan iac -t checkov --checkov-options "--framework terraform --framework secrets --skip-check CKV_AWS_18,CKV_AWS_21"

# Customize Trivy to focus on high and critical severity issues
thothctl scan iac -t trivy --trivy-options "--severity HIGH,CRITICAL"

# Customize TFSec to exclude specific checks
thothctl scan iac -t tfsec --tfsec-options "--exclude aws-s3-enable-bucket-encryption"
```

## Automated Remediation

Use AI-powered recommendations to automatically generate fixes for identified security issues.

```bash
# Run scan and get AI recommendations
thothctl scan iac -t checkov -t trivy --output-format json

# Review and apply recommended fixes
# (This is a conceptual example - actual implementation depends on the AI integration)
```

## Scheduled Security Audits

Set up scheduled security audits to regularly check your infrastructure code for new vulnerabilities.

```bash
# Create a cron job to run security scans weekly
(crontab -l 2>/dev/null; echo "0 0 * * 0 cd /path/to/project && thothctl scan iac -t checkov -t trivy --html-reports-format simple --reports-dir ./security-reports") | crontab -
```

## Team Collaboration

Share scan results with your team to collaborate on fixing security issues.

```bash
# Generate reports in a shareable format
thothctl scan iac -t checkov -t trivy --html-reports-format simple --reports-dir ./shared-reports

# Share the reports directory with your team
# (This could be through a shared drive, version control, or other collaboration tools)
```
