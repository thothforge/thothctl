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

## OPA/Conftest Scanner (v0.19.0)

The OPA/Conftest scanner supports two evaluation modes:

| Mode | Input | Command | Best For |
|------|-------|---------|----------|
| **conftest** (default) | Static HCL files | `conftest test` | Naming conventions, tagging, structure rules |
| **opa exec** | `tfplan.json` | `opa exec` | Plan-based validation (resource counts, blast radius, drift) |

### Key Features

- **Unified HTML reports** matching the same style as Checkov/KICS/Trivy (gradient header, severity badges, cards)
- **Git-hosted policy repos** — point to a remote Git repository containing your Rego policies
- **`THOTH_ORG_POLICY` env var** — centralizes policy source for OPA, terraform-compliance, and project structure rules
- **OPA v1 Rego syntax required** — policies must use `import rego.v1` and the `contains`/`if` keywords

### Example Usage

```bash
# Scan with OPA using conftest mode (static HCL)
thothctl scan iac -t opa

# Scan with OPA using plan-based evaluation
thothctl scan iac -t opa --opa-mode exec

# Use a Git-hosted policy repo
export THOTH_ORG_POLICY=https://github.com/myorg/infra-policies.git
thothctl scan iac -t opa
```

### Policy Structure (OPA v1)

```rego
package terraform.policies

import rego.v1

deny contains msg if {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket"
    not resource.change.after.tags.Environment
    msg := sprintf("S3 bucket %q missing 'Environment' tag", [resource.address])
}

warn contains msg if {
    resource := input.resource_changes[_]
    resource.type == "aws_instance"
    resource.change.after.instance_type == "t2.micro"
    msg := sprintf("Instance %q uses t2.micro — consider t3.micro for better perf/cost", [resource.address])
}
```

### YAML Data Files for Policy Parameterization (v0.20.2)

OPA/Conftest now supports automatic conversion of YAML data files (`.yaml`/`.yml`) to JSON for policy parameterization. This allows you to externalize policy parameters — such as allowed regions, required tags, and thresholds — from your Rego code into maintainable YAML configuration files.

#### How It Works

- Place YAML files alongside your `.rego` policies (e.g., `policy/config.yaml`)
- ThothCTL auto-converts YAML data files to JSON before running Conftest
- Conftest automatically loads the converted JSON as data via its `--data` flag
- **Caching**: only reconverts if the YAML source is newer than the existing JSON, avoiding unnecessary work on repeated scans

#### Use Case

Externalize policy parameters that change across teams or environments without modifying Rego logic:

- Allowed cloud regions
- Required resource tags
- Cost or resource count thresholds
- Naming convention patterns

#### Example

Define your parameters in YAML:

```yaml
# policy/config.yaml
allowed_regions:
  - us-east-1
  - eu-west-1
required_tags:
  - Environment
  - Owner
```

Reference them in your Rego policy via `data.config`:

```rego
# policy/regions.rego
package main
import data.config

deny[msg] {
  # uses config.allowed_regions from YAML
  resource := input.resource.aws_instance[name]
  not resource.provider_region in config.allowed_regions
  msg := sprintf("Instance '%s' deployed in non-allowed region", [name])
}

deny[msg] {
  resource := input.resource.aws_instance[name]
  missing := {tag | tag := config.required_tags[_]; not resource.tags[tag]}
  count(missing) > 0
  msg := sprintf("Instance '%s' missing required tags: %v", [name, missing])
}
```

#### Directory Layout

```
policy/
├── config.yaml         # Externalized parameters (auto-converted to JSON)
├── regions.rego        # Policy using data.config.allowed_regions
├── tagging.rego        # Policy using data.config.required_tags
└── ...
```

No additional CLI flags are needed — ThothCTL detects YAML files in the policy directory automatically.

## Enforcement (v0.19.0)

When `--enforcement hard` is specified, ThothCTL gates the pipeline based on scan findings:

```bash
thothctl scan iac -t checkov -t opa --enforcement hard
```

### Behavior

- **Only `deny` rules trigger enforcement** — `warn` rules are informational and do not cause a non-zero exit
- Displays a **Non-Compliance Findings** table showing the top 15 HIGH/CRITICAL violations across all tools
- Shows **per-tool violation counts** so teams know which tool flagged the most issues
- Provides a **clear guidance message** explaining how to fix or suppress findings
- Exit code `1` is returned when any deny-level violations exist (hard mode)
- Exit code `0` is always returned in soft mode regardless of findings

### Example Output

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                  Non-Compliance Findings (Top 15)             ┃
┡━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Tool          │ Severity │ Finding                            │
├───────────────┼──────────┼────────────────────────────────────┤
│ checkov       │ HIGH     │ CKV_AWS_18: S3 access logging      │
│ opa           │ CRITICAL │ Missing encryption at rest          │
│ ...           │ ...      │ ...                                │
└───────────────┴──────────┴────────────────────────────────────┘

Per-tool violations: checkov=5, opa=3, trivy=1

❌ Enforcement HARD: 9 deny-level violations found.
   Fix the findings above or add suppressions to proceed.
```

## HTML Reports (v0.19.0)

All scanning tools now generate unified HTML reports with a consistent visual style:

```
Reports/
├── checkov/
│   └── html_reports/
│       ├── index.html          # Summary index page
│       ├── stack_main.html     # Per-stack report
│       └── stack_modules.html
├── trivy/
│   └── html_reports/
│       ├── index.html
│       └── ...
├── kics/
│   └── html_reports/
│       └── ...
├── opa/
│   └── html_reports/
│       └── ...
└── terraform-compliance/
    └── html_reports/
        └── ...
```

### Design

- **Gradient header** with tool name and scan metadata
- **Inter font** for professional, readable typography
- **Severity badges** color-coded (CRITICAL=red, HIGH=orange, MEDIUM=yellow, LOW=blue)
- **Card layout** grouping findings by resource or check
- **Per-stack reports** with a unified index page linking to each stack
- **Print-friendly** CSS for PDF export and documentation

## Dashboard Integration (v0.19.0)

The ThothCTL web dashboard provides an interactive view of scan findings:

```bash
# Launch the dashboard after scanning
thothctl dashboard launch
```

### Features

- **Search and filter** findings by severity, tool, resource type, or keyword
- **Inline report viewer** renders HTML reports via iframe for quick inspection
- **All 5 tools supported**: Checkov, Trivy, KICS, OPA, Terraform-compliance
- **Findings table** with sortable columns and pagination
- **Trend visualization** showing scan improvements over time

### Workflow

```bash
# 1. Run scan with all tools
thothctl scan iac -t checkov -t trivy -t kics -t opa -t terraform-compliance

# 2. Launch dashboard to explore results
thothctl dashboard launch --port 8080

# 3. Open http://localhost:8080 in your browser
```

## Next Steps

For detailed information about scanning IaC resources, see the [IaC Scanning](scan_iac.md) documentation.
