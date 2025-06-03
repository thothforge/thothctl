# Document Command

The `document` command in ThothCTL provides tools to automatically generate documentation for your projects. It helps maintain up-to-date documentation that accurately reflects your codebase, saving time and ensuring consistency.

## Overview

The document command helps developers and teams to:

- Generate comprehensive documentation for Infrastructure as Code (IaC) resources
- Keep documentation synchronized with code changes
- Standardize documentation format across projects
- Improve code maintainability and knowledge sharing

## Subcommands

Currently, ThothCTL supports the following document subcommands:

- `iac` - Generate documentation for Infrastructure as Code resources (Terraform, Terragrunt)

## Basic Usage

```bash
# Generate documentation for Terraform code
thothctl document iac -f terraform

# Generate documentation for Terragrunt code
thothctl document iac -f terragrunt

# Generate documentation recursively
thothctl document iac -f terraform --recursive
```

## Common Options

| Option | Description |
|--------|-------------|
| `-f, --framework` | Specify the IaC framework to document (terraform, terragrunt, terraform-terragrunt) |
| `--recursive` | Generate documentation recursively for all modules/components |
| `--config-file` | Path to a custom configuration file for the documentation generator |

## Benefits of Automated Documentation

1. **Consistency**: Ensures documentation follows a standard format across all projects
2. **Accuracy**: Documentation is generated directly from code, reducing discrepancies
3. **Efficiency**: Saves time by automating the documentation process
4. **Maintainability**: Makes it easier to keep documentation up-to-date as code changes
5. **Collaboration**: Improves team collaboration with clear, accessible documentation

## Next Steps

For more detailed information about documenting Infrastructure as Code, see the [IaC Documentation](document_iac.md) page.
