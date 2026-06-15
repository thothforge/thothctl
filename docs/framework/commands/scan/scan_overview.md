# Scan Command

The `scan` command in ThothCTL provides comprehensive security scanning capabilities for Infrastructure as Code (IaC) resources. It integrates multiple industry-standard security scanning tools to help identify vulnerabilities, misconfigurations, and compliance issues in your infrastructure code.

## Overview

The scan command helps DevSecOps teams and developers to:

- Identify security vulnerabilities in IaC templates
- Check for compliance with best practices and security standards
- Enforce custom organizational policies using OPA/Rego
- Generate detailed reports in various formats (HTML, Markdown, JSON, SARIF)
- Track scan trends over time with local SQLite history
- Gate CI/CD pipelines with hard enforcement mode
- Post scan summaries to pull requests
- Integrate with GitHub Code Scanning via SARIF output

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

# JSON output for CI/CD
thothctl scan iac -t checkov --output json

# SARIF output for GitHub Code Scanning
thothctl scan iac -t checkov --output sarif
```

## Common Options

| Option | Description |
|--------|-------------|
| `-t, --tools` | Specify scanning tools: `checkov`, `trivy`, `kics`, `terraform-compliance`, `opa` |
| `--enforcement [soft\|hard]` | Exit 0 (soft) or exit 1 on violations (hard) |
| `--output [text\|json\|sarif]` | Output format (default: text) |
| `--reports-dir` | Directory to store scan reports |
| `--post-to-pr` | Post scan summary to pull request |
| `--verbose` | Enable verbose output |

## Report Outputs

Every scan automatically produces:

| Output | Description |
|--------|-------------|
| `scan_report.html` | Unified multi-tool HTML report with severity, findings, and trend |
| `scan_summary.md` | Markdown summary |
| Terminal tables | Pass/fail per tool + severity breakdown + trend comparison |

Optional outputs via `--output` flag:

| Flag | File | Use Case |
|------|------|----------|
| `--output json` | `scan_report.json` | CI/CD pipeline consumption |
| `--output sarif` | `scan_results.sarif` | GitHub Code Scanning, IDE integration |

## Scan History & Trends

ThothCTL automatically tracks scan results in `~/.thothcf/scan_history.db` (SQLite). On each scan, it compares against the previous run for the same directory and shows improvement or regression.

## Supported Scanning Tools

| Tool | Type | Requires |
|------|------|----------|
| **Checkov** | Static analysis with built-in rules | `checkov` binary |
| **Trivy** | Vulnerability and misconfiguration detection | `trivy` binary |
| **KICS** | Static analysis via Docker | Docker |
| **Terraform-compliance** | BDD-style compliance testing against tfplan.json | `terraform-compliance` (pip) |
| **OPA/Conftest** | Custom policy evaluation with Rego | `conftest` and/or `opa` binary |

Each tool has its own strengths. Combine built-in rule scanners (Checkov, Trivy) with custom policy tools (OPA, Terraform-compliance) for comprehensive coverage.

**Organization Policy Repo**: Set `THOTH_ORG_POLICY` env var to point all policy tools (OPA, terraform-compliance, project structure rules) to a single centralized governance repository.

## Next Steps

For detailed information about scanning IaC resources, see the [IaC Scanning](scan_iac.md) documentation.
