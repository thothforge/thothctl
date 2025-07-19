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

1. **Project Templates**: Complete project structures with predefined directories and files
2. **Component Templates**: Reusable infrastructure components like modules or services
3. **Stack Templates**: Templates for creating infrastructure stacks
4. **Custom Templates**: User-defined templates for specific organizational needs

## Template Structure
https://github.com/velez94/terragrunt_ecs_blueprint.git
A template in ThothCTL is defined as a hierarchical structure of directories and files:

```python
template = [
    {
        "type": "directory",
        "name": ".",
        "contents": [
            {"type": "file", "name": "README.md"},
            {"type": "file", "name": ".thothcf.toml"},
            {
                "type": "directory",
                "name": "modules",
                "contents": [
                    {"type": "file", "name": "main.tf"},
                    {"type": "file", "name": "variables.tf"},
                ]
            }
        ]
    }
]
```

### The `.thothcf.toml` File

The `.thothcf.toml` file is a critical component of every ThothCTL template. It defines:

1. Template input parameters and validation rules
2. Project structure requirements
3. Configuration for ThothCTL integration

Each template type has a specific `.thothcf.toml` structure:

#### For Terraform Projects:

```toml
[template_input_parameters.project_name]
template_value = "test-wrapper"
condition = "\\b[a-zA-Z]+\\b"
description = "Project Name"

[template_input_parameters.deployment_region]
template_value = "us-east-2"
condition = "^[a-z]{2}-[a-z]{4,10}-\\d$"
description = "AWS Region"

[template_input_parameters.environment]
template_value = "dev"
condition = "(dev|qa|stg|test|prod)"
description = "Environment name (dev|qa|stg|test|prod)"

# Project structure definition
[project_structure]
root_files = [
   ".git",
    ".gitignore",
    ".pre-commit-config.yaml",
    "README.md"
]
ignore_folders = [
    ".git",
    ".terraform",
    "Reports"
]
```

#### For Terraform Modules:

```toml
[template_input_parameters.module_name]
template_value = "#{ModuleName}#"
condition = "^[a-z_]+$"
description = "Module Name"

[template_input_parameters.description]
template_value= "#{ModuleDescription}#"
condition = "^[a-zA-Z\\s]+$"
description = "Module description"

# Project structure definition
[[project_structure.folders]]
name = "modules"
mandatory = true
content = [
    "variables.tf",
    "main.tf",
    "outputs.tf",
    "README.md"
]
type= "root"
```

## Creating Templates

### Using the CLI

You can create a new template using the `thothctl generate template` command:

```bash
thothctl generate template --template-name my-terraform-template --template-type terraform
```

This will create a new template with the standard structure for the specified type.

### Template Configuration

Templates are configured using a YAML file with the following structure:

```yaml
name: my-terraform-template
type: terraform
description: A template for Terraform projects
version: 1.0.0
author: Your Name
files:
  - path: README.md
    content: |
      # My Terraform Project
      
      This is a template for Terraform projects.
  - path: main.tf
    content: |
      # Main Terraform configuration
  - path: .thothcf.toml
    content: |
      [template_input_parameters.project_name]
      template_value = "test-wrapper"
      condition = "\\b[a-zA-Z]+\\b"
      description = "Project Name"
```

### Custom Template Content

You can customize the content of template files by:

1. Editing the template configuration file
2. Using variables in template files that will be replaced during generation
3. Adding hooks for post-generation actions

## Managing Templates

### Storing Templates

Templates can be stored in:

1. **Local Repository**: `~/.thothctl/templates/`
2. **Git Repository**: Remote repository for sharing across teams
3. **Template Registry**: Central registry for organization-wide templates

### Versioning Templates

Templates should follow semantic versioning:

```yaml
name: my-terraform-template
version: 1.0.0
```

When updating templates, increment:
- MAJOR version for incompatible changes
- MINOR version for new features
- PATCH version for bug fixes

### Publishing Templates

To publish a template to a shared repository:

```bash
thothctl template publish --template-name my-terraform-template --repository https://github.com/myorg/templates
```

## Using Templates

### Creating Projects from Templates

```bash
thothctl init project --project-name my-project --template my-terraform-template
```

### Creating Components from Templates

```bash
thothctl generate component --component-name network --template network-module
```

### Template Variables and `.thothcf.toml` Interaction

The `.thothcf.toml` file defines template variables that are replaced during generation:

```toml
[template_input_parameters.project_name]
template_value = "test-wrapper"
condition = "\\b[a-zA-Z]+\\b"
description = "Project Name"
```

When you use a template, ThothCTL will:

1. Parse the `.thothcf.toml` file to identify required parameters
2. Prompt for values if not provided via command line
3. Validate input against the defined conditions
4. Replace all occurrences of `#{parameter_name}#` in template files

Example command with variables:

```bash
thothctl generate component --component-name s3-bucket --template s3-module --variables '{"bucket_name": "my-unique-bucket", "environment": "dev"}'
```

### Parameter Validation

The `.thothcf.toml` file includes regex conditions to validate input parameters:

```toml
[template_input_parameters.environment]
template_value = "dev"
condition = "(dev|qa|stg|test|prod)"
description = "Environment name (dev|qa|stg|test|prod)"
```

If a provided value doesn't match the condition, ThothCTL will:
1. Show an error message
2. Display the parameter description
3. Prompt for a valid value

## Template Best Practices

1. **Documentation**: Include comprehensive README files in templates
2. **Modularity**: Design templates to be composable and reusable
3. **Validation**: Include validation rules for generated code
4. **Testing**: Provide example usage and test cases
5. **Compliance**: Embed security and compliance checks
6. **Consistency**: Maintain consistent naming conventions and structure
7. **`.thothcf.toml` Structure**: 
   - Keep parameter names descriptive
   - Use specific regex patterns for validation
   - Include helpful descriptions for each parameter
   - Define mandatory project structure elements

## Template Integration with Spaces

Templates can be associated with specific spaces to ensure consistent standards:

```bash
thothctl init space --space-name development --default-templates terraform-dev,module-standard
```

Projects created within a space will automatically use the space's default templates unless overridden.

## Example: Creating a Custom Template

1. Create a template configuration file:

```bash
cat > my-template.yaml << EOF
name: custom-terraform-module
type: terraform_module
description: Custom Terraform module template
version: 1.0.0
author: Your Name
EOF
```

2. Define the template structure:

```bash
thothctl generate template --config-file my-template.yaml --output-dir ./templates
```

3. Customize the template files in `./templates`

4. Create or modify the `.thothcf.toml` file:

```bash
cat > ./templates/.thothcf.toml << EOF
[template_input_parameters.module_name]
template_value = "#{ModuleName}#"
condition = "^[a-z_]+$"
description = "Module Name"

[template_input_parameters.resources_to_create]
template_value= "#{ResourcesToCreate}#"
condition= "^[a-zA-Z\\\\s]+$"
description = "Resources to create in this module"

[project_structure]
root_files = [
   ".gitignore",
   "README.md",
   "main.tf",
   "variables.tf",
   "outputs.tf"
]

[[project_structure.folders]]
name = "examples"
mandatory = true
type= "root"
EOF
```

5. Register the template:

```bash
thothctl template register --template-path ./templates
```

6. Use the template:

```bash
thothctl generate component --component-name my-component --template custom-terraform-module
```

## `.thothcf.toml` File Reference

### Template Input Parameters Section

Each parameter is defined with:

```toml
[template_input_parameters.parameter_name]
template_value = "#{ParameterName}#"  # The placeholder in template files
condition = "regex_pattern"           # Validation regex pattern
description = "Parameter description"  # Human-readable description
```

### Project Structure Section

Defines required files and directories:

```toml
[project_structure]
root_files = [                        # Required files in root directory
   ".gitignore",
   "README.md"
]
ignore_folders = [                    # Folders to ignore during validation
    ".git",
    ".terraform"
]

[[project_structure.folders]]         # Required folder definition
name = "examples"                     # Folder name
mandatory = true                      # Is this folder required?
type = "root"                         # Location (root or child_folder)
content = [                           # Required files in this folder
    "main.tf",
    "README.md"
]
```

## Conclusion

Templates are a powerful feature of ThothCTL that enable standardization, acceleration, and consistency in your infrastructure code. The `.thothcf.toml` file is central to this functionality, providing parameter validation, structure definition, and configuration for your templates. By creating and managing templates effectively, you can significantly improve developer productivity and code quality across your organization.
