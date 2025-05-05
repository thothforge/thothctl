# ThothCTL Inventory Commands

## Overview

The `thothctl inventory` command group provides tools for creating, managing, and updating inventories of your infrastructure components. These inventories help you track modules, their versions, sources, and dependencies, providing valuable insights into your infrastructure composition.

## Available Inventory Commands

### [inventory iac](inventory_iac.md)

Creates an inventory of Infrastructure as Code (IaC) components in your project.

```bash
thothctl inventory iac [OPTIONS]
```

This command scans your Terraform/OpenTofu files and creates a detailed inventory of all modules, their versions, sources, and dependencies.

## Common Options

Most inventory commands support the following options:

- **--inventory-path PATH**: Specifies where to save inventory reports
- **--check-versions**: Checks if modules are using the latest available versions
- **--report-type [html|json|all]**: Specifies the type of report to generate

## Inventory Actions

The inventory commands support three main actions:

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

## Inventory Reports

The inventory commands generate detailed reports about your infrastructure components:

### HTML Report

The HTML report includes:
- Project overview
- Module list with versions and sources
- Dependency graph visualization
- Version status (latest vs. current)
- File locations

### JSON Report

The JSON report contains structured data about your infrastructure that can be used for further processing or integration with other tools.

## Best Practices

1. **Regular Inventories**: Create inventories regularly to track changes over time
2. **Version Checking**: Use `--check-versions` to identify outdated modules
3. **Multiple Report Types**: Use `--report-type all` to generate both HTML and JSON reports
4. **Backup Inventories**: Store inventories in a version-controlled location
5. **CI/CD Integration**: Add inventory creation to your CI/CD pipeline

## Extending Inventory Commands

ThothCTL's inventory commands can be extended with custom inventory types. To create a custom inventory type:

1. Create a new Python file in the `src/thothctl/services/inventory/` directory
2. Implement the inventory logic
3. Create a new command file in `src/thothctl/commands/inventory/commands/`
4. Register your inventory type with the command

## Related Documentation

- [Infrastructure as Code Best Practices](../../iac_best_practices.md): Best practices for IaC
- [Version Management](../../version_management.md): Guidelines for managing module versions
