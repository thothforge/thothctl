# ThothCTL Check Environment Command

## Overview

The `thothctl check environment` command validates the development environment and required tools installation. This command ensures that all necessary tools are installed, accessible, and meet version requirements for infrastructure development workflows.

## Command Structure

```
Usage: thothctl check environment [OPTIONS]

  Check development environment and tool installations

Options:
  --help    Show this message and exit.
```

## Basic Usage

### Check Environment Setup

```bash
thothctl check environment
```

This validates the current development environment and provides a comprehensive report of tool availability and versions.

## Validation Output

The command provides professional Rich-formatted output showing:

### Tool Availability
- Installation status for each required tool
- Version information (current vs recommended)
- Installation path and accessibility
- Compatibility warnings

### Version Compliance
- Current installed versions
- Recommended versions for optimal compatibility
- Version mismatch warnings
- Upgrade recommendations

## Example Output

```
╭──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ 🔧 Development Environment Check                                                                                                                                                                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

                                         🛠️ Tool Availability                                        
╭───────────────────────────┬──────────────────┬──────────────────┬────────────────────────────────╮
│ Tool                      │ Status           │ Version          │ Recommended                    │
├───────────────────────────┼──────────────────┼──────────────────┼────────────────────────────────┤
│ terraform                 │ ✅ Available     │ 1.6.0            │ 1.6.0                          │
│ terragrunt                │ ✅ Available     │ 0.53.0           │ 0.53.0                         │
│ opentofu                  │ ✅ Available     │ 1.6.0            │ 1.6.0                          │
│ git                       │ ✅ Available     │ 2.34.1           │ 2.30.0+                        │
│ python                    │ ✅ Available     │ 3.11.5           │ 3.8.0+                         │
╰───────────────────────────┴──────────────────┴──────────────────┴────────────────────────────────╯

╭──────────────────────────────────────────────────────────────────────────────────────────────────────────── Summary ─────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ ✅ Development environment is properly configured                                                                                                                                                                                    │
│ 🛠️ All required tools are available and up to date                                                                                                                                                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Validated Tools

The command checks for the following tools:

### Infrastructure Tools
- **Terraform**: Infrastructure as Code provisioning
- **OpenTofu**: Open-source Terraform alternative
- **Terragrunt**: Terraform orchestration and DRY configuration

### Version Control
- **Git**: Source code management
- **GitHub CLI** (optional): GitHub integration
- **Azure CLI** (optional): Azure DevOps integration

### Development Tools
- **Python**: Required for ThothCTL and extensions
- **Node.js** (optional): For certain templates and tools
- **Docker** (optional): Container-based workflows

### Security Tools
- **Checkov** (optional): Infrastructure security scanning
- **Trivy** (optional): Vulnerability scanning

## Use Cases

### Environment Setup Validation

Before starting infrastructure development:

```bash
thothctl check environment
```

Ensures all required tools are properly installed and configured.

### CI/CD Pipeline Validation

In continuous integration environments:

```bash
# Validate build environment
thothctl check environment
```

Confirms the CI environment has all necessary tools for infrastructure operations.

### Onboarding New Developers

For new team members setting up their development environment:

```bash
thothctl check environment
```

Provides a checklist of required tools and their installation status.

## Configuration

### Version Requirements

Tool version requirements are defined in `version_tools.py` as the single source of truth:

```python
TOOL_VERSIONS = {
    "terraform": {
        "min_version": "1.5.0",
        "recommended": "1.6.0",
        "install_method": "https://terraform.io/downloads"
    },
    "terragrunt": {
        "min_version": "0.50.0", 
        "recommended": "0.53.0",
        "install_method": "https://terragrunt.gruntwork.io/docs/getting-started/install/"
    }
}
```

### Custom Tool Validation

Organizations can extend tool validation by:
1. Updating `version_tools.py` with custom requirements
2. Adding organization-specific tools
3. Defining custom version policies

## Error Scenarios

### Tool Not Found
```
❌ terraform: Not found in PATH
```
**Solution**: Install Terraform following the official installation guide.

### Version Mismatch
```
⚠️ terraform: 1.4.0 (recommended: 1.6.0)
```
**Solution**: Upgrade to the recommended version for optimal compatibility.

### Permission Issues
```
❌ terraform: Permission denied
```
**Solution**: Ensure proper execution permissions and PATH configuration.

## Best Practices

1. **Regular Validation**: Run environment checks regularly to catch tool updates
2. **CI Integration**: Include environment validation in CI/CD pipelines
3. **Team Consistency**: Ensure all team members use compatible tool versions
4. **Documentation**: Keep tool requirements documented and up to date
5. **Automation**: Automate tool installation where possible

## Troubleshooting

### PATH Issues
If tools are installed but not found:
```bash
# Check PATH configuration
echo $PATH

# Verify tool location
which terraform
```

### Version Detection Issues
If version detection fails:
```bash
# Manual version check
terraform version
terragrunt --version
```

### Permission Problems
For permission-related issues:
```bash
# Check file permissions
ls -la $(which terraform)

# Fix permissions if needed
chmod +x $(which terraform)
```

## Exit Codes

- **Exit Code 0**: All required tools are available and meet version requirements
- **Exit Code 1**: Missing tools or version mismatches detected

## Related Documentation

- [Quick Start Guide](../../../quick_start.md): Getting started with ThothCTL
- [Installation Guide](../../../installation/windows_installation.md): Platform-specific installation
- [Troubleshooting](../../../troubleshooting/troubleshooting.md): Common environment issues and solutions
