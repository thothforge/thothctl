# IaC Scanning

The `thothctl scan iac` command provides comprehensive security scanning for Infrastructure as Code (IaC) resources. It integrates with multiple industry-standard security scanning tools to identify vulnerabilities, misconfigurations, and compliance issues in your Terraform or OpenTofu code.

## Command Syntax

```bash
thothctl scan iac [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `--verbose` | Enable verbose output with detailed scan information |
| `--html-reports-format [simple\|xunit]` | Generate HTML reports in simple or xunit format |
| `--output-format [text\|json\|xml]` | Specify the output format for scan results |
| `--tftool [terraform\|tofu]` | Specify which Terraform tool to use (terraform or tofu) |
| `--terraform-compliance-options TEXT` | Additional options to pass to Terraform-compliance scanner |
| `--checkov-options TEXT` | Additional options to pass to Checkov scanner |
| `--tfsec-options TEXT` | Additional options to pass to TFSec scanner |
| `--trivy-options TEXT` | Additional options to pass to Trivy scanner |
| `--features-dir PATH` | Directory containing terraform-compliance features |
| `-t, --tools [trivy\|tfsec\|checkov\|terraform-compliance]` | Specify which security scanning tools to use |
| `--reports-dir PATH` | Directory to store scan reports |
| `--post-to-pr` | Post scan summary as a PR comment (Azure DevOps or GitHub) |
| `--vcs-provider [auto\|azure_repos\|github]` | VCS provider for PR comments (default: auto-detect) |
| `--space TEXT` | Space name for credential resolution (Azure DevOps) |
| `--help` | Show help message and exit |

## Scanning Tools

### Checkov

[Checkov](https://www.checkov.io/) is a static code analysis tool for IaC that scans cloud infrastructure provisioned using Terraform, CloudFormation, Kubernetes, Serverless, or ARM Templates and detects security and compliance misconfigurations.

```bash
# Scan with Checkov only
thothctl scan iac -t checkov

# Pass additional options to Checkov
thothctl scan iac -t checkov --checkov-options "--skip-check CKV_AWS_1,CKV_AWS_2"
```

### Trivy

[Trivy](https://trivy.dev/) is a comprehensive security scanner that can find vulnerabilities in container images, file systems, and git repositories, as well as misconfigurations in IaC files.

```bash
# Scan with Trivy only
thothctl scan iac -t trivy

# Pass additional options to Trivy
thothctl scan iac -t trivy --trivy-options "--severity HIGH,CRITICAL"
```

### TFSec

[TFSec](https://github.com/aquasecurity/tfsec) is a security scanner for Terraform code that checks for potential security issues.

```bash
# Scan with TFSec only
thothctl scan iac -t tfsec

# Pass additional options to TFSec
thothctl scan iac -t tfsec --tfsec-options "--exclude-downloaded-modules"
```

### Terraform-compliance

[Terraform-compliance](https://terraform-compliance.com/) is a lightweight, security and compliance focused test framework against Terraform that enables negative testing capability for your infrastructure-as-code.

```bash
# Scan with Terraform-compliance only
thothctl scan iac -t terraform-compliance --features-dir ./features

# Pass additional options to Terraform-compliance
thothctl scan iac -t terraform-compliance --terraform-compliance-options "--no-ansi"
```

## Report Formats

ThothCTL can generate reports in various formats to suit your needs:

### Text Output

```bash
thothctl scan iac --output-format text
```

### JSON Output

```bash
thothctl scan iac --output-format json
```

### XML Output

```bash
thothctl scan iac --output-format xml
```

### HTML Reports

```bash
# Generate simple HTML reports
thothctl scan iac --html-reports-format simple

# Generate xunit-style HTML reports (requires xunit-viewer)
thothctl scan iac --html-reports-format xunit
```

!!! note
    To use the xunit format, you must have xunit-viewer installed: `npm -g install xunit-viewer`

## AI-Powered Recommendations

ThothCTL can send scan results to AI tools for analysis and recommendations on how to fix identified issues. This feature helps developers understand security findings and implement appropriate fixes.

## Examples

### Basic Scan

```bash
# Run a basic scan with default settings
thothctl scan iac
```

### Comprehensive Scan

```bash
# Run a comprehensive scan with all tools and generate HTML reports
thothctl scan iac -t checkov -t trivy -t tfsec -t terraform-compliance --html-reports-format simple --verbose
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

ThothCTL's scan command can be easily integrated into CI/CD pipelines to automate security scanning of IaC resources:

```yaml
# Example GitHub Actions workflow
name: Security Scan

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install ThothCTL
        run: pip install thothctl
        
      - name: Run Security Scan
        run: thothctl scan iac -t checkov -t trivy --reports-dir ./reports --post-to-pr
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        
      - name: Upload Scan Results
        uses: actions/upload-artifact@v3
        with:
          name: security-scan-results
          path: ./reports
```

### Azure Pipelines

```yaml
- script: thothctl scan iac -t checkov --post-to-pr
  displayName: 'Security Scan'
  env:
    AZDO_PERSONAL_ACCESS_TOKEN: $(System.AccessToken)
```

The `--post-to-pr` flag posts a scan results summary table (tool, status, passed/failed/errors, success rate) directly to the pull request. See [check iac PR comment docs](../check/check_iac.md#pr-comment-integration) for full platform setup details and required Azure DevOps permissions.

## Best Practices

1. **Run scans early and often** - Integrate security scanning into your development workflow to catch issues early.
2. **Use multiple scanning tools** - Different tools catch different types of issues, so using multiple tools provides better coverage.
3. **Customize scan options** - Use tool-specific options to focus on relevant security checks for your environment.
4. **Review AI recommendations** - AI-powered recommendations can help you understand and fix security issues more effectively.
5. **Store and track reports** - Keep a history of scan reports to track security improvements over time.
