# Document IaC Command

## Overview

The `document iac` command generates comprehensive documentation for Infrastructure as Code projects using terraform-docs and AI-powered documentation generation.

## Usage

```bash
# Basic documentation generation
thothctl document iac -f terraform-terragrunt

# Recursive documentation
thothctl document iac -f terraform-terragrunt --recursive

# Custom configuration
thothctl document iac -f terraform --config-file .terraform-docs.yml
```

## Features

- **Automatic Documentation**: Generate README files for modules
- **Terraform-docs Integration**: Professional module documentation
- **AI-Powered Docs**: Generative AI documentation creation
- **Graph Generation**: Dependency graphs and visualizations
- **Multi-Framework Support**: Terraform, Terragrunt, CDK

## Supported Frameworks

- **terraform**: Pure Terraform projects
- **terragrunt**: Terragrunt-based projects
- **terraform-terragrunt**: Mixed environments

## Output

The command generates:
- README.md files for each module
- Dependency graphs (SVG format)
- Input/output documentation
- Usage examples

## Examples

### Generate Module Documentation
```bash
thothctl document iac -f terraform-terragrunt
```

### Recursive Documentation
```bash
thothctl document iac -f terraform-terragrunt --recursive
```

### Custom Configuration
```bash
thothctl document iac -f terraform --config-file custom-docs.yml
```

## Related Commands

- [`check iac`](../check/check_iac.md) - Validate structure
- [`inventory iac`](../inventory/iac.md) - Create inventory
- [`scan iac`](../scan/iac.md) - Security scanning
