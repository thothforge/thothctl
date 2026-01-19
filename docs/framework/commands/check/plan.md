# Check Terraform Plan Command

## Overview

The `check tfplan` command validates and analyzes Terraform plan files for compliance, security, and best practices.

## Usage

```bash
# Basic plan validation
thothctl check iac -type tfplan

# Recursive plan checking
thothctl check iac --recursive -type tfplan

# Generate markdown report
thothctl check iac -type tfplan --outmd plan-report.md
```

## Features

- **Plan Validation**: Analyze tfplan.json files
- **Security Scanning**: Identify security issues
- **Compliance Checking**: Ensure policy compliance
- **Resource Analysis**: Detailed resource breakdown
- **Report Generation**: Markdown and HTML reports

## Prerequisites

Generate Terraform plan files:
```bash
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
```

## Output

The command provides:
- Resource change summary
- Security findings
- Compliance violations
- Recommendations for improvements

## Examples

### Basic Plan Check
```bash
thothctl check iac -type tfplan
```

### Generate Report
```bash
thothctl check iac -type tfplan --outmd security-report.md
```

## Related Commands

- [`check deps`](deps.md) - Analyze dependencies
- [`check cost-analysis`](cost-analysis.md) - Estimate costs
- [`scan iac`](../scan/iac.md) - Security scanning
