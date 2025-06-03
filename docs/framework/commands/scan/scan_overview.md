# Scan Command

The `scan` command in ThothCTL provides comprehensive security scanning capabilities for Infrastructure as Code (IaC) resources. It integrates multiple industry-standard security scanning tools to help identify vulnerabilities, misconfigurations, and compliance issues in your infrastructure code.

## Overview

The scan command helps DevSecOps teams and developers to:

- Identify security vulnerabilities in IaC templates
- Check for compliance with best practices and security standards
- Generate detailed reports in various formats
- Get AI-powered recommendations for fixing identified issues

## Subcommands

Currently, ThothCTL supports the following scan subcommands:

- `iac` - Scan Infrastructure as Code resources (Terraform, OpenTofu)

## Basic Usage

```bash
# Scan IaC resources using default settings
thothctl scan iac

# Scan with specific tools
thothctl scan iac -t checkov -t trivy

# Generate HTML reports
thothctl scan iac --html-reports-format simple
```

## Common Options

| Option | Description |
|--------|-------------|
| `--verbose` | Enable verbose output for detailed scan information |
| `--output-format` | Specify the output format for scan results (text, json, xml) |
| `--reports-dir` | Directory to store scan reports |

## Supported Scanning Tools

ThothCTL integrates with multiple security scanning tools to provide comprehensive coverage:

1. **Checkov** - Static code analysis tool for IaC
2. **Trivy** - Comprehensive security scanner for containers and IaC
3. **TFSec** - Security scanner for Terraform code
4. **Terraform-compliance** - BDD-style test framework for Terraform

Each tool has its own strengths and focuses on different aspects of security scanning, providing a well-rounded security assessment of your infrastructure code.

## Next Steps

For more detailed information about scanning IaC resources, see the [IaC Scanning](scan_iac.md) documentation.
