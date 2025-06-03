# Terraform Framework Support

## Overview

ThothCTL's inventory command provides comprehensive support for Terraform projects. It can analyze Terraform files (`.tf`) to create an inventory of all modules, their versions, sources, and dependencies.

## Terraform Module Detection

The inventory command scans all `.tf` files in your project directory and extracts module information from them. It identifies:

- Module references
- Version constraints
- Source locations
- File paths

## Example Terraform Module

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "3.14.0"

  name = "my-vpc"
  cidr = "10.0.0.0/16"
}
```

From this module definition, the inventory command extracts:

- **Type**: `module`
- **Name**: `vpc`
- **Version**: `3.14.0`
- **Source**: `terraform-aws-modules/vpc/aws`
- **File**: Path to the file containing this module

## Version Checking

When used with the `--check-versions` flag, the inventory command checks if your modules are using the latest available versions:

```bash
thothctl inventory iac --framework-type terraform --check-versions
```

This connects to the Terraform Registry API to check for the latest versions of your modules and identifies which ones are outdated.

## Supported Source Formats

The inventory command supports various Terraform module source formats:

- **Terraform Registry**: `terraform-aws-modules/vpc/aws`
- **GitHub**: `github.com/terraform-aws-modules/terraform-aws-vpc`
- **Local Paths**: `../modules/vpc`
- **Git URLs**: `git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git?ref=v3.14.0`

## Specifying Terraform Framework

To explicitly analyze only Terraform files, use the `--framework-type terraform` option:

```bash
thothctl inventory iac --framework-type terraform
```

This will ignore any Terragrunt files in your project and focus only on Terraform files.

## Best Practices for Terraform Projects

1. **Use Explicit Versions**: Always specify explicit versions for your modules to ensure reproducible builds
2. **Organize Modules**: Group related modules in directories to improve organization
3. **Regular Inventory**: Create inventories regularly to track changes over time
4. **Version Checking**: Use `--check-versions` to identify outdated modules
5. **Documentation**: Generate HTML reports for better documentation

## Example Workflow

```bash
# Create an inventory of your Terraform project
thothctl inventory iac --framework-type terraform

# Check for outdated modules
thothctl inventory iac --framework-type terraform --check-versions

# Generate comprehensive reports
thothctl inventory iac --framework-type terraform --check-versions --report-type all

# Update modules to latest versions
thothctl inventory iac --framework-type terraform --inventory-action update --inventory-path ./Reports/Inventory/InventoryIaC_20250602_121227.json
```

## Related Documentation

- [Inventory Command Overview](../inventory_overview.md): General information about the inventory command
- [IaC Inventory](../inventory_iac.md): Detailed documentation for the inventory iac command
- [Terragrunt Framework Support](terragrunt.md): Information about Terragrunt support
