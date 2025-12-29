# Scan IaC Command

## Overview

The `scan iac` command performs comprehensive security scanning of Infrastructure as Code templates using multiple security tools.

## Usage

```bash
# Basic security scan
thothctl scan iac

# Recursive scanning
thothctl scan iac --recursive

# Specific scanner
thothctl scan iac --scanner checkov
```

## Features

- **Multi-Scanner Support**: Checkov, Trivy, TFSec integration
- **Security Policy Checking**: CIS benchmarks and best practices
- **Vulnerability Detection**: Identify security misconfigurations
- **Compliance Reporting**: Generate compliance reports
- **CI/CD Integration**: Automated security scanning

## Supported Scanners

- **Checkov**: Policy-as-code scanning
- **Trivy**: Vulnerability and misconfiguration detection
- **TFSec**: Terraform security scanner
- **Terraform Compliance**: BDD testing for Terraform

## Output

The command provides:
- Security findings by severity
- Compliance violations
- Remediation recommendations
- Detailed scan reports

## Examples

### Basic Security Scan
```bash
thothctl scan iac
```

### Comprehensive Scan
```bash
thothctl scan iac --recursive --all-scanners
```

## Related Commands

- [`check iac`](../check/check_iac.md) - Structure validation
- [`inventory iac`](../inventory/iac.md) - Component inventory
- [`document iac`](../document/iac.md) - Documentation generation
