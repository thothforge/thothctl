# ThothCTL Check Commands

## Overview

The `thothctl check` command group provides tools for validating various aspects of your infrastructure code, project structure, and environment. These commands help ensure that your projects follow best practices, adhere to defined structures, and meet security requirements.

## Available Check Commands

### [check iac](check_iac.md)

Validates Infrastructure as Code (IaC) artifacts against predefined rules and best practices.

```bash
thothctl check iac [OPTIONS]
```

This command can validate:
- Project structure
- Module structure
- Terraform plans

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

## Common Options

Most check commands support the following options:

- **--mode [soft|hard]**: Determines whether validation failures should cause the command to exit with a non-zero code
- **--outmd**: Generates a Markdown report of validation results

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

## Best Practices

1. **Define Clear Rules**: Create detailed structure rules in your `.thothcf.toml` file
2. **Version Control Rules**: Include your validation rules in version control
3. **Consistent Validation**: Use the same validation rules across all environments
4. **Automated Checks**: Integrate validation into your CI/CD pipeline
5. **Documentation**: Document your project structure requirements

## Extending Check Commands

ThothCTL's check commands can be extended with custom validators. To create a custom validator:

1. Create a new Python file in the `src/thothctl/services/check/` directory
2. Implement the validation logic
3. Create a new command file in `src/thothctl/commands/check/commands/`
4. Register your validator with the command

## Related Documentation

- [Project Structure](../../project_structure.md): Documentation on project structure requirements
- [Terraform Best Practices](../../terraform_best_practices.md): Best practices for Terraform code
- [Security Guidelines](../../security_guidelines.md): Security guidelines for infrastructure code
