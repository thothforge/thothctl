# Scan Command

The `scan` command in ThothCTL provides comprehensive security scanning capabilities for Infrastructure as Code (IaC) resources. It integrates multiple industry-standard security scanning tools to help identify vulnerabilities, misconfigurations, and compliance issues in your infrastructure code.

## Overview

The scan command helps DevSecOps teams and developers to:

- Identify security vulnerabilities in IaC templates
- Check for compliance with best practices and security standards
- Enforce custom organizational policies using OPA/Rego
- Generate detailed reports in various formats (HTML, Markdown, JSON)
- Gate CI/CD pipelines with hard enforcement mode
- Post scan summaries to pull requests

## Subcommands

Currently, ThothCTL supports the following scan subcommands:

- `iac` - Scan Infrastructure as Code resources (Terraform, OpenTofu)

## Basic Usage

```bash
# Scan IaC resources using default settings (Checkov)
thothctl scan iac

# Scan with specific tools
thothctl scan iac -t checkov -t trivy -t opa

# Fail pipeline on violations
thothctl scan iac -t checkov -t opa --enforcement hard

# Generate HTML reports
thothctl scan iac --html-reports-format simple
```

## Common Options

| Option | Description |
|--------|-------------|
| `-t, --tools` | Specify scanning tools to use |
| `--enforcement [soft\|hard]` | Exit 0 (soft) or exit 1 on violations (hard) |
| `--reports-dir` | Directory to store scan reports |
| `--verbose` | Enable verbose output |
| `--post-to-pr` | Post scan summary to pull request |

## Supported Scanning Tools

ThothCTL integrates with multiple security scanning tools to provide comprehensive coverage:

| Tool | Type | Requires |
|------|------|----------|
| **Checkov** | Static analysis with built-in rules | `checkov` binary |
| **Trivy** | Vulnerability and misconfiguration detection | `trivy` binary |
| **TFSec** | Terraform security scanner | `tfsec` binary |
| **KICS** | Static analysis via Docker | Docker |
| **Terraform-compliance** | BDD-style compliance testing | `terraform-compliance` binary |
| **OPA/Conftest** | Custom policy evaluation with Rego | `conftest` and/or `opa` binary |

Each tool has its own strengths. Combine built-in rule scanners (Checkov, Trivy) with custom policy tools (OPA) for comprehensive coverage.

## Next Steps

For detailed information about scanning IaC resources, see the [IaC Scanning](scan_iac.md) documentation.
