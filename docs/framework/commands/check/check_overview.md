# ThothCTL Check Commands

## Overview

The `thothctl check` command group provides tools for validating various aspects of your infrastructure code, project structure, and development environment. These commands help ensure that your projects follow best practices, adhere to defined structures, and meet security requirements.

## Available Check Commands

### [check environment](check_environment.md)

Validates the development environment and required tools installation.

```bash
thothctl check environment
```

This command validates:
- Tool versions (Terraform, OpenTofu, Terragrunt, etc.)
- Current vs recommended versions
- Tool availability and installation status

### [check space](check_space.md)

Provides comprehensive diagnostics for space configuration and setup.

```bash
thothctl check space --space-name <space_name>
```

This command validates:
- Space configuration and directory structure
- VCS settings and connectivity
- Credential status and security
- Project usage and associations

### [check project iac](check_project_iac.md)

Validates Infrastructure as Code (IaC) project **source code structure** against predefined rules and best practices.

```bash
# Validate full stack project
thothctl check project iac -p stack

# Validate single module
thothctl check project iac -p module
```

This command validates:
- Root project structure (folders and files)
- Module structure within subfolders
- Template-based configuration compliance
- Required vs optional components

**Project Types**:
- `stack` - Full project with modules, environments, etc. (default)
- `module` - Single reusable Terraform module

See [detailed documentation](check_project_iac.md) for complete usage guide.

### [check iac](check_iac.md)

Analyzes IaC **generated artifacts** including terraform plans, dependencies, costs, and blast radius.

```bash
# Analyze terraform plan
thothctl check iac -type tfplan --recursive

# Analyze dependencies
thothctl check iac -type deps --recursive

# Assess blast radius (ITIL v4 compliant)
thothctl check iac -type blast-radius --recursive

# Estimate infrastructure costs
thothctl check iac -type cost-analysis --recursive
```

Available check types:
- **tfplan**: Analyze terraform plan files (tfplan.json)
- **deps**: Visualize dependency graph and relationships
- **blast-radius**: ITIL v4 compliant risk assessment combining dependency analysis with planned changes
- **cost-analysis**: Estimate AWS infrastructure costs from Terraform plans

See [detailed documentation](check_iac.md) for complete usage guide.

### [Blast Radius Assessment](blast-radius.md)

ITIL v4 compliant risk assessment that combines dependency analysis with planned changes to assess deployment impact.

```bash
thothctl check iac -type blast-radius --recursive --plan-file tfplan.json
```

Features:
- Risk scoring based on component complexity and dependencies
- ITIL v4 change type classification (STANDARD, NORMAL, EMERGENCY)
- Automated approval workflow recommendations
- Mitigation steps and rollback planning
- Visual risk assessment with color-coded components

## Command Structure

The check commands follow a hierarchical structure:

```
thothctl check
├── environment          # Environment and tools validation
├── space               # Space configuration diagnostics
└── project              # Project-specific validations
    └── iac              # Infrastructure as Code structure validation
```

## Common Options

Most check commands support the following options:

- **--mode [soft|strict]**: Determines validation strictness level
- **--check-type**: Specifies the type of validation to perform
- **--debug**: Enables detailed logging for troubleshooting

## Professional Output

All check commands provide Rich-formatted output with:
- Color-coded status indicators (✅ Pass, ❌ Fail)
- Professional tables with clear categorization
- Detailed summary panels with actionable guidance
- Consistent styling across all commands

### Example Output Structure

```
╭──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ 🏗️ Infrastructure as Code Project Structure Check                                                                                                                                                                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

                                         🏗️ Root Structure                                          
╭───────────────────────────┬──────────┬────────────┬────────────┬────────────────────────────────╮
│ Item                      │ Type     │ Required   │ Status     │ Details                        │
├───────────────────────────┼──────────┼────────────┼────────────┼────────────────────────────────┤
│ common                    │ 📁       │ Required   │ ✅ Pass    │ .                          │
│ docs                      │ 📁       │ Required   │ ✅ Pass    │ .                          │
╰───────────────────────────┴──────────┴────────────┴────────────┴────────────────────────────────╯

╭──────────────────────────────────────────────────────────────────────────────────────────────────────────── Summary ─────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ ✅ IaC project structure validation passed                                                                                                                                                                                       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
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
      - name: Check Environment
        run: thothctl check environment
      - name: Check Space Configuration
        run: thothctl check space --space-name ${{ vars.SPACE_NAME }}
      - name: Validate IaC Structure
        run: thothctl check project iac --mode strict
```

### Pre-commit Hooks

Use check commands in pre-commit hooks to validate changes before committing:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: thothctl-check-environment
        name: ThothCTL Check Environment
        entry: thothctl check environment
        language: system
        pass_filenames: false
      - id: thothctl-check-project-iac
        name: ThothCTL Check Project IaC
        entry: thothctl check project iac
        language: system
        pass_filenames: false
```

### Development Workflow

Run check commands during development to ensure your environment and code meet requirements:

```bash
# Check development environment setup
thothctl check environment

# Validate space configuration before project operations
thothctl check space --space-name development

# Validate project structure before committing
thothctl check project iac

# Strict validation for production readiness
thothctl check project iac --mode strict
```

## Configuration

### Environment Configuration

Environment checks use `version_tools.py` as the single source of truth for tool versions and installation methods.

### Project Structure Configuration

Project structure validation uses `.thothcf_project.toml` template files for configuration:

```toml
[project_structure]
root_files = [
    ".gitignore",
    ".pre-commit-config.yaml", 
    "README.md",
    "root.hcl"
]

[[project_structure.folders]]
name = "modules"
mandatory = true
type = "root"
content = [
    "variables.tf",
    "main.tf", 
    "outputs.tf",
    "README.md"
]
```

## Best Practices

1. **Template-Based Configuration**: Use `.thothcf_project.toml` files to define project structure rules
2. **Version Control**: Include thothcf configuration files in version control for consistency
3. **CI/CD Integration**: Add validation commands to pipelines to enforce requirements
4. **Environment Validation**: Regularly check environment setup to ensure tool compatibility
5. **Strict Mode**: Use strict validation mode in production environments
6. **Regular Updates**: Keep tool versions and templates updated based on organizational standards

## Exit Codes

All check commands follow consistent exit code patterns:

- **Exit Code 0**: Validation passed successfully
- **Exit Code 1**: Validation failed (required items missing or environment issues)

## Troubleshooting

### Common Issues

#### Missing Configuration Files
```
Using default options
```
**Solution**: Create appropriate `.thothcf_project.toml` configuration files.

#### Tool Version Mismatches
```
❌ terraform: 1.5.0 (recommended: 1.6.0)
```
**Solution**: Update tools to recommended versions or adjust version requirements.

#### Permission Issues
```
Error: [Errno 13] Permission denied
```
**Solution**: Ensure proper read/write permissions for directories being validated.

### Debugging

Enable debug mode for detailed logging:

```bash
thothctl --debug check environment
thothctl --debug check project iac
```

## Extending Check Commands

ThothCTL's modular architecture allows for easy extension of check commands:

1. **Service Layer**: Implement validation logic in `src/thothctl/services/check/`
2. **Command Layer**: Create command interfaces in `src/thothctl/commands/check/commands/`
3. **Configuration**: Define validation rules in template files
4. **Rich Output**: Use consistent Rich formatting for professional output

## Related Documentation

- [Environment Setup](../init/init.md): Setting up development environments
- [Project Initialization](../init/init.md): Creating new projects with proper structure
- [Template Engine](../../../template_engine/template_engine.md): Understanding ThothCTL templates
- [Best Practices](../../use_cases/check_command.md): Infrastructure code best practices
