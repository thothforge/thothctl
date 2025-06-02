# ThothCTL Generate Components

## Overview

The `thothctl generate component` command allows you to create infrastructure components according to project rules and conventions. This command helps maintain consistency across your infrastructure codebase by generating components with standardized structure and configuration.

## Use Cases

- **Standardized Component Creation**: Ensure all infrastructure components follow the same structure and conventions
- **Accelerated Development**: Quickly create new infrastructure components without manual setup
- **Consistent Naming**: Enforce naming conventions across your infrastructure codebase
- **Project Rule Compliance**: Ensure components adhere to your organization's best practices

## Command Options

```
Usage: thothctl generate component [OPTIONS]

  Create IaC component according to project rules and conventions

Options:
  -ct, --component-type TEXT  Component Type for base template, there are the
                              names for your folder in folders field in
                              .thothcf.toml
  -cn, --component-name TEXT  Component name for template
  -cph, --component-path TEXT  Component path for base template, for example
                              ./modules
  --help                      Show this message and exit.
```

## Basic Usage

To generate a new component:

```bash
thothctl generate component --component-type module --component-name network --component-path ./modules
```

This will create a new component named "network" of type "module" in the "./modules" directory.

## Component Types

Component types are defined in your project's `.thothcf.toml` file under the `project_structure.folders` section. Each folder entry with `type = "root"` or `type = "child_folder"` can be used as a component type.

Example component types:
- `module`: For reusable Terraform modules
- `stack`: For Terragrunt stacks
- `service`: For application services
- `resource`: For individual infrastructure resources

## Project Structure Configuration

The component structure is defined in your project's `.thothcf.toml` file. Here's an example configuration:

```toml
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

[[project_structure.folders]]
name = "modules"
mandatory = false
content = [
    "variables.tf",
    "main.tf",
    "outputs.tf",
    "README.md"
]
type= "root"

[[project_structure.folders]]
name = "examples"
mandatory = true
type= "root"
content = [
    "main.tf",
    "outputs.tf",
    "terraform.tfvars",
    "README.md",
    "variables.tf",
]
```

## Generated Structure

For a component of type "module" named "network", the command will generate:

```
modules/
└── network/
    ├── main.tf
    ├── variables.tf
    ├── outputs.tf
    └── README.md
```

Each file will be populated with appropriate content based on templates defined in the system.

## File Templates

The content of generated files is based on templates defined in the system. For example:

### main.tf
```hcl
/*
* # Module for network deployment
*
* Terraform stack to provision a custom network
*
*/
```

### variables.tf
```hcl
variable "vpc_cidr" {
  description = "The CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "environment" {
  description = "Environment name"
  type        = string
}
```

## Advanced Features

### Component Hierarchy

Components can have parent-child relationships defined in the `.thothcf.toml` file:

```toml
[[project_structure.folders]]
name = "modules"
mandatory = false
type= "root"

[[project_structure.folders]]
name = "networking"
mandatory = false
parent = "modules"
type = "child"
content = [
    "main.tf",
    "variables.tf",
    "outputs.tf"
]
```

When generating a component of type "networking", it will be created as a child of the "modules" folder.

### Template Substitution

The command supports template substitution in generated files. For example, `#{resource_name}#` in templates will be replaced with the component name.

## Examples

### Generate a Terraform Module

```bash
thothctl generate component --component-type module --component-name vpc --component-path ./modules
```

### Generate a Terragrunt Stack

```bash
thothctl generate component --component-type stack --component-name database --component-path ./stacks
```

### Generate a Service Component

```bash
thothctl generate component --component-type service --component-name api --component-path ./services
```

## Best Practices

1. **Consistent Component Types**: Define a standard set of component types for your organization
2. **Standardized File Structure**: Ensure each component type has a consistent file structure
3. **Documentation**: Include README.md files in your component templates
4. **Version Control**: Commit generated components to version control
5. **Component Testing**: Include test files in your component templates

## Troubleshooting

### Common Issues

- **Invalid Component Type**: Ensure the component type exists in your `.thothcf.toml` file
- **Missing Template Files**: Check that all required template files are available
- **Permission Issues**: Ensure you have write permissions to the component path
- **Duplicate Components**: Check if a component with the same name already exists

### Debugging

For more detailed logs, run ThothCTL with the `--debug` flag:

```bash
thothctl --debug generate component --component-type module --component-name network
```
