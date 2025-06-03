# Project Conversion

The `thothctl project convert` command allows you to convert between different project formats, create templates from projects, and generate projects from templates. This flexibility enables efficient reuse of code and standardization across your organization.

## Command Syntax

```bash
thothctl project convert [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-br, --branch-name TEXT` | Branch name for Terramate stacks |
| `-tpt, --template-project-type [terraform\|tofu\|cdkv2]` | Project type according to Internal Developer Portal |
| `-mtem, --make-template` | Create template from project |
| `-mpro, --make-project` | Create project from template |
| `-tm, --make-terramate-stacks` | Create Terramate stack for advanced deployments |
| `--help` | Show help message and exit |

## Conversion Types

### Project to Template

Converting a project to a template allows you to create a reusable pattern that can be shared across your organization. This is useful for standardizing infrastructure deployments and ensuring consistency.

```bash
# Convert the current project to a template
thothctl project convert --make-template

# Specify the project type when converting to a template
thothctl project convert --make-template --template-project-type terraform
```

When converting a project to a template, ThothCTL:

1. Identifies variables and parameters that should be customizable
2. Creates placeholder values for sensitive information
3. Generalizes project-specific configurations
4. Prepares the template for storage in your template repository

### Template to Project

Creating a project from a template allows you to quickly start new projects based on proven patterns. This accelerates development and ensures adherence to best practices.

```bash
# Create a new project from a template
thothctl project convert --make-project

# Specify the project type when creating from a template
thothctl project convert --make-project --template-project-type terraform
```

When creating a project from a template, ThothCTL:

1. Prompts for values to replace placeholders
2. Customizes the template with project-specific information
3. Sets up the initial project structure
4. Prepares the project for immediate use

### IaC Framework Conversion

ThothCTL supports conversion between different Infrastructure as Code frameworks, allowing you to migrate from one tool to another or use multiple tools together.

#### Terramate Stacks

[Terramate](https://terramate.io/) is a tool for managing multiple Terraform stacks. Converting to Terramate stacks allows for more advanced deployment patterns.

```bash
# Create Terramate stacks from a Terraform project
thothctl project convert --make-terramate-stacks

# Specify a branch name for Terramate stacks
thothctl project convert --make-terramate-stacks --branch-name feature/terramate-migration
```

When creating Terramate stacks, ThothCTL:

1. Analyzes the existing Terraform configuration
2. Creates appropriate stack structure
3. Sets up stack dependencies
4. Configures Terramate-specific features

## Project Types

ThothCTL supports different project types to match your organization's needs:

### Terraform

[Terraform](https://www.terraform.io/) is a widely used Infrastructure as Code tool for provisioning and managing cloud infrastructure.

```bash
# Convert to a Terraform template
thothctl project convert --make-template --template-project-type terraform

# Create a Terraform project from a template
thothctl project convert --make-project --template-project-type terraform
```

### OpenTofu

[OpenTofu](https://opentofu.org/) is an open-source fork of Terraform that provides similar functionality.

```bash
# Convert to an OpenTofu template
thothctl project convert --make-template --template-project-type tofu

# Create an OpenTofu project from a template
thothctl project convert --make-project --template-project-type tofu
```

### AWS CDK v2

[AWS CDK](https://aws.amazon.com/cdk/) (Cloud Development Kit) is a framework for defining cloud infrastructure using familiar programming languages.

```bash
# Convert to a CDK v2 template
thothctl project convert --make-template --template-project-type cdkv2

# Create a CDK v2 project from a template
thothctl project convert --make-project --template-project-type cdkv2
```

## Examples

### Converting a Terraform Project to a Template

```bash
# Navigate to your Terraform project
cd my-terraform-project

# Convert the project to a template
thothctl project convert --make-template --template-project-type terraform
```

### Creating a New Project from a Template

```bash
# Navigate to the directory where you want to create the project
cd projects

# Create a new project from a template
thothctl project convert --make-project --template-project-type terraform
```

### Converting a Terraform Project to Terramate Stacks

```bash
# Navigate to your Terraform project
cd my-terraform-project

# Convert to Terramate stacks
thothctl project convert --make-terramate-stacks
```

## Best Practices

1. **Version Control Templates**: Store templates in version control to track changes and enable collaboration
2. **Document Templates**: Include clear documentation with each template explaining its purpose and usage
3. **Parameterize Appropriately**: Identify which values should be customizable in templates
4. **Test Conversions**: Always test converted projects or templates to ensure they work as expected
5. **Maintain Consistency**: Use consistent naming and structure conventions across templates
6. **Update Regularly**: Keep templates updated with the latest best practices and security recommendations

## Integration with CI/CD

You can integrate project conversion into your CI/CD pipeline to automate template generation:

```yaml
# GitHub Actions example for template generation
name: Generate Template

on:
  push:
    branches: [ main ]
    paths:
      - 'templates/**'

jobs:
  generate-template:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install ThothCTL
        run: pip install thothctl
        
      - name: Convert to Template
        run: |
          cd templates/source-project
          thothctl project convert --make-template --template-project-type terraform
        
      - name: Commit Template
        uses: stefanzweifel/git-auto-commit-action@v4
        with:
          commit_message: "chore: Update generated template"
          file_pattern: "templates/generated/*"
```
