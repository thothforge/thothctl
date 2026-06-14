# IaC Scanning

The `thothctl scan iac` command provides comprehensive security scanning for Infrastructure as Code (IaC) resources. It integrates with multiple industry-standard security scanning tools to identify vulnerabilities, misconfigurations, and compliance issues in your Terraform or OpenTofu code.

## Command Syntax

```bash
thothctl scan iac [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-t, --tools [checkov\|trivy\\|kics\|terraform-compliance\|opa]` | Specify which security scanning tools to use |
| `--reports-dir PATH` | Directory to store scan reports (default: `Reports`) |
| `-p, --project-name TEXT` | Name of the project being scanned |
| `-o, --options TEXT` | Additional options for scanning tools (key=value,key2=value2) |
| `--tftool [terraform\|tofu]` | Specify which Terraform tool to use (default: tofu) |
| `--output [text\|json\|sarif]` | Output format: text (default), json, or sarif |
| `--enforcement [soft\|hard]` | Enforcement mode: `soft` reports violations (exit 0), `hard` fails the pipeline (exit 1) |
| `--post-to-pr` | Post scan summary as a PR comment (Azure DevOps or GitHub) |
| `--vcs-provider [auto\|azure_repos\|github]` | VCS provider for PR comments (default: auto-detect) |
| `--space TEXT` | Space name for credential resolution (Azure DevOps) |
| `--max-workers INT` | Max parallel Checkov scans (default: 2) |
| `--compact` | Use Checkov compact mode to reduce memory on CI agents |
| `--verbose` | Enable verbose output |
| `--help` | Show help message and exit |

## Scanning Tools

### Checkov

[Checkov](https://www.checkov.io/) is a static code analysis tool for IaC that scans cloud infrastructure provisioned using Terraform, CloudFormation, Kubernetes, Serverless, or ARM Templates and detects security and compliance misconfigurations.

```bash
# Scan with Checkov only (default)
thothctl scan iac -t checkov
```

### Trivy

[Trivy](https://trivy.dev/) is a comprehensive security scanner that can find vulnerabilities in container images, file systems, and git repositories, as well as misconfigurations in IaC files.

```bash
# Scan with Trivy only
thothctl scan iac -t trivy
```

### KICS

[KICS](https://kics.io/) (Keeping Infrastructure as Code Secure) is an open source solution for static code analysis of IaC. Requires Docker.

```bash
# Scan with KICS (requires Docker)
thothctl scan iac -t kics
```

### Terraform-compliance

[Terraform-compliance](https://terraform-compliance.com/) is a lightweight, security and compliance focused test framework against Terraform that enables negative testing capability for your infrastructure-as-code.

```bash
# Scan with Terraform-compliance
thothctl scan iac -t terraform-compliance
```

### OPA / Conftest

[Open Policy Agent (OPA)](https://www.openpolicyagent.org/) is a CNCF-graduated general-purpose policy engine. ThothCTL integrates OPA through two modes:

- **Conftest mode** (default): Static analysis of `.tf`, `.yaml`, `.json`, and `.hcl` files using [Conftest](https://www.conftest.dev/), which evaluates Rego policies directly against configuration files without requiring a Terraform plan.
- **OPA mode**: Plan-based evaluation using `opa exec` against `tfplan.json` files, enabling policies that inspect planned changes (blast radius, IAM modifications, resource deletions, etc.).

Both modes use the same [Rego policy language](https://www.openpolicyagent.org/docs/latest/policy-language/).

#### Prerequisites

Install one or both tools depending on your use case:

```bash
# Install Conftest (for static HCL analysis)
thothctl init env  # select conftest

# Install OPA (for plan-based evaluation)
thothctl init env  # select opa

# Or install manually
brew install conftest  # macOS
brew install opa       # macOS
```

#### Writing Policies

Create a `policy/` directory in your project root with `.rego` files:

```bash
mkdir -p policy
```

Example policy — deny S3 buckets without encryption (`policy/s3.rego`):

```rego
package main

deny contains msg if {
    some resource in input.resource.aws_s3_bucket
    not resource.server_side_encryption_configuration
    msg := sprintf("S3 bucket '%s' must have encryption enabled", [resource])
}
```

Example policy — deny public security groups (`policy/security_groups.rego`):

```rego
package main

deny contains msg if {
    some name, sg in input.resource.aws_security_group
    some rule in sg.ingress
    rule.cidr_blocks[_] == "0.0.0.0/0"
    msg := sprintf("Security group '%s' allows ingress from 0.0.0.0/0", [name])
}

warn contains msg if {
    some name, sg in input.resource.aws_security_group
    not sg.tags
    msg := sprintf("Security group '%s' has no tags", [name])
}
```

!!! note
    Conftest looks for `deny`, `warn`, and `violation` rules in the `main` namespace by default. `deny` and `violation` rules count as failures. `warn` rules count as warnings.

#### Conftest Mode (Static Analysis)

Scans `.tf` files directly — no Terraform plan required:

```bash
# Basic scan with default policy/ directory
thothctl scan iac -t opa

# Custom policy directory
thothctl scan iac -t opa -o "policy_dir=my-policies"

# Specific Rego namespace
thothctl scan iac -t opa -o "namespace=terraform.security"

# With additional data files
thothctl scan iac -t opa -o "data_dir=data"
```

#### OPA Mode (Plan-Based Evaluation)

Evaluates policies against `tfplan.json` files for deeper analysis of planned changes:

```bash
# First generate a plan
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json

# Evaluate with OPA
thothctl scan iac -t opa -o "mode=opa"

# Custom decision path
thothctl scan iac -t opa -o "mode=opa,decision=terraform/analysis/authz"
```

Example blast radius policy (`policy/terraform.rego`):

```rego
package terraform.analysis

import input as tfplan

blast_radius := 30

weights := {
    "aws_autoscaling_group": {"delete": 100, "create": 10, "modify": 1},
    "aws_instance": {"delete": 10, "create": 1, "modify": 1},
}

default authz := false

authz if {
    score < blast_radius
    not touches_iam
}

score := s if {
    all := [x |
        some rt, crud in weights
        x := crud.delete * num_deletes[rt] + crud.create * num_creates[rt] + crud.modify * num_modifies[rt]
    ]
    s := sum(all)
}

touches_iam if {
    some rc in tfplan.resource_changes
    rc.type == "aws_iam"
}
```

#### Cost Governance Policies

OPA/Conftest can enforce cost governance rules — budget gates, instance type restrictions, required cost tags, and more. See [Cost Governance Policies with OPA](use_cases.md#cost-governance-policies-with-opa) for complete examples including:

- Deny expensive instance types and enforce cost allocation tags (Conftest mode)
- Budget gate that blocks deployments exceeding a monthly threshold (OPA mode)
- Prevent mass resource deletion and enforce Reserved Instance coverage (OPA mode)

```bash
# Static cost policies against .tf files
thothctl scan iac -t opa -o "policy_dir=policy" --enforcement hard

# Plan-based budget gate against tfplan.json
thothctl scan iac -t opa -o "mode=opa,decision=terraform/cost/allow" --enforcement hard
```

#### Policy Source Resolution

The `policy_dir` option supports multiple sources. ThothCTL resolves policies in this order:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | **Git repository URL** | `https://github.com/myorg/opa-policies.git` |
| 2 | **Relative to project** | `policy` → `<project>/policy/` |
| 3 | **Absolute path** | `/shared/company-policies` |
| 4 | **`THOTH_POLICY_REPO` env var** | Pre-cloned org repo |

##### Git Repository as Policy Source

Pass a Git URL directly as `policy_dir` to fetch policies from a remote repository:

```bash
# Use policies from a Git repo
thothctl scan iac -t opa -o "policy_dir=https://github.com/myorg/opa-policies.git"

# Pin to a specific branch or tag
thothctl scan iac -t opa -o "policy_dir=https://github.com/myorg/opa-policies.git@v1.2.0"
thothctl scan iac -t opa -o "policy_dir=https://github.com/myorg/opa-policies.git@main"

# SSH URL
thothctl scan iac -t opa -o "policy_dir=git@github.com:myorg/opa-policies.git@v1.0"
```

Repos are cached locally at `~/.thothcf/.policy_cache/` and updated on subsequent runs. This enables:

- **Centralized policy management** — one repo shared across all projects
- **Versioned policies** — pin to a tag for stability, or track `main` for latest
- **CI/CD friendly** — no need to pre-clone; ThothCTL handles it

##### Organization Policy Repo (env var)

For teams that pre-clone a shared policy repository in CI/CD:

```bash
export THOTH_POLICY_REPO=/path/to/cloned/org-policies

# ThothCTL will look for policies at:
# 1. <THOTH_POLICY_REPO>/<policy_dir>
# 2. <THOTH_POLICY_REPO>/shared/policy (fallback)
thothctl scan iac -t opa -o "policy_dir=networking"
```

#### Conftest vs OPA Mode

| Aspect | Conftest mode | OPA mode |
|--------|--------------|----------|
| Input | `.tf`, `.yaml`, `.json`, `.hcl` files | `tfplan.json` files |
| Requires plan | No | Yes |
| Best for | Static policy checks (encryption, tags, naming) | Change analysis (blast radius, IAM, deletions) |
| Tool required | `conftest` | `opa` |

## Enforcement Mode

The `--enforcement` flag controls whether policy violations cause the scan command to exit with a non-zero exit code. This applies to **all** scanning tools, not just OPA.

| Mode | Violations found | Exit code |
|------|-----------------|-----------|
| `soft` (default) | yes | 0 |
| `soft` | no | 0 |
| `hard` | yes (any tool) | 1 |
| `hard` | no | 0 |

```bash
# Soft mode (default) — report only
thothctl scan iac -t checkov -t opa

# Hard mode — fail pipeline if any tool finds violations
thothctl scan iac -t checkov -t opa --enforcement hard

# Hard mode in CI/CD — will fail the build step
thothctl scan iac -t checkov -t trivy -t opa --enforcement hard --post-to-pr
```

!!! tip
    Use `--enforcement hard` in CI/CD pipelines to gate deployments on security compliance. Use `--enforcement soft` (default) during local development for informational scanning.

## Report Output

Every scan produces multiple output formats:

### Always Generated

| Output | File | Description |
|--------|------|-------------|
| **Terminal table** | — | Rich table with per-tool pass/fail/warnings/errors/success rate |
| **Severity breakdown** | — | Terminal table showing CRITICAL/HIGH/MEDIUM/LOW counts |
| **Trend comparison** | — | Delta vs previous scan (stored in local SQLite at `~/.thothcf/scan_history.db`) |
| **Unified HTML report** | `Reports/scan_report.html` | Single-page professional report with summary, per-tool bars, severity badges, findings table, and trend |
| **Markdown summary** | `Reports/scan_summary.md` | Machine-readable summary with severity section |

### Conditional Outputs

| Output | Flag | File | Description |
|--------|------|------|-------------|
| **JSON report** | `--output json` | `Reports/scan_report.json` | Structured data for CI/CD pipelines |
| **SARIF report** | `--output sarif` | `Reports/scan_results.sarif` | GitHub Code Scanning / IDE integration |
| **PR comment** | `--post-to-pr` | — | Posts summary to PR (GitHub/Azure DevOps) |

### Output Formats

#### JSON (`--output json`)

Structured JSON for CI/CD machine consumption:

```bash
thothctl scan iac -t checkov -t trivy --output json
```

```json
{
  "timestamp": "2026-06-14T15:30:00",
  "directory": "/path/to/project",
  "total_findings": 5,
  "severity_counts": {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 2},
  "tools": [
    {
      "tool": "checkov",
      "status": "COMPLETE",
      "passed": 40,
      "failed": 3,
      "findings": [{"id": "CKV_AWS_19", "severity": "CRITICAL", "title": "...", "file": "main.tf", "line": 12}]
    }
  ]
}
```

#### SARIF (`--output sarif`)

[SARIF 2.1.0](https://sarifweb.azurewebsites.net/) format for integration with:
- GitHub Code Scanning / Advanced Security
- Azure DevOps
- VS Code SARIF Viewer extension
- JetBrains IDE plugins

```bash
# Generate SARIF report
thothctl scan iac -t checkov --output sarif

# Upload to GitHub Code Scanning
gh api repos/:owner/:repo/code-scanning/sarifs -f "sarif=@Reports/scan_results.sarif"
```

#### Unified HTML Report

A single self-contained `scan_report.html` with:
- Summary cards (total/passed/failed/rate)
- Per-tool success rate bars
- Severity badge breakdown
- Sortable findings table with file/resource/rule details
- Trend comparison (if previous scan exists)
- Print-optimized styling

Generated automatically on every scan — no flag needed.

### Trend / Historical Comparison

ThothCTL automatically stores scan results in a local SQLite database (`~/.thothcf/scan_history.db`) and shows improvement/regression vs the previous scan for the same directory:

```
📈 Trend (vs 2026-06-13)
┌──────────┬──────────┬─────────┬─────────┐
│ Metric   │ Previous │ Current │ Delta   │
├──────────┼──────────┼─────────┼─────────┤
│ Findings │ 8        │ 5       │ ↓ -3    │
│ Passed   │ 38       │ 44      │ ↑ +6    │
│ Failed   │ 8        │ 5       │ ↓ -3    │
│ CRITICAL │ 2        │ 1       │ ↓ -1    │
│ HIGH     │ 4        │ 3       │ ↓ -1    │
└──────────┴──────────┴─────────┴─────────┘
```

- **No configuration needed** — history is always saved automatically
- **Per-directory tracking** — each project gets its own history
- **Shown in HTML report** — trend is included in `scan_report.html`

### CI/CD: Comparing Across Runs

For CI/CD pipelines (where local SQLite isn't persistent), use artifact-based comparison:

```yaml
# GitHub Actions — compare vs previous scan
- uses: actions/download-artifact@v4
  with:
    name: scan-baseline
  continue-on-error: true

- run: thothctl scan iac -t checkov -t trivy --output json --enforcement hard

- uses: actions/upload-artifact@v4
  with:
    name: scan-baseline
    path: Reports/scan_report.json
```

### Report Directory Structure

```
Reports/
├── scan_report.html              ← Unified multi-tool report (summary, severity, findings, trend)
├── scan_summary.md               ← Markdown summary
├── scan_report.json              ← JSON (--output json)
├── scan_results.sarif            ← SARIF (--output sarif)
├── checkov/
│   └── security-scan/
│       ├── html_reports/
│       │   ├── index.html        ← Per-stack browser with links to individual reports
│       │   ├── report_network_vpc.html
│       │   ├── report_data_rds.html
│       │   └── ...
│       ├── report_network_vpc/
│       │   ├── results_junitxml.xml   ← Raw JUnit XML
│       │   └── results_json.json      ← Raw Checkov JSON
│       ├── report_data_rds/
│       │   └── ...
│       └── checkov_log_report.txt
├── trivy/                        ← Raw Trivy output
│   └── results.json
└── opa/                          ← Raw OPA/Conftest output
    ├── conftest_results.json
    └── results_junitxml.xml
```

**Browsing reports:**
- Open `Reports/scan_report.html` for the unified summary with severity and trend
- Open `Reports/checkov/security-scan/html_reports/index.html` to browse individual stack results with detailed check-level findings

## Examples

### Basic Scan

```bash
# Run a basic scan with default settings (Checkov)
thothctl scan iac
```

### Multi-Tool Scan

```bash
# Comprehensive scan with multiple tools
thothctl scan iac -t checkov -t trivy -t opa
```

### CI/CD with Hard Enforcement and SARIF

```bash
# Fail pipeline on violations + produce SARIF for GitHub Security tab
thothctl scan iac -t checkov -t opa --enforcement hard --output sarif --post-to-pr
```

### Custom Report Directory

```bash
# Specify a custom directory for reports
thothctl scan iac --reports-dir ./security-reports
```

### Using OpenTofu Instead of Terraform

```bash
# Use OpenTofu instead of Terraform
thothctl scan iac --tftool tofu
```

## Integration with CI/CD

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

      - name: Install scanning tools
        run: |
          # Checkov (included with thothctl)
          # Install Conftest for OPA policies
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

### Azure Pipelines

```yaml
- script: |
    pip install thothctl
    thothctl scan iac -t checkov -t opa --enforcement hard --post-to-pr
  displayName: 'Security Scan'
  env:
    AZDO_PERSONAL_ACCESS_TOKEN: $(System.AccessToken)
```

## Best Practices

1. **Use `--enforcement hard` in CI/CD** — Gate deployments on security compliance to prevent insecure infrastructure from reaching production.
2. **Use multiple scanning tools** — Different tools catch different types of issues. Combine Checkov (built-in rules) with OPA (custom policies) for best coverage.
3. **Use `--output sarif` for GitHub** — Upload SARIF to GitHub Code Scanning for findings directly in PR diffs and the Security tab.
4. **Write custom OPA policies** — Encode your organization's specific security requirements as Rego policies. Use Git repos as policy source for centralized management.
5. **Track trends** — Scan history is automatic. Review the trend table to catch regressions early.
6. **Use Conftest mode for fast feedback** — Static HCL analysis doesn't require a Terraform plan, making it ideal for pre-commit hooks and early CI stages.
7. **Use OPA mode for change analysis** — Plan-based evaluation catches issues that static analysis can't, like blast radius and IAM changes.
8. **Use `--output json` in CI/CD** — Machine-readable output for custom integrations, dashboards, and artifact-based comparison across runs.
