# Init Command
Use this command to Initialize a project, environment, or space.

```bash
thothctl init --help
Usage: thothctl init [OPTIONS] COMMAND [ARGS]...

  Initialize and setup project configurations

Options:
  --help  Show this message and exit.

Commands:
  env      Initialize a development environment with required tools and...
  project  Initialize a new project
  space    Initialize a new space
```

# ThothCTL Init Project Command

## Overview

The `thothctl init project` command initializes a new project with the ThothCTL framework. This command creates the necessary project structure, configuration files, and optionally sets up version control integration. Projects can be associated with spaces for consistent configuration and credential management.

## Command Options

```
Usage: thothctl init project [OPTIONS]

  Initialize a new project

Options:
  -p, --project-name TEXT        Name of the project  [required]
  -pt, --project-type [terraform|tofu|cdkv2|terraform_module|terragrunt|custom]
                                 Type of project to create  [default: terraform]
  -sc, --setup-conf              Setup project configuration  [default: True]
  -vcss, --version-control-systems-service [azure_repos|github|gitlab]
                                 The Version Control System Service for you IDP
                                 [default: azure_repos]
  -reuse, --reuse                Reuse templates, pattern, PoC, projects and
                                 more from your IDP catalog
  -az-org, --az-org-name TEXT    Azure organization name (for Azure Repos)
  -gh-user, --github-username TEXT
                                 GitHub username or organization (for GitHub)
  -s, --space TEXT               Space name for the project (used for loading
                                 credentials and configurations)
  --batch                        Run in batch mode with minimal prompts and use
                                 default values where possible
  --help                         Show this message and exit.
```

## Basic Usage

### Create a Basic Terraform Project

```bash
thothctl init project --project-name my-terraform-project
```

This creates a new Terraform project with the default structure.

### Create a Project with Configuration Setup

```bash
thothctl init project --project-name my-project --setup_conf
```

This creates a new project and sets up the `.thothcf.toml` configuration file.

### Create a Project in a Space

```bash
thothctl init project --project-name my-project --space development
```

This creates a new project in the "development" space, inheriting the space's configurations.

### Create a Project with a Specific Type

```bash
thothctl init project --project-name my-cdk-project --project-type cdkv2
```

This creates a new project using the CDKv2 template.

### Create a Terragrunt Project

```bash
thothctl init project --project-name my-terragrunt-project --project-type terragrunt --space development
```

This creates a new Terragrunt project in the "development" space with the appropriate structure for Terragrunt orchestration.

## Project Types

ThothCTL supports the following project types:

- **terraform**: Standard Terraform project (default)
- **tofu**: OpenTofu project
- **cdkv2**: AWS CDK v2 project
- **terraform_module**: Terraform module project
- **terragrunt**: Terragrunt project with orchestration structure
- **custom**: Custom project structure

Each project type has a predefined structure and set of files that will be created.

## Project Structure

When you initialize a project, ThothCTL creates the following structure:

### Terraform Project (Default)

```
my-project/
├── .gitignore
├── .pre-commit-config.yaml
├── .thothcf.toml
├── .tflint.hcl
├── common/
│   ├── common.hcl
│   └── common.tfvars
├── README.md
└── root.hcl
```

### Terragrunt Project

```
my-terragrunt-project/
├── .gitignore
├── .pre-commit-config.yaml
├── .thothcf.toml
├── .tflint.hcl
├── README.md
├── root.hcl
├── common/
│   ├── common.hcl
│   ├── common.tfvars
│   └── variables.tf
├── docs/
│   ├── DiagramArchitecture.png
│   └── graph.svg
├── modules/
│   ├── main.tf
│   ├── outputs.tf
│   ├── README.md
│   └── variables.tf
└── stacks/
    ├── README.md
    ├── terragrunt.hcl
    ├── graph.svg
    └── compute/
        └── EC2/
            └── ALB_Main/
                ├── README.md
                ├── terragrunt.hcl
                └── graph.svg
```

## Configuration Files

### .thothcf.toml

The main configuration file for ThothCTL projects:

```toml
[template_input_parameters.project_name]
template_value = "my-project"
condition = "\b[a-zA-Z]+\b"
description = "Project Name"

[template_input_parameters.deployment_region]
template_value = "us-east-1"
condition = "^[a-z]{2}-[a-z]{4,10}-\d$"
description = "AWS Region"

# Additional configuration parameters...

[thothcf]
version = "1.0.0"
space = "development"  # If project is in a space
```

## Integration with Spaces

When you create a project within a space using the `--space` option, the project inherits:

1. **Version Control System Configuration**: The project uses the VCS provider configured for the space
2. **Terraform Registry Settings**: The project uses the Terraform registry and authentication method from the space
3. **Orchestration Tool Configuration**: The project uses the orchestration tool (e.g., Terragrunt, Terramate) configured for the space

This ensures consistency across all projects within the same space.

## Azure DevOps Integration

ThothCTL supports integration with Azure DevOps for template reuse and repository setup.

### List Available Templates

```bash
thothctl init project --project-name my-project --reuse --az-org-name my-organization -r -list
```

This lists all available templates in your Azure DevOps organization.

### Reuse a Template

```bash
thothctl init project --project-name my-project --reuse --az-org-name my-organization
```

This prompts you to select a template from your Azure DevOps organization and creates a project based on that template.

## Advanced Features

### Project Properties

When setting up a project configuration, ThothCTL collects and stores the following properties:

- Project name
- Cloud provider
- Deployment region
- Backend configuration (bucket, region, profile)
- Environment settings
- Owner information
- Client information

These properties are used for template substitution and configuration generation.

### Template Substitution

ThothCTL supports template substitution in project files. For example, `test-wrapper` in templates will be replaced with the actual project name.

## Examples

### Basic Terraform Project

```bash
thothctl init project --project-name terraform-vpc --project-type terraform --setup-conf
```

### Terraform Module in a Space

```bash
thothctl init project --project-name vpc-module --project-type terraform_module --space shared-modules
```

### Terragrunt Project with Batch Mode

```bash
thothctl init project --project-name terragrunt-infra --project-type terragrunt --space production --batch
```

### CDK Project with GitHub Integration

```bash
thothctl init project --project-name cdk-app --project-type cdkv2 --reuse --github-username my-organization
```

## Best Practices

1. **Use Spaces**: Organize related projects within spaces for consistent configuration
2. **Descriptive Names**: Use descriptive project names that reflect the purpose of the project
3. **Version Control**: Always use version control for your projects
4. **Configuration Setup**: Use the `--setup_conf` flag to set up the project configuration
5. **Template Reuse**: Leverage template reuse for consistent project structures

## Troubleshooting

### Common Issues

#### Project Already Exists

```
💥 Project "my-project" already exists.
Run 👉 thothctl remove -pj my-project 👈🏼 if you want to reuse the project name.
```

**Solution**: Either choose a different project name or remove the existing project.

#### Invalid Project Type

```
Error: Invalid value for "--project-type": "invalid-type" is not one of "terraform", "tofu", "cdkv2", "terraform_module", "terragrunt", "custom".
```

**Solution**: Use one of the supported project types.

#### Space Not Found

```
Error: Space "non-existent-space" not found
```

**Solution**: Create the space first or use an existing space.

### Debugging

For more detailed logs, run ThothCTL with the `--debug` flag:

```bash
thothctl --debug init project --project-name my-project
```

## Related Commands

- [thothctl init space](init.md): Initialize a new space
- [thothctl list projects](../../use_cases/space_management.md): List all projects
- [thothctl remove project](../../use_cases/space_management.md): Remove a project
