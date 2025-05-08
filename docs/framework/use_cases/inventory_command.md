# ThothCTL Inventory Command

## Overview

The `thothctl inventory` command creates, manages, and updates inventories of your infrastructure components. This command helps you track modules, their versions, sources, and dependencies, providing valuable insights into your infrastructure composition and enabling version management.

## Available Inventory Commands

### inventory iac

Creates an inventory of Infrastructure as Code (IaC) components in your project.

```bash
thothctl inventory iac [OPTIONS]
```

Options:
- `-iph, --inventory-path PATH`: Path for saving inventory reports (default: ./Reports/Inventory)
- `-ch, --check-versions`: Check remote versions
- `-updep, --update-dependencies-path`: Pass the inventory json file path for updating dependencies
- `-auto, --auto-approve`: Use with --update_dependencies option for auto approve updating dependencies
- `-iact, --inventory-action [create|update|restore]`: Action for inventory tasks (default: create)
- `--report-type, -r [html|json|all]`: Type of report to generate (default: html)

[Detailed documentation for inventory iac](commands/inventory/inventory_iac.md)

## Basic Usage

### Create an Inventory

```bash
thothctl inventory iac
```

This creates an inventory of all IaC components in the current directory and generates an HTML report in the default location (`./Reports/Inventory`).

### Create an Inventory with Version Checking

```bash
thothctl inventory iac --check-versions
```

This creates an inventory and checks if the modules are using the latest available versions.

### Generate Different Report Types

```bash
thothctl inventory iac --report-type json
```

This creates an inventory and generates a JSON report.

```bash
thothctl inventory iac --report-type all
```

This creates an inventory and generates both HTML and JSON reports.

## Inventory Actions

The command supports three main actions:

### 1. Create (Default)

```bash
thothctl inventory iac --inventory-action create
```

This action scans your IaC files and creates a new inventory.

### 2. Update

```bash
thothctl inventory iac --inventory-action update --inventory-path ./path/to/inventory.json
```

This action updates your IaC files based on the inventory. It can be used to apply version updates or other changes.

### 3. Restore

```bash
thothctl inventory iac --inventory-action restore --inventory-path ./path/to/inventory.json
```

This action restores your IaC files to the state recorded in the inventory.

## Inventory Reports

The command generates detailed reports about your infrastructure components:

### HTML Report

The HTML report includes:
- Project overview
- Module list with versions and sources
- Dependency graph visualization
- Version status (latest vs. current)
- File locations

### JSON Report

The JSON report contains structured data about your infrastructure:
```json
{
  "project_name": "my-project",
  "components": [
    {
      "stack": "./modules",
      "components": [
        {
          "type": "module",
          "name": "vpc",
          "version": "3.14.0",
          "source": "terraform-aws-modules/vpc/aws",
          "file": "modules/main.tf",
          "status": "Latest"
        }
      ]
    }
  ],
  "version_checks": {
    "total": 5,
    "latest": 3,
    "outdated": 2
  }
}
```

## Use Cases

### Infrastructure Auditing

Create an inventory to audit your infrastructure components:

```bash
thothctl inventory iac --check-versions --report-type all
```

### Version Management

Identify outdated modules and update them:

```bash
# First create an inventory with version checking
thothctl inventory iac --check-versions --report-type json

# Then update modules to latest versions
thothctl inventory iac --inventory-action update --inventory-path ./Reports/Inventory/inventory.json
```

### Documentation

Generate documentation about your infrastructure:

```bash
thothctl inventory iac --report-type html
```

### Disaster Recovery

Create regular inventories for disaster recovery purposes:

```bash
thothctl inventory iac --report-type all --inventory-path ./backups/$(date +%Y-%m-%d)
```

## Examples

### Basic Inventory Creation

```bash
thothctl inventory iac
```

### Comprehensive Inventory with Version Checking

```bash
thothctl inventory iac --check-versions --report-type all --inventory-path ./docs/inventory
```

### Update Infrastructure to Latest Versions

```bash
# First create an inventory with version checking
thothctl inventory iac --check-versions --report-type json

# Then update modules to latest versions
thothctl inventory iac --inventory-action update --inventory-path ./Reports/Inventory/inventory.json
```

### Restore Infrastructure from Backup

```bash
thothctl inventory iac --inventory-action restore --inventory-path ./backups/2023-01-01/inventory.json
```

## Best Practices

1. **Regular Inventories**: Create inventories regularly to track changes over time
2. **Version Checking**: Use `--check-versions` to identify outdated modules
3. **Multiple Report Types**: Use `--report-type all` to generate both HTML and JSON reports
4. **Backup Inventories**: Store inventories in a version-controlled location
5. **CI/CD Integration**: Add inventory creation to your CI/CD pipeline

## Troubleshooting

### Common Issues

#### No Components Found

```
Warning: No components found in the specified directory.
```

**Solution**: Ensure you're running the command in a directory containing Terraform (`.tf`) files.

#### Version Checking Failures

```
Error: Failed to check versions for module xyz
```

**Solution**: Ensure you have internet connectivity and the module source is accessible.

#### Report Generation Failures

```
Error: Failed to generate HTML report
```

**Solution**: Ensure you have write permissions to the output directory.

### Debugging

For more detailed logs, run ThothCTL with the `--debug` flag:

```bash
thothctl --debug inventory iac
```

## Related Commands

- [thothctl check iac](commands/check/check_iac.md): Check IaC components against best practices
- [thothctl scan](commands/scan/scan.md): Scan infrastructure code for security issues
