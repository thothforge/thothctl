# ThothCTL Check Command

## Overview

The `thothctl check` command group provides tools for validating various aspects of your infrastructure code, project structure, and environment. These commands help ensure that your projects follow best practices, adhere to defined structures, and meet security requirements.

## Available Check Commands

### check iac

Validates Infrastructure as Code (IaC) artifacts against predefined rules and best practices.

```bash
thothctl check iac [OPTIONS]
```

Options:
- `--mode [soft|hard]`: Validation mode (default: soft)
- `-deps, --dependencies TEXT`: View a dependency graph in ASCII pretty shell output
- `--recursive [local|recursive]`: Validate your terraform plan recursively or in one directory
- `--outmd`: Output markdown file path
- `-type, --check_type [tfplan|module|project]`: Check module or project structure format, or check tfplan (default: project)

This command can validate:
- Project structure against defined rules
- Module structure against best practices
- Terraform plans for security and compliance

[Detailed documentation for check iac](../commands/check/check_iac.md)

### check project

Validates project configuration and structure.

```bash
thothctl check project [OPTIONS]
```

This command is currently under development.

### check environment

Validates the development environment and required tools.

```bash
thothctl check environment [OPTIONS]
```

This command is currently under development.

## Project Structure Validation

The `check iac` command validates your project structure against rules defined in the `.thothcf.toml` file. The validation includes:

1. **Required Folders**: Checks if all mandatory folders exist
2. **Required Files**: Checks if all required files exist in the project root
3. **Folder Content**: Checks if folders contain required files
4. **Folder Hierarchy**: Validates the parent-child relationship between folders

### Example Project Structure Rules

```toml
[project_structure]
root_files = [
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
mandatory = true
content = [
    "variables.tf",
    "main.tf",
    "outputs.tf",
    "README.md"
]
type = "root"

[[project_structure.folders]]
name = "environments"
mandatory = true
type = "root"
```

## Validation Modes

The check commands support two validation modes:

- **soft**: Reports issues but doesn't fail the command (exit code 0)
- **hard**: Reports issues and fails the command with a non-zero exit code if any issues are found

```bash
thothctl check iac --mode hard
```

## Use Cases

### Continuous Integration

Add check commands to your CI/CD pipeline to validate infrastructure code before deployment:

```yaml
# Example GitHub Actions workflow
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install ThothCTL
        run: pip install thothctl
      - name: Validate IaC
        run: thothctl check iac --mode hard
```

### Pre-commit Hooks

Use check commands in pre-commit hooks to validate changes before committing:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: thothctl-check-iac
        name: ThothCTL Check IaC
        entry: thothctl check iac
        language: system
        pass_filenames: false
```

### Development Workflow

Run check commands during development to ensure your code meets requirements:

```bash
# Before submitting a pull request
thothctl check iac --check_type project
```

## Examples

### Basic Project Structure Check

```bash
thothctl check iac
```

### Strict Module Validation

```bash
thothctl check iac --check_type module --mode hard
```

### Recursive Terraform Plan Check with Markdown Output

```bash
thothctl check iac --check_type tfplan --recursive recursive --outmd
```

### Check Project Structure with Dependencies

```bash
thothctl check iac --dependencies
```

## Best Practices

1. **Define Clear Rules**: Create detailed structure rules in your `.thothcf.toml` file
2. **Version Control Rules**: Include your validation rules in version control
3. **Consistent Validation**: Use the same validation rules across all environments
4. **Automated Checks**: Integrate validation into your CI/CD pipeline
5. **Documentation**: Document your project structure requirements

## Troubleshooting

### Common Issues

#### Missing Configuration

```
Using default options
```

**Solution**: Create a `.thothcf.toml` file with your project structure rules.

#### Validation Failures

```
❌ - Required file main.tf missing in modules/network
Project structure is invalid
```

**Solution**: Add the missing file or update your structure rules if the file is not actually required.

#### Permission Issues

```
Error: [Errno 13] Permission denied: '/path/to/directory'
```

**Solution**: Ensure you have read permissions for all directories being validated.

### Debugging

For more detailed logs, run ThothCTL with the `--debug` flag:

```bash
thothctl --debug check iac
```

## Related Commands

- [thothctl init project](../commands/init/init.md): Initialize a new project with the correct structure
- [thothctl scan](../commands/check/check_iac.md): Scan infrastructure code for security issues
