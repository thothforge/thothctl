# ThothCTL Check IaC Command

## Overview

The `thothctl check iac` command validates Infrastructure as Code (IaC) artifacts against predefined rules and best practices. This command helps ensure that your infrastructure code follows project conventions, contains required files, and adheres to structural requirements. It also provides dependency visualization with risk assessment to help identify high-risk components in your infrastructure.

## Command Options

```
Usage: thothctl check iac [OPTIONS]

  Check Infrastructure as code artifacts like tfplan and dependencies

Options:
  --mode [soft|hard]              Validation mode  [default: soft]
  -deps, --dependencies           View a dependency graph with risk assessment
                                  in ASCII pretty shell output
  --recursive                     Search for tfplan files recursively in
                                  subdirectories
  --outmd TEXT                    Output markdown file path
                                  [default: tfplan_check_results.md]
  --tftool [terraform|tofu]       Terraform tool to use (terraform or tofu)
                                  [default: tofu]
  -type, --check_type [tfplan|module|project|deps]
                                  Check module or project structure format, check
                                  tfplan, or visualize dependencies
                                  [default: project]
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

### Visualize Dependencies with Risk Assessment

```bash
thothctl check iac --check_type deps
# or
thothctl check iac -deps
```

This visualizes the dependencies between infrastructure components and provides a risk assessment for each component.

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
thothctl check iac --recursive
```

This checks all subdirectories that contain IaC files.

## Dependency Visualization with Risk Assessment

The dependency visualization feature (`-deps` or `--check_type deps`) provides a comprehensive view of your infrastructure components and their dependencies, along with a risk assessment for each component:

```bash
thothctl check iac -deps
```

### Risk Assessment Factors

The risk assessment considers multiple factors:

1. **Changes Frequency**: How often the component changes (based on git history)
2. **Dependencies Count**: Number of incoming and outgoing dependencies
3. **Complexity**: Based on number of files and lines of code
4. **Criticality**: How many other components depend on this one
5. **Recent Changes**: Recent modifications to the component

### Risk Levels

Components are color-coded based on their risk level:

- **Green (0-25%)**: Low risk - Minimal risk of issues if changed
- **Yellow (26-50%)**: Medium risk - Changes should be reviewed carefully
- **Orange (51-75%)**: High risk - Significant risk, careful testing needed
- **Red (76-100%)**: Critical risk - Very high risk, changes may cause cascading issues

### Example Output

```
╭──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ 🔄 Enhanced Dependency Visualization 🔄                                                                                                                                                                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
Infrastructure Modules
├── stacks/infra/databases/aurora (72.5% risk)
│   ├── stacks/networking (45.2% risk)
│   ├── stacks/infra/baselines (28.7% risk)
│   │   └── stacks/networking (45.2% risk)
│   └── stacks/infra/containers (63.1% risk)
│       ├── stacks/networking (45.2% risk)
│       └── stacks/infra/baselines (28.7% risk)
└── stacks/services/addons (85.3% risk)
    ├── stacks/infra/containers (63.1% risk)
    ├── stacks/infra/streaming/msk (54.8% risk)
    │   ├── stacks/networking (45.2% risk)
    │   ├── stacks/infra/containers (63.1% risk)
    │   └── stacks/infra/baselines (28.7% risk)
    ├── stacks/infra/baselines (28.7% risk)
    ├── stacks/networking (45.2% risk)
    └── stacks/infra/application (67.9% risk)
        ├── stacks/networking (45.2% risk)
        ├── stacks/infra/baselines (28.7% risk)
        └── stacks/infra/containers (63.1% risk)

✅ Found 24 modules with 17 dependencies

Risk Level Legend:
Risk Level           Description
Low Risk (0-25%)     Minimal risk of issues if changed
Medium Risk (26-50%) Moderate risk, changes should be reviewed
High Risk (51-75%)   Significant risk, careful testing needed
Critical Risk (76-100%) Very high risk, changes may cause cascading issues
```

## Output Options

The `--outmd` flag generates a Markdown report of the validation results:

```bash
thothctl check iac --check_type tfplan --outmd report.md
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
thothctl check iac --check_type tfplan --recursive --outmd report.md
```

### Visualize Dependencies with Risk Assessment

```bash
thothctl check iac -deps
```

### Check Dependencies for a Specific Directory

```bash
thothctl -d /path/to/project check iac --check_type deps
```

## Validation Process

1. **Configuration Loading**: The command first loads the project configuration from `.thothcf.toml` or uses default rules
2. **Structure Analysis**: It analyzes the current directory structure
3. **Rule Comparison**: It compares the actual structure against the defined rules
4. **Risk Assessment**: For dependency visualization, it calculates risk percentages for each component
5. **Report Generation**: It generates a report of any discrepancies or visualizes dependencies with risk assessment
6. **Exit Code**: In hard mode, it exits with a non-zero code if validation fails

## Best Practices

1. **Version Control**: Include the `.thothcf.toml` file in version control to ensure consistent validation across the team
2. **CI/CD Integration**: Add the check command to your CI/CD pipeline to validate infrastructure code before deployment
3. **Hard Mode**: Use hard mode in CI/CD pipelines to enforce structure requirements
4. **Risk Assessment**: Use the dependency visualization with risk assessment to identify high-risk components before making changes
5. **Custom Rules**: Define custom rules in `.thothcf.toml` to match your project's specific requirements
6. **Regular Validation**: Run validation regularly during development to catch issues early

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

#### Terragrunt Not Found

```
Error running terragrunt dag graph: [Errno 2] No such file or directory: 'terragrunt'
```

**Solution**: Install Terragrunt or ensure it's in your PATH.

### Debugging

For more detailed logs, run ThothCTL with the `--debug` flag:

```bash
thothctl --debug check iac -deps
```

## Related Commands

- [thothctl init project](../init/init_project.md): Initialize a new project with the correct structure
- [thothctl scan](../scan/scan.md): Scan infrastructure code for security issues
- [thothctl inventory](../inventory/inventory.md): Create an inventory of infrastructure components
