# ThothCTL Check IaC Command

## Overview

The `thothctl check iac` command validates Infrastructure as Code (IaC) artifacts against predefined rules and best practices. This command helps ensure that your infrastructure code follows project conventions, contains required files, and adheres to structural requirements.

## Command Options

```
Usage: thothctl check iac [OPTIONS]

  Check Infrastructure as code artifacts like tfplan and dependencies

Options:
  --mode [soft|hard]              Validation mode  [default: soft]
  -deps, --dependencies TEXT      View a dependency graph in asccii pretty
                                  shell output
  --recursive [local|recursive]   Validate your terraform plan recursively or
                                  in one directory
  --outmd                         Output markdown file path
  -type, --check_type [tfplan|module|project]
                                  Check module or project structure format, or
                                  check tfplan  [default: project]
  --help                          Show this message and exit.
```

## Basic Usage

### Check Project Structure

```bash
thothctl check iac --check_type project
```

This validates the current project's structure against the defined rules in the project's `.thothcf.toml` file or uses default rules if no configuration is found.

### Check Module Structure

```bash
thothctl check iac --check_type module
```

This validates a Terraform module's structure against module-specific rules.

### Check Terraform Plan

```bash
thothctl check iac --check_type tfplan
```

This validates a Terraform plan file against best practices and security rules.

## Validation Modes

The command supports two validation modes:

- **soft**: Reports issues but doesn't fail the command (exit code 0)
- **hard**: Reports issues and fails the command with a non-zero exit code if any issues are found

```bash
thothctl check iac --mode hard
```

## Project Structure Validation

The command validates the project structure against rules defined in the `.thothcf.toml` file. The validation includes:

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

## Module Structure Validation

When checking modules (`--check_type module`), the command validates against module-specific rules, which typically include:

1. **Required Files**: `main.tf`, `variables.tf`, `outputs.tf`, `README.md`
2. **Documentation**: Checks for proper documentation in the README
3. **Module Structure**: Validates the module follows best practices

## Terraform Plan Validation

When checking Terraform plans (`--check_type tfplan`), the command validates:

1. **Security Issues**: Identifies potential security concerns
2. **Best Practices**: Checks if the plan follows Terraform best practices
3. **Resource Changes**: Analyzes the changes that will be applied

## Recursive Validation

The `--recursive` option allows you to validate multiple directories:

```bash
thothctl check iac --recursive recursive
```

- **local**: Only checks the current directory
- **recursive**: Checks all subdirectories that contain IaC files

## Dependency Visualization

The `--dependencies` flag enables visualization of dependencies between resources:

```bash
thothctl check iac --dependencies
```

This generates an ASCII representation of the dependency graph between resources.

## Output Options

The `--outmd` flag generates a Markdown report of the validation results:

```bash
thothctl check iac --outmd
```

This creates a detailed report that can be included in documentation or shared with team members.

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

## Validation Process

1. **Configuration Loading**: The command first loads the project configuration from `.thothcf.toml` or uses default rules
2. **Structure Analysis**: It analyzes the current directory structure
3. **Rule Comparison**: It compares the actual structure against the defined rules
4. **Report Generation**: It generates a report of any discrepancies
5. **Exit Code**: In hard mode, it exits with a non-zero code if validation fails

## Best Practices

1. **Version Control**: Include the `.thothcf.toml` file in version control to ensure consistent validation across the team
2. **CI/CD Integration**: Add the check command to your CI/CD pipeline to validate infrastructure code before deployment
3. **Hard Mode**: Use hard mode in CI/CD pipelines to enforce structure requirements
4. **Custom Rules**: Define custom rules in `.thothcf.toml` to match your project's specific requirements
5. **Regular Validation**: Run validation regularly during development to catch issues early

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

- [thothctl init project](../init/init_project.md): Initialize a new project with the correct structure
- [thothctl scan](../scan/scan.md): Scan infrastructure code for security issues
