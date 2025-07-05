# ThothCTL Inventory Commands

## Overview

The `thothctl inventory` command group provides tools for creating, managing, and updating inventories of your infrastructure components. These inventories help you track modules, their versions, sources, and dependencies, providing valuable insights into your infrastructure composition with **modern, professional reporting** and comprehensive analysis.

## Recent Improvements ✨

- **🎯 Unified Version Checking**: Single `--check-versions` flag handles both module and provider version checking
- **🎨 Modern HTML Reports**: Professional styling with Inter font, gradients, and responsive design
- **📊 Enhanced Provider Analysis**: Comprehensive provider version tracking with status indicators
- **🚀 Intelligent Automation**: Automatic provider checking when version checking is enabled
- **📱 Responsive Design**: Reports work perfectly on desktop, tablet, and mobile devices

## Available Inventory Commands

### [inventory iac](inventory_iac.md) - Infrastructure as Code Inventory

Creates a comprehensive inventory of Infrastructure as Code (IaC) components in your project.

```bash
# Recommended: Comprehensive analysis with modern reporting
thothctl inventory iac --check-versions

# Basic inventory with modern HTML report
thothctl inventory iac

# Complete analysis with all report types
thothctl inventory iac --check-versions --report-type all
```

**Key Features:**
- ✅ **Modern HTML Reports**: Professional styling suitable for business use
- ✅ **Provider Version Analysis**: Comprehensive provider version tracking
- ✅ **Unified Version Checking**: Single flag for all version analysis
- ✅ **Multi-Framework Support**: Terraform, OpenTofu, and Terragrunt
- ✅ **Responsive Design**: Works on all devices and screen sizes

## Common Options

### **Essential Options**

- **`-cv, --check-versions`**: 🚀 **Recommended** - Checks latest versions for modules and providers (includes provider version checking)
- **`-r, --report-type [html|json|all]`**: Type of report to generate (default: html with modern styling)
- **`-pj, --project-name TEXT`**: Custom project name for professional reports
- **`-iph, --inventory-path PATH`**: Where to save inventory reports

### **Framework and Analysis Options**

- **`-ft, --framework-type [auto|terraform|terragrunt|terraform-terragrunt]`**: Framework type to analyze (auto-detection recommended)
- **`--check-providers`**: Check provider information (automatically enabled with `--check-versions`)
- **`--provider-tool [tofu|terraform]`**: Tool for provider analysis (default: tofu)
- **`--complete`**: Include .terraform and .terragrunt-cache folders

### **Action Options**

- **`-iact, --inventory-action [create|update|restore]`**: Action to perform (default: create)
- **`--auto-approve`**: Auto-approve updates without confirmation
- **`--update-dependencies-path`**: Path to inventory JSON for updates

## Framework Types

### Auto-detect Framework (Recommended)

```bash
thothctl inventory iac --framework-type auto --check-versions
```

Automatically detects the framework type and provides comprehensive analysis.

### Terraform Framework

```bash
thothctl inventory iac --framework-type terraform --check-versions
```

Analyzes Terraform files (`.tf`) with modern reporting and version checking.

### Terragrunt Framework

```bash
thothctl inventory iac --framework-type terragrunt --check-versions
```

Analyzes Terragrunt files (`terragrunt.hcl`) with provider version analysis.

### Mixed Terraform-Terragrunt Framework

```bash
thothctl inventory iac --framework-type terraform-terragrunt --check-versions
```

Analyzes both Terraform and Terragrunt files with comprehensive reporting.

## Report Types

### Modern HTML Reports (Default) 🎨

```bash
thothctl inventory iac --check-versions --report-type html
```

**Features:**
- **Professional Design**: Inter font, gradient headers, modern styling
- **Provider Version Columns**: "Latest Version" and "Status" for all providers
- **Color-Coded Status**: Green (Current), Red (Outdated), Yellow (Unknown)
- **Responsive Layout**: Works on desktop, tablet, and mobile
- **Print Optimization**: Perfect for PDF generation

### JSON Reports for Automation

```bash
thothctl inventory iac --check-versions --report-type json
```

**Features:**
- Structured data for CI/CD integration
- Provider version statistics
- Component and module details
- Programmatic analysis support

### Combined Reports

```bash
thothctl inventory iac --check-versions --report-type all
```

Generates both modern HTML and JSON reports for comprehensive documentation and automation.

## Quick Start Examples

### Basic Infrastructure Audit

```bash
thothctl inventory iac --check-versions
```

**What it does:**
- ✅ Scans all IaC files in the current directory
- ✅ Checks latest versions for modules and providers
- ✅ Generates modern HTML report with professional styling
- ✅ Shows version status and recommendations

### Comprehensive Analysis

```bash
thothctl inventory iac \
  --check-versions \
  --report-type all \
  --project-name "Production Infrastructure" \
  --inventory-path ./docs/infrastructure
```

**What it does:**
- ✅ Complete version analysis for modules and providers
- ✅ Generates both HTML and JSON reports
- ✅ Uses custom project name for professional presentation
- ✅ Saves reports in organized directory structure

### CI/CD Integration

```bash
thothctl inventory iac \
  --check-versions \
  --report-type json \
  --inventory-path ./reports/$(date +%Y-%m-%d)
```

**What it does:**
- ✅ Automated inventory creation for pipelines
- ✅ JSON output for programmatic analysis
- ✅ Date-organized report storage
- ✅ Version tracking for compliance

## Use Cases

### 1. Infrastructure Auditing 📊

```bash
thothctl inventory iac --check-versions --report-type all
```

**Benefits:**
- Identify outdated modules and providers
- Generate professional reports for stakeholders
- Track infrastructure composition over time
- Support compliance and security audits

### 2. Documentation Generation 📚

```bash
thothctl inventory iac \
  --check-versions \
  --project-name "Infrastructure Documentation" \
  --report-type html
```

**Benefits:**
- Modern, professional documentation
- Comprehensive component information
- Version status and recommendations
- Suitable for business presentations

### 3. Version Management 🔄

```bash
thothctl inventory iac --check-versions --report-type json
```

**Benefits:**
- Identify components needing updates
- Track version drift over time
- Support automated update workflows
- Maintain infrastructure currency

### 4. Compliance and Security 🔒

```bash
thothctl inventory iac \
  --check-versions \
  --complete \
  --report-type all
```

**Benefits:**
- Security audits through version analysis
- Compliance reporting with comprehensive data
- Risk assessment for outdated components
- Professional documentation for auditors

## Best Practices

### 1. Regular Inventory Creation

```bash
# Weekly infrastructure health check
thothctl inventory iac --check-versions
```

### 2. Professional Documentation

```bash
# Generate business-ready reports
thothctl inventory iac \
  --check-versions \
  --project-name "$(basename $(pwd)) Infrastructure - $(date +%B\ %Y)" \
  --report-type html
```

### 3. Automation Integration

```bash
# CI/CD pipeline integration
thothctl inventory iac \
  --check-versions \
  --report-type json \
  --inventory-path ./reports/$(date +%Y-%m-%d)
```

### 4. Comprehensive Analysis

```bash
# Monthly comprehensive audit
thothctl inventory iac \
  --check-versions \
  --complete \
  --report-type all \
  --project-name "Monthly Infrastructure Audit"
```

## Migration Guide

### From Old Flags (Deprecated)

```bash
# Old approach with redundant flags
thothctl inventory iac --check-providers --check-provider-versions --check-versions
```

### To New Unified Approach (Recommended)

```bash
# New simplified approach
thothctl inventory iac --check-versions
```

**Benefits:**
- ✅ Single flag for all version checking
- ✅ Automatic provider analysis when needed
- ✅ Simplified user experience
- ✅ Maintained functionality
- ✅ Modern reporting

## Advanced Features

### Provider Tool Selection

```bash
# Use OpenTofu (recommended for modern workflows)
thothctl inventory iac --check-versions --provider-tool tofu

# Use Terraform (for legacy workflows)
thothctl inventory iac --check-versions --provider-tool terraform
```

### Complete Analysis

```bash
# Include normally excluded directories
thothctl inventory iac --check-versions --complete
```

### Custom Output Organization

```bash
# Organized by environment and date
thothctl inventory iac \
  --check-versions \
  --inventory-path ./reports/production/$(date +%Y-%m) \
  --project-name "Production Infrastructure - $(date +%B\ %Y)"
```

## Troubleshooting

### Common Issues

1. **No Components Found**: Ensure you're in a directory with IaC files
2. **Version Check Failures**: Verify internet connectivity and module accessibility
3. **Provider Analysis Issues**: Ensure provider tools are installed and initialized
4. **Report Generation Problems**: Check write permissions to output directory

### Getting Help

```bash
# Detailed command help
thothctl inventory iac --help

# Debug mode for troubleshooting
thothctl --debug inventory iac --check-versions
```

## Summary

The ThothCTL inventory commands now provide:

- 🎯 **Unified Experience**: Single `--check-versions` flag for comprehensive analysis
- 🎨 **Modern Reports**: Professional HTML styling suitable for business use
- 📊 **Enhanced Analysis**: Provider version tracking with status indicators
- 🚀 **Intelligent Automation**: Automatic provider checking when needed
- 📱 **Responsive Design**: Multi-device compatibility
- 🔧 **Simplified Interface**: Reduced complexity with maintained functionality

**Recommended command for most users:**
```bash
thothctl inventory iac --check-versions
```

This provides comprehensive analysis with modern reporting in a single, simple command.
