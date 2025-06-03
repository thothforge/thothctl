# Terragrunt Framework Support

## Overview

ThothCTL's inventory command now provides comprehensive support for Terragrunt projects. It can analyze Terragrunt files (`terragrunt.hcl`) to create an inventory of all modules, their versions, sources, and dependencies.

## Terragrunt Module Detection

The inventory command scans all `terragrunt.hcl` files in your project directory (excluding `.terragrunt-cache` directories) and extracts module information from them. It identifies:

- Module references in `terraform { source = "..." }` blocks
- Version constraints from source URLs
- Source locations
- File paths

## Example Terragrunt Module

```hcl
terraform {
  source = "tfr:///terraform-aws-modules/alb/aws?version=8.7.0"
}

inputs = {
  create_lb          = true
  name               = "test-alb"
  vpc_id             = "vpc-12345"
  load_balancer_type = "application"
  internal           = true
}
```

From this module definition, the inventory command extracts:

- **Type**: `terragrunt_module`
- **Name**: `aws`
- **Version**: `8.7.0`
- **Source**: `terraform-aws-modules/alb/aws`
- **File**: Path to the terragrunt.hcl file

## Version Checking

When used with the `--check-versions` flag, the inventory command checks if your modules are using the latest available versions:

```bash
thothctl inventory iac --framework-type terragrunt --check-versions
```

This connects to the Terraform Registry API to check for the latest versions of your modules and identifies which ones are outdated.

## Supported Source Formats

The inventory command supports various Terragrunt source formats:

- **Terraform Registry**: `tfr:///terraform-aws-modules/alb/aws?version=8.7.0`
- **GitHub References**: `git::https://github.com/org/repo.git?ref=v1.0.0`
- **Local Modules**: `../modules/my-module`
- **Direct References**: `terraform-aws-modules/vpc/aws`

## Cache Directory Exclusion

The inventory command automatically excludes `.terragrunt-cache` directories when scanning for Terragrunt files. This prevents duplicate modules from being included in the inventory and ensures accurate results.

## Specifying Terragrunt Framework

To explicitly analyze only Terragrunt files, use the `--framework-type terragrunt` option:

```bash
thothctl inventory iac --framework-type terragrunt
```

This will ignore any Terraform files in your project and focus only on Terragrunt files.

## Mixed Framework Support

If your project uses both Terraform and Terragrunt files, you can use the `--framework-type terraform-terragrunt` option:

```bash
thothctl inventory iac --framework-type terraform-terragrunt
```

This will analyze both Terraform and Terragrunt files in your project.

## Best Practices for Terragrunt Projects

1. **Use Explicit Versions**: Always specify explicit versions in your source URLs
2. **Organize by Component**: Group related components in directories
3. **Regular Inventory**: Create inventories regularly to track changes over time
4. **Version Checking**: Use `--check-versions` to identify outdated modules
5. **Documentation**: Generate HTML reports for better documentation

## Example Workflow

```bash
# Create an inventory of your Terragrunt project
thothctl inventory iac --framework-type terragrunt

# Check for outdated modules
thothctl inventory iac --framework-type terragrunt --check-versions

# Generate comprehensive reports
thothctl inventory iac --framework-type terragrunt --check-versions --report-type all

# Update modules to latest versions
thothctl inventory iac --framework-type terragrunt --inventory-action update --inventory-path ./Reports/Inventory/InventoryIaC_20250602_121227.json
```

## Related Documentation

- [Inventory Command Overview](../inventory_overview.md): General information about the inventory command
- [IaC Inventory](../inventory_iac.md): Detailed documentation for the inventory iac command
- [Terraform Framework Support](terraform.md): Information about Terraform support
