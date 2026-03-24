# IaC Scanning

The `thothctl scan iac` command provides comprehensive security scanning for Infrastructure as Code (IaC) resources. It integrates with multiple industry-standard security scanning tools to identify vulnerabilities, misconfigurations, and compliance issues in your Terraform or OpenTofu code.

## Command Syntax

```bash
thothctl scan iac [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-t, --tools [checkov\|trivy\|tfsec\|kics\|terraform-compliance\|opa]` | Specify which security scanning tools to use |
| `--reports-dir PATH` | Directory to store scan reports (default: `Reports`) |
| `-p, --project-name TEXT` | Name of the project being scanned |
| `-o, --options TEXT` | Additional options for scanning tools (key=value,key2=value2) |
| `--tftool [terraform\|tofu]` | Specify which Terraform tool to use (default: tofu) |
| `--verbose` | Enable verbose output with detailed scan information |
| `--html-reports-format [simple\|xunit]` | Generate HTML reports in simple or xunit format |
| `--enforcement [soft\|hard]` | Enforcement mode: `soft` reports violations (exit 0), `hard` fails the pipeline (exit 1) |
| `--post-to-pr` | Post scan summary as a PR comment (Azure DevOps or GitHub) |
| `--vcs-provider [auto\|azure_repos\|github]` | VCS provider for PR comments (default: auto-detect) |
| `--space TEXT` | Space name for credential resolution (Azure DevOps) |
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

### TFSec

[TFSec](https://github.com/aquasecurity/tfsec) is a security scanner for Terraform code that checks for potential security issues.

```bash
# Scan with TFSec only
thothctl scan iac -t tfsec
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

Every scan produces:

- **Rich terminal table** with per-tool breakdown (passed, failed, warnings, errors, skipped, success rate)
- **`scan_summary.md`** saved to the reports directory (always generated)
- **HTML reports** per tool in the reports directory
- **PR comment** (when `--post-to-pr` is set)

The markdown summary includes a Warnings column for tools that produce warnings (e.g., Conftest `warn` rules):

```
| Tool    | Status   | Total | Passed | Failed | Warnings | Errors | Skipped | Success Rate |
|---------|----------|-------|--------|--------|----------|--------|---------|--------------|
| checkov | COMPLETE | 55    | 50     | 3      | 0        | 0      | 2       | 90.9%        |
| opa     | COMPLETE | 10    | 8      | 1      | 1        | 0      | 0       | 80.0%        |
| TOTAL   |          | 65    | 58     | 4      | 1        | 0      | 2       | 89.2%        |
```

## Examples

### Basic Scan

```bash
# Run a basic scan with default settings (Checkov)
thothctl scan iac
```

### Multi-Tool Scan

```bash
# Comprehensive scan with multiple tools
thothctl scan iac -t checkov -t trivy -t opa --html-reports-format simple --verbose
```

### CI/CD with Hard Enforcement

```bash
# Fail the pipeline if any violations are found
thothctl scan iac -t checkov -t opa --enforcement hard --post-to-pr
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
3. **Write custom OPA policies** — Encode your organization's specific security requirements as Rego policies. Start with the `policy/` directory convention.
4. **Use Conftest mode for fast feedback** — Static HCL analysis doesn't require a Terraform plan, making it ideal for pre-commit hooks and early CI stages.
5. **Use OPA mode for change analysis** — Plan-based evaluation catches issues that static analysis can't, like blast radius and IAM changes.
6. **Always review the `scan_summary.md`** — The markdown summary is generated on every scan and provides a quick overview of all findings.
