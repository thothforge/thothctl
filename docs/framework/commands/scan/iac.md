# Scan IaC Command

## Overview

The `scan iac` command performs comprehensive security scanning of Infrastructure as Code templates using multiple security tools.

## Usage

```bash
# Basic security scan (Checkov by default)
thothctl scan iac

# Multi-tool scan
thothctl scan iac -t checkov -t trivy -t opa

# Hard enforcement — exit 1 on violations
thothctl scan iac -t checkov -t opa --enforcement hard
```

## Features

- **Multi-Scanner Support**: Checkov, Trivy, TFSec, KICS, OPA/Conftest integration
- **Custom Policy Evaluation**: Write Rego policies for organization-specific rules via OPA
- **Enforcement Modes**: Soft (report only) or hard (fail pipeline) for all tools
- **Security Policy Checking**: CIS benchmarks and best practices
- **Vulnerability Detection**: Identify security misconfigurations
- **Compliance Reporting**: Generate HTML, Markdown, and JSON reports
- **CI/CD Integration**: `--enforcement hard` + `--post-to-pr` for automated pipelines

## Supported Scanners

| Scanner | Description |
|---------|-------------|
| **Checkov** | Policy-as-code scanning with built-in rules |
| **Trivy** | Vulnerability and misconfiguration detection |
| **TFSec** | Terraform security scanner |
| **KICS** | Static analysis via Docker |
| **OPA/Conftest** | Custom Rego policy evaluation (static HCL + plan-based) |

## Output

Every scan produces:

- Rich terminal table with per-tool breakdown
- `scan_summary.md` in the reports directory (always generated)
- HTML reports per tool
- PR comment (when `--post-to-pr` is set)

## Examples

### Basic Security Scan
```bash
thothctl scan iac
```

### Comprehensive Scan with Enforcement
```bash
thothctl scan iac -t checkov -t trivy -t opa --enforcement hard --html-reports-format simple
```

### OPA Custom Policies
```bash
# Static HCL analysis with Conftest
thothctl scan iac -t opa -o "policy_dir=my-policies"

# Plan-based evaluation with OPA
thothctl scan iac -t opa -o "mode=opa,decision=terraform/analysis/authz"
```

## Related Commands

- [`check iac`](../check/check_iac.md) - Structure validation
- [`inventory iac`](../inventory/iac.md) - Component inventory
- [`document iac`](../document/iac.md) - Documentation generation
