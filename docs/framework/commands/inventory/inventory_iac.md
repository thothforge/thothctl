# ThothCTL Inventory IaC Command

## Overview

The `thothctl inventory iac` command creates, updates, and manages an inventory of Infrastructure as Code (IaC) components in your project. This inventory tracks modules, their versions, sources, and dependencies, providing valuable insights into your infrastructure composition with **modern, professional HTML reports** and comprehensive provider version analysis.

## Recent Improvements ✨

- **🎯 Unified Version Checking**: Single `--check-versions` flag handles both module and provider version checking
- **🎨 Modern HTML Reports**: Professional styling with Inter font, gradients, and responsive design
- **📊 Enhanced Provider Analysis**: Comprehensive provider version tracking with status indicators
- **🚀 Intelligent Automation**: Automatic provider checking when version checking is enabled
- **📱 Responsive Design**: Reports work perfectly on desktop, tablet, and mobile devices

## Command Options

```
Usage: thothctl inventory iac [OPTIONS]

  Create a inventory about IaC modules composition for terraform/tofu/terragrunt projects

Options:
  -pj, --project-name TEXT        Specify a custom project name for the
                                  inventory report
  --provider-tool [tofu|terraform]
                                  Tool to use for checking providers (default:
                                  tofu)
  --check-providers               Check and report provider information for
                                  each stack (automatically enabled with
                                  --check-versions)
  --complete                      Include .terraform and .terragrunt-cache
                                  folders in analysis (complete analysis)
  -ft, --framework-type [auto|terraform|terragrunt|terraform-terragrunt]
                                  Framework type to analyze (auto for
                                  automatic detection)
  -r, --report-type [html|json|cyclonedx|all]
                                  Type of report to generate (cyclonedx
                                  generates OWASP CycloneDX SBOM format)
  -iact, --inventory-action [create|update|restore]
                                  Action for inventory tasks
  -auto, --auto-approve           Use with --update_dependencies option for
                                  auto approve updating dependencies.
  -updep, --update-dependencies-path
                                  Pass the inventory json file path for
                                  updating dependencies.
  -cv, --check-versions           Check latest versions for modules and
                                  providers (includes provider version
                                  checking)
  -iph, --inventory-path PATH     Path for saving inventory reports
  --help                          Show this message and exit.
```

## Basic Usage

### Create a Basic Inventory

```bash
thothctl inventory iac
```

This creates an inventory of all IaC components in the current directory and generates a **modern HTML report** in the default location (`./Reports/Inventory`).

### Create an Inventory with Version Checking (Recommended) 🚀

```bash
thothctl inventory iac --check-versions
```

This creates a comprehensive inventory that:
- ✅ Checks latest versions for all modules
- ✅ Automatically enables provider checking
- ✅ Analyzes provider versions against registries
- ✅ Shows "Latest Version" and "Status" columns
- ✅ Generates modern, professional HTML reports

### Generate Different Report Types

```bash
# HTML report with modern styling (default)
thothctl inventory iac --report-type html

# JSON report for automation
thothctl inventory iac --report-type json

# CycloneDX SBOM report (OWASP standard)
thothctl inventory iac --report-type cyclonedx

# All report types (HTML, JSON, and CycloneDX)
thothctl inventory iac --report-type all
```

### Specify Custom Output Directory and Project Name

```bash
thothctl inventory iac \
  --check-versions \
  --inventory-path ./docs/infrastructure \
  --project-name "Production Infrastructure"
```

## Modern HTML Reports 🎨

The new HTML reports feature:

## CycloneDX SBOM Reports 🔒

ThothCTL now supports generating **CycloneDX Software Bill of Materials (SBOM)** reports, following the OWASP CycloneDX standard:

### Features:
- ✅ **OWASP Standard Compliance**: Follows CycloneDX 1.4 specification
- ✅ **Infrastructure Components**: Maps Terraform modules and providers to SBOM components
- ✅ **Version Tracking**: Includes current and latest version information
- ✅ **Security Integration**: Compatible with vulnerability scanning tools
- ✅ **Supply Chain Visibility**: Provides complete infrastructure dependency mapping

### Use Cases:
- **Security Auditing**: Track all infrastructure dependencies for security reviews
- **Compliance Reporting**: Meet regulatory requirements for software inventory
- **Vulnerability Management**: Integration with security scanning tools
- **Supply Chain Security**: Monitor infrastructure component sources and versions

### Example:
```bash
# Generate CycloneDX SBOM for security audit
thothctl inventory iac --check-versions --report-type cyclonedx

# Complete analysis with all formats including SBOM
thothctl inventory iac --check-versions --report-type all
```

The CycloneDX report includes:
- Infrastructure components as SBOM components
- Version information and update status
- Source URLs and external references
- Custom properties for ThothCTL-specific metadata

### **Professional Design**
- **Inter Font Family**: Modern, readable typography
- **Gradient Headers**: Professional blue gradient styling
- **Responsive Layout**: Works on all devices and screen sizes
- **Print Optimization**: Perfect for PDF generation and documentation

### **Enhanced Data Visualization**
- **Provider Version Columns**: "Latest Version" and "Status" columns for all providers
- **Color-Coded Status Badges**: 
  - 🟢 **Current**: Green badges for up-to-date components
  - 🔴 **Outdated**: Red badges for components needing updates
  - 🟡 **Unknown**: Yellow badges for components with unknown status
- **Interactive Tables**: Hover effects and improved readability
- **Module Information**: Comprehensive component and provider details

### **Report Features**
- **Project Information Header**: Clean project overview with metadata
- **Summary Statistics**: Total components, outdated count, provider statistics
- **Detailed Component Tables**: Organized by stack with full provider information
- **Modern CSS Styling**: Professional appearance suitable for business use

## Version Checking & Provider Analysis 📊

### **Unified Version Checking**

The `--check-versions` flag now provides comprehensive analysis:

```bash
thothctl inventory iac --check-versions
```

**What it does:**
- ✅ Checks latest versions for all Terraform/Terragrunt modules
- ✅ Automatically enables provider checking
- ✅ Analyzes provider versions against registries
- ✅ Shows version comparison (current vs. latest)
- ✅ Provides status indicators (Current/Outdated/Unknown)

### **Provider-Only Analysis**

If you only want provider information without version checking:

```bash
thothctl inventory iac --check-providers
```

### **Provider Version Information**

The reports now include comprehensive provider data:
- **Provider Name**: aws, google, kubernetes, etc.
- **Current Version**: Version currently in use
- **Latest Version**: Most recent available version
- **Source Registry**: Where the provider comes from
- **Module Context**: Which module uses the provider
- **Status**: Current, Outdated, or Unknown

## Framework Type Options

### Auto-detect Framework (Default)

```bash
thothctl inventory iac --framework-type auto
```

Automatically detects the framework type based on project files.

### Terraform Framework

```bash
thothctl inventory iac --framework-type terraform --check-versions
```

Analyzes Terraform files (`.tf`) with version checking.

### Terragrunt Framework

```bash
thothctl inventory iac --framework-type terragrunt --check-versions
```

Analyzes Terragrunt files (`terragrunt.hcl`) with comprehensive provider analysis.

### Mixed Terraform-Terragrunt Framework

```bash
thothctl inventory iac --framework-type terraform-terragrunt --check-versions
```

Analyzes both Terraform and Terragrunt files with full version checking.

## Inventory Actions

### 1. Create (Default)

```bash
thothctl inventory iac --inventory-action create --check-versions
```

Scans IaC files and creates a new inventory with version analysis.

### 2. Update

```bash
thothctl inventory iac \
  --inventory-action update \
  --inventory-path ./path/to/inventory.json \
  --auto-approve
```

Updates IaC files based on the inventory.

### 3. Restore

```bash
thothctl inventory iac \
  --inventory-action restore \
  --inventory-path ./path/to/inventory.json
```

Restores IaC files to the state recorded in the inventory.

## Advanced Usage Examples

### Comprehensive Infrastructure Audit

```bash
thothctl inventory iac \
  --check-versions \
  --report-type all \
  --project-name "Production Infrastructure Audit" \
  --inventory-path ./docs/audit
```

**This generates:**
- Modern HTML report with provider version analysis
- JSON report for automation
- Complete module and provider inventory
- Version status for all components

### Terragrunt Project Analysis

```bash
thothctl inventory iac \
  --framework-type terragrunt \
  --check-versions \
  --project-name "Terragrunt Infrastructure"
```

### CI/CD Integration

```bash
# In your CI/CD pipeline
thothctl inventory iac \
  --check-versions \
  --report-type json \
  --inventory-path ./reports/$(date +%Y-%m-%d)
```

### Complete Analysis with All Options

```bash
thothctl inventory iac \
  --check-versions \
  --complete \
  --report-type all \
  --project-name "Complete Infrastructure Analysis" \
  --provider-tool tofu \
  --inventory-path ./comprehensive-analysis
```

## Report Structure

### HTML Report Sections

1. **Header**: Project name, type, and generation timestamp
2. **Summary**: Statistics about components, providers, and versions
3. **Stack Details**: Organized by stack with:
   - Component tables with version information
   - Provider tables with version analysis
   - Status indicators and latest version information

### JSON Report Structure

```json
{
  "version": 2,
  "projectName": "my-project",
  "projectType": "terraform-terragrunt",
  "components": [
    {
      "stack": "./stacks/networking",
      "components": [
        {
          "type": "module",
          "name": "vpc",
          "version": ["5.0.0"],
          "source": ["terraform-aws-modules/vpc/aws"],
          "latest_version": "5.19.0",
          "source_url": "https://registry.terraform.io/modules/terraform-aws-modules/vpc/aws",
          "status": "Outdated"
        }
      ],
      "providers": [
        {
          "name": "aws",
          "version": "6.0.0",
          "source": "registry.opentofu.org/hashicorp/aws",
          "module": "Root",
          "component": "networking",
          "latest_version": "6.2.0",
          "status": "outdated"
        }
      ]
    }
  ],
  "provider_version_stats": {
    "total_providers": 15,
    "outdated_providers": 3,
    "current_providers": 12,
    "unknown_providers": 0
  }
}
```

## Use Cases

### 1. Infrastructure Auditing

```bash
thothctl inventory iac --check-versions --report-type all
```

**Benefits:**
- Identify outdated modules and providers
- Generate professional reports for stakeholders
- Track infrastructure composition over time

### 2. Version Management

```bash
# Create inventory with version analysis
thothctl inventory iac --check-versions --report-type json

# Review the generated report for outdated components
# Update modules based on findings
```

### 3. Documentation Generation

```bash
thothctl inventory iac \
  --check-versions \
  --project-name "Production Infrastructure Documentation" \
  --report-type html
```

**Generates professional documentation with:**
- Modern styling suitable for business presentations
- Comprehensive component and provider information
- Version status and recommendations

### 4. Compliance and Security

```bash
thothctl inventory iac \
  --check-versions \
  --complete \
  --report-type all
```

**Helps with:**
- Security audits by identifying outdated providers
- Compliance reporting with comprehensive documentation
- Risk assessment through version analysis

### 5. CI/CD Integration

```bash
# In your pipeline
thothctl inventory iac \
  --check-versions \
  --report-type json \
  --inventory-path ./reports/$(date +%Y-%m-%d)

# Parse JSON output for automated decision making
```

## Best Practices

### 1. Regular Version Checking
```bash
# Run weekly to identify outdated components
thothctl inventory iac --check-versions
```

### 2. Comprehensive Analysis
```bash
# For thorough audits, use all features
thothctl inventory iac \
  --check-versions \
  --complete \
  --report-type all \
  --project-name "Monthly Infrastructure Audit"
```

### 3. Documentation Standards
```bash
# Generate consistent documentation
thothctl inventory iac \
  --check-versions \
  --project-name "$(basename $(pwd)) Infrastructure" \
  --inventory-path ./docs/infrastructure
```

### 4. Provider Tool Selection
```bash
# Use OpenTofu for modern Terraform workflows
thothctl inventory iac --check-versions --provider-tool tofu

# Use Terraform for legacy workflows
thothctl inventory iac --check-versions --provider-tool terraform
```

### 5. Report Organization
```bash
# Organize reports by date and environment
thothctl inventory iac \
  --check-versions \
  --inventory-path ./reports/$(date +%Y-%m)/production \
  --project-name "Production Infrastructure - $(date +%B\ %Y)"
```

## Troubleshooting

### Common Issues

#### CSS Styling Issues (Fixed)
The recent updates have resolved all CSS variable issues that previously caused HTML report generation failures.

#### Version Checking Failures
```
Error: Failed to check versions for module xyz
```
**Solution**: Ensure internet connectivity and module source accessibility.

#### Provider Analysis Failures
```
Error: Failed to get providers for stack xyz
```
**Solution**: 
- Ensure the provider tool (tofu/terraform) is installed
- Run `tofu init` or `terraform init` in problematic directories
- Check that all modules are properly initialized

#### Report Generation Issues
```
Error: Failed to generate HTML report
```
**Solution**: Ensure write permissions to the output directory.

### Debugging

For detailed logs:
```bash
thothctl --debug inventory iac --check-versions
```

## Migration from Old Flags

### Before (Deprecated)
```bash
# Old redundant flags
thothctl inventory iac --check-providers --check-provider-versions --check-versions
```

### After (Recommended)
```bash
# New unified approach
thothctl inventory iac --check-versions
```

**Benefits of the new approach:**
- ✅ Single flag for all version checking
- ✅ Automatic provider checking when needed
- ✅ Simplified user experience
- ✅ Reduced confusion
- ✅ Maintained functionality

## Related Commands

- [thothctl check iac](../check/check_iac.md): Check IaC components against best practices
- [thothctl scan](../../use_cases/check_command.md): Scan infrastructure code for security issues
- [thothctl project](../project/project_overview.md): Project management commands

## Summary

The `thothctl inventory iac` command now provides:

- 🎯 **Unified version checking** with a single `--check-versions` flag
- 🎨 **Modern HTML reports** with professional styling and responsive design
- 📊 **Comprehensive provider analysis** with version tracking and status indicators
- 🚀 **Intelligent automation** that enables provider checking when needed
- 📱 **Multi-device compatibility** with responsive design for all screen sizes
- 🔧 **Enhanced user experience** with simplified flags and better documentation

Use `thothctl inventory iac --check-versions` for the best experience with comprehensive analysis and modern reporting.
