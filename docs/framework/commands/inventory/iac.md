# Inventory IaC Command

## Overview

The `inventory iac` command creates comprehensive inventories of your Infrastructure as Code projects, tracking dependencies, versions, and components.

## Usage

```bash
# Basic inventory creation
thothctl inventory iac

# Check versions
thothctl inventory iac --check-versions

# Generate HTML report
thothctl inventory iac --check-versions --project-name "My Project"
```

## Features

- **Component Tracking**: Catalog all IaC components
- **Version Management**: Track provider and module versions
- **Dependency Mapping**: Map component relationships
- **Professional Reports**: Generate HTML and JSON reports
- **Update Detection**: Identify outdated components

## Output Formats

- **HTML**: Professional reports with styling
- **JSON**: Machine-readable inventory data
- **Terminal**: Colored output with status indicators

## Examples

### Create Basic Inventory
```bash
thothctl inventory iac
```

### Version Analysis
```bash
thothctl inventory iac --check-versions
```

### Professional Report
```bash
thothctl inventory iac --check-versions --project-name "Production Infrastructure"
```

## Related Commands

- [`check iac`](../check/check_iac.md) - Validate IaC structure
- [`scan iac`](../scan/iac.md) - Security scanning
- [`document iac`](../document/iac.md) - Generate documentation
