# Creating and Managing Templates

Templates are a core feature of ThothCTL that enable standardized project creation, component generation, and code reuse across your organization. This document outlines how to create, manage, and use templates with ThothCTL.

## Overview

ThothCTL's template system allows you to:

1. Create standardized project structures for different types of infrastructure code
2. Enforce organizational best practices and coding standards
3. Accelerate development by providing pre-configured components
4. Maintain consistency across projects and teams
5. Define project parameters and validation rules through `.thothcf.toml` files

## Template Types

ThothCTL supports several template types:

1. **Project Templates**: Complete project structures fetched from GitHub scaffold repositories
2. **Component Templates**: Reusable infrastructure components defined in `.thothcf.toml`
3. **Stack Templates**: Templates for creating infrastructure stacks via configuration

## Template Placeholder Format

ThothCTL uses `#{parameter_name}#` expressions for parameterization in template files:

```hcl
# Template
resource "aws_vpc" "main" {
  cidr_block = "#{vpc_cidr}#"
  tags = {
    Name        = "#{project}#-vpc"
    Environment = "#{environment}#"
  }
}
```

When instantiated, placeholders are replaced with the values provided by the user.

## The `.thothcf.toml` File

The `.thothcf.toml` file is a critical component of every ThothCTL template. It defines:

1. Template input parameters and validation rules
2. Project structure requirements
3. Configuration for ThothCTL integration

### For Terraform Projects

```toml
[thothcf]
project_id = "my-project"

[template_input_parameters.project_name]
template_value = "#{project}#"
condition = "^[a-zA-Z0-9_-]+$"
description = "Project Name"

[template_input_parameters.deployment_region]
template_value = "#{backend_region}#"
condition = "^[a-z]{2}-[a-z]{4,10}-\\d$"
description = "AWS Region"

[template_input_parameters.environment]
template_value = "#{environment}#"
condition = "(dev|qa|stg|test|prod)"
description = "Environment name (dev|qa|stg|test|prod)"

# Project structure definition
[project_structure]
root_files = [".git", ".gitignore", ".pre-commit-config.yaml", "README.md"]
ignore_folders = [".git", ".terraform", "Reports"]
```

### For Terraform Modules

```toml
[template_input_parameters.module_name]
template_value = "#{ModuleName}#"
condition = "^[a-z_]+$"
description = "Module Name"

[template_input_parameters.description]
template_value = "#{ModuleDescription}#"
condition = "^[a-zA-Z\\s]+$"
description = "Module description"

[[project_structure.folders]]
name = "modules"
mandatory = true
content = ["variables.tf", "main.tf", "outputs.tf", "README.md"]
type = "root"
```

## Creating Templates

### From an Existing Project

The primary way to create a template is by converting a working project:

```bash
# Navigate to your project
cd my-terraform-project

# Convert to template
thothctl project convert --make-template --template-project-type terraform

# For Terragrunt projects
thothctl project convert --make-template --template-project-type terraform-terragrunt
```

This reads `[project_properties]` from `.thothcf.toml`, replaces values with `#{placeholder}#` expressions, and saves the template to `~/.thothcf/<project_name>/`.

### Setting Up Custom Template Repositories

Configure a custom GitHub repository as the scaffold source for a project type:

```bash
# Set a custom template URL
thothctl init template --project-type terraform --template-url https://github.com/myorg/custom-terraform.git
```

## Using Templates

### Creating Projects from Scaffold Templates

```bash
# Terraform + Terragrunt project (fetches from GitHub scaffold)
thothctl init project --project-name my-infra --project-type terraform-terragrunt

# CDK v2 project with language selection
thothctl init project --project-name my-app --project-type cdkv2 --language python

# Reuse template from VCS (Azure DevOps or GitHub space)
thothctl init project --project-name my-project --project-type terraform --reuse --space my-space
```

### Creating Projects from Local Templates

```bash
# Create project from a previously saved local template
thothctl project convert --make-project --template-project-type terraform
```

### Creating Components from Project Structure

```bash
# Create a component based on folder structure rules in .thothcf.toml
thothctl generate component \
  --component-type modules \
  --component-name networking \
  --component-path ./modules
```

### Generating Stacks from Configuration

```bash
# Generate stacks from a YAML configuration file
thothctl generate stacks --config-file stack-config.yaml

# Create an example config to get started
thothctl generate stacks --create-example
```

### Template Variables and `.thothcf.toml` Interaction

When you use a template, ThothCTL will:

1. Parse the `.thothcf.toml` file to identify required parameters
2. Prompt for values if not provided via command line
3. Validate input against the defined `condition` regex
4. Replace all occurrences of `#{parameter_name}#` in template files

### Parameter Validation

The `.thothcf.toml` file includes regex conditions to validate input parameters:

```toml
[template_input_parameters.environment]
template_value = "#{environment}#"
condition = "(dev|qa|stg|test|prod)"
description = "Environment name (dev|qa|stg|test|prod)"
```

If a provided value doesn't match the condition, ThothCTL will show an error and prompt for a valid value.

## Managing Templates

### Storage Locations

| Location | Purpose |
|----------|---------|
| `~/.thothcf/<project_name>/` | Saved template files (from `--make-template`) |
| `~/.thothcf/.thothcf.toml` | Global template registry with file hashes |
| `~/.thothcf/.thothctl_templates.toml` | Custom template URL overrides |

### Listing Available Templates

```bash
# Show available templates
thothctl list templates

# Show templates from a specific space
thothctl list templates --space my-space
```

### Upgrading Projects from Templates

Keep projects in sync with template updates:

```bash
# Check what would change
thothctl project upgrade --dry-run

# Interactive file selection
thothctl project upgrade --interactive

# Force upgrade
thothctl project upgrade --force
```

## Template Integration with Spaces

Templates can be associated with specific spaces via VCS providers (GitHub, Azure DevOps):

```bash
# Initialize a space
thothctl init space --space-name development

# Create project reusing a template from the space
thothctl init project --project-name my-project --project-type terraform --reuse --space development
```

Projects created within a space can discover templates from the space's VCS provider.

## `.thothcf.toml` Reference

### Template Input Parameters Section

```toml
[template_input_parameters.parameter_name]
template_value = "#{ParameterName}#"   # Placeholder in template files
condition = "regex_pattern"             # Validation regex
description = "Human-readable prompt"   # Shown during parameter input
```

### Project Structure Section

```toml
[project_structure]
root_files = [".gitignore", "README.md"]
ignore_folders = [".git", ".terraform"]

[[project_structure.folders]]
name = "modules"
mandatory = true
type = "root"
content = ["main.tf", "variables.tf", "outputs.tf"]
```

## Best Practices

1. **Keep parameters meaningful** — Use descriptive names and provide helpful descriptions
2. **Validate strictly** — Define specific regex patterns to catch errors early
3. **Document templates** — Include README and architecture docs in your templates
4. **Version control** — Store templates in Git repositories with semantic versioning
5. **Test conversions** — Always test `make-project` after creating a template
6. **Define structure** — Use `[project_structure]` to enforce required files and folders

## Related Documentation

- [Template Engine Overview](../../template_engine/template_engine.md)
- [GitHub Templates](../../template_engine/github_templates.md)
- [Project Convert](../commands/project/project_convert.md)
- [Project Upgrade](../commands/project/project_upgrade.md)
- [Platform Engineering Templates](../platform_engineering_templates.md)
