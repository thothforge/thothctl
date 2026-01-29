# ThothCTL Check Project IaC Command

## Overview

The `thothctl check project iac` command validates Infrastructure as Code **source code structure** and organization. This command ensures your IaC projects follow defined standards, have required files, and maintain proper folder hierarchies.

## Command Structure

```
Usage: thothctl check project iac [OPTIONS]

  Check Infrastructure as Code project structure and configuration

Options:
  -m, --mode [soft|strict]        Validation mode [default: soft]
  -t, --check-type [structure|metadata|compliance]
                                  Type of IaC check to perform [default: structure]
  -p, --project-type [stack|module]
                                  Project type: stack or module [default: stack]
  --help                          Show this message and exit.
```

## Project Types

### Stack Projects (`-p stack`)

Full infrastructure projects with modules, environments, and complete project structure.

**Typical Structure**:
```
project/
├── .gitignore
├── .pre-commit-config.yaml
├── README.md
├── root.hcl
├── modules/
│   ├── networking/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   └── compute/
├── environments/
│   ├── dev/
│   ├── staging/
│   └── prod/
└── common/
```

**Usage**:
```bash
thothctl check project iac -p stack
thothctl check project iac -p stack -m strict
```

### Module Projects (`-p module`)

Single reusable Terraform modules with examples and documentation.

**Typical Structure**:
```
module/
├── .gitignore
├── .pre-commit-config.yaml
├── README.md
├── main.tf
├── variables.tf
├── outputs.tf
├── docs/
├── examples/
│   └── complete/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── terraform.tfvars
└── test/
```

**Usage**:
```bash
cd modules/networking
thothctl check project iac -p module
```

## Check Types

### Structure Validation (`-t structure`)

Validates folder and file structure against templates.

**What it checks**:
- Required root files exist
- Mandatory folders are present
- Folder content matches requirements
- Parent-child folder relationships

**Example**:
```bash
thothctl check project iac -t structure -p stack
```

### Metadata Validation (`-t metadata`)

Validates project metadata and configuration files.

**What it checks**:
- Project configuration completeness
- Metadata format and validity
- Documentation presence

**Example**:
```bash
thothctl check project iac -t metadata -p stack
```

### Compliance Validation (`-t compliance`)

Validates compliance with organizational standards.

**What it checks**:
- Security requirements
- Naming conventions
- Required documentation
- Policy adherence

**Example**:
```bash
thothctl check project iac -t compliance -p stack
```

## Validation Modes

### Soft Mode (`-m soft`)

Reports issues but doesn't fail the command (exit code 0).

**Use cases**:
- Development workflow
- Initial project setup
- Informational checks

```bash
thothctl check project iac -m soft
```

### Strict Mode (`-m strict`)

Reports issues and fails with non-zero exit code if any issues found.

**Use cases**:
- CI/CD pipelines
- Pre-deployment validation
- Production readiness checks

```bash
thothctl check project iac -m strict
```

## Configuration

### Template Files

Structure validation uses template files to define requirements:

**Stack Template**: `src/thothctl/common/.thothcf_project.toml`
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

**Module Template**: `src/thothctl/common/.thothcf_module.toml`
```toml
[project_structure]
root_files = [
    ".gitignore",
    ".pre-commit-config.yaml",
    "README.md"
]

[[project_structure.folders]]
name = "examples"
mandatory = true
type = "child"
parent = "modules"
```

### Custom Configuration

Override defaults by creating `.thothcf.toml` in your project root:

```toml
[thothcf]
project_type = "stack"  # or "module"

[project_structure]
root_files = [
    ".gitignore",
    "README.md",
    "custom-file.txt"
]

[[project_structure.folders]]
name = "custom-folder"
mandatory = true
type = "root"
```

## Usage Examples

### Validate Full Stack Project

```bash
# Basic validation
thothctl check project iac -p stack

# Strict validation for CI/CD
thothctl check project iac -p stack -m strict

# Check specific aspect
thothctl check project iac -p stack -t compliance
```

### Validate Single Module

```bash
# Navigate to module directory
cd modules/networking

# Validate module structure
thothctl check project iac -p module

# Strict validation
thothctl check project iac -p module -m strict
```

### Development Workflow

```bash
# During development (soft mode)
thothctl check project iac -p stack -m soft

# Before committing
thothctl check project iac -p stack -m strict

# Check specific module
cd modules/compute
thothctl check project iac -p module
```

## Output Format

The command provides rich formatted output with clear status indicators:

```
╭─────────────────────────────────────────────────────────────────╮
│ 🏗️ Infrastructure as Code Stack Structure Check                │
╰─────────────────────────────────────────────────────────────────╯

                        🏗️ Root Structure                         
╭──────────────┬──────┬──────────┬──────────┬─────────────────────╮
│ Item         │ Type │ Required │ Status   │ Details             │
├──────────────┼──────┼──────────┼──────────┼─────────────────────┤
│ modules      │ 📁   │ Required │ ✅ Pass  │ .                   │
│ environments │ 📁   │ Required │ ✅ Pass  │ .                   │
│ README.md    │ 📄   │ Required │ ✅ Pass  │ .                   │
╰──────────────┴──────┴──────────┴──────────┴─────────────────────╯

                        📁 Module Structure                        
╭──────────────┬──────┬──────────┬──────────┬─────────────────────╮
│ Item         │ Type │ Required │ Status   │ Details             │
├──────────────┼──────┼──────────┼──────────┼─────────────────────┤
│ main.tf      │ 📄   │ Required │ ✅ Pass  │ modules/networking  │
│ variables.tf │ 📄   │ Required │ ✅ Pass  │ modules/networking  │
│ outputs.tf   │ 📄   │ Required │ ✅ Pass  │ modules/networking  │
╰──────────────┴──────┴──────────┴──────────┴─────────────────────╯

╭─────────────────────────────────────────────────────────────────╮
│ ✅ IaC project structure validation passed                      │
╰─────────────────────────────────────────────────────────────────╯
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Validate IaC Structure

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Install ThothCTL
        run: pip install thothctl
      
      - name: Validate Stack Structure
        run: thothctl check project iac -p stack -m strict
```

### GitLab CI

```yaml
validate-structure:
  stage: validate
  script:
    - pip install thothctl
    - thothctl check project iac -p stack -m strict
  only:
    - merge_requests
    - main
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: thothctl-check-structure
        name: Validate IaC Structure
        entry: thothctl check project iac -p stack -m strict
        language: system
        pass_filenames: false
```

## Comparison with `check iac`

| Aspect | `check project iac` | `check iac` |
|--------|---------------------|-------------|
| **Focus** | Source code structure | Generated artifacts |
| **Validates** | Folders, files, organization | Plans, costs, dependencies |
| **Input** | Source .tf files | tfplan.json, graphs |
| **When to use** | Development, CI/CD | Pre-deployment analysis |
| **Output** | Structure validation | Analysis reports |
| **Validation mode** | `--mode soft/strict` | N/A (informational only) |
| **Exit on failure** | Yes (in strict mode) | No (always informational) |

**Use both commands together**:
```bash
# 1. Validate source structure
thothctl check project iac -p stack -m strict

# 2. Generate plan
tofu plan -out=tfplan.bin
tofu show -json tfplan.bin > tfplan.json

# 3. Analyze artifacts
thothctl check iac -type tfplan
thothctl check iac -type cost-analysis
thothctl check iac -type blast-radius
```

## Troubleshooting

### Missing Required Files

```
❌ - Required file main.tf missing in modules/networking
```

**Solution**: Add the missing file or update your `.thothcf.toml` configuration.

### Invalid Project Type

```
Error: Project type must be 'stack' or 'module'
```

**Solution**: Use `-p stack` or `-p module` option.

### Configuration Not Found

```
Using default options
```

**Solution**: This is informational. Create `.thothcf.toml` for custom configuration.

## Best Practices

1. **Use Strict Mode in CI/CD**: Enforce structure requirements in pipelines
2. **Validate Early**: Check structure during development, not just before deployment
3. **Customize Templates**: Create `.thothcf.toml` for project-specific requirements
4. **Module Validation**: Always validate modules independently with `-p module`
5. **Combine Checks**: Use both `check project iac` and `check iac` for comprehensive validation

## Related Commands

- [check iac](check_iac.md) - Analyze generated artifacts
- [init project](../init/init.md) - Initialize projects with correct structure
- [scan](../scan/scan.md) - Security scanning for IaC

## See Also

- [Template Engine](../../../template_engine/template_engine.md)
- [Project Structure Best Practices](../../use_cases/check_command.md)
- [Configuration Guide](../../configuration.md)
