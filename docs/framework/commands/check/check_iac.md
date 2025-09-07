# ThothCTL Check Project IaC Command

## Overview

The `thothctl check project iac` command validates Infrastructure as Code (IaC) project structure against predefined rules and best practices. This command ensures that your infrastructure project follows organizational conventions, contains required files and folders, and adheres to structural requirements defined in `.thothcf_project.toml` configuration files.

## Command Structure

```
Usage: thothctl check project iac [OPTIONS]

  Check Infrastructure as Code project structure and configuration

Options:
  -m, --mode [soft|strict]        Validation mode: soft (warnings) or strict (errors) [default: soft]
  -t, --check-type [structure|metadata|compliance]
                                  Type of IaC check to perform [default: structure]
  --help                          Show this message and exit.
```

## Basic Usage

### Check Project Structure

```bash
thothctl check project iac
```

This validates the current project's structure against the rules defined in `.thothcf_project.toml` or uses default template rules if no configuration is found.

### Strict Validation Mode

```bash
thothctl check project iac --mode strict
```

Uses strict validation mode that enforces all requirements without exceptions.

### Check Specific Types

```bash
thothctl check project iac --check-type metadata
thothctl check project iac --check-type compliance
```

## Validation Output

The command provides a professional Rich-formatted output with two main sections:

### Root Structure Table
Displays root-level folders and files:
- **Required folders**: `common`, `docs`, `modules`, `resources`
- **Optional folders**: `test`
- **Required files**: `.gitignore`, `.pre-commit-config.yaml`, `README.md`, `root.hcl`

### Module Structure Table
Displays module-specific files found in subfolders:
- **Module files**: `variables.tf`, `main.tf`, `outputs.tf`, `README.md`
- **Subfolder content**: Files within module directories

### Example Output

```
╭──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ 🏗️ Infrastructure as Code Project Structure Check                                                                                                                                                                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
⚛️ Checking root structure
📝 Checking content of subfolder terraform-aws-gitops-bridge-spoke

                                         🏗️ Root Structure                                          
╭───────────────────────────┬──────────┬────────────┬────────────┬────────────────────────────────╮
│ Item                      │ Type     │ Required   │ Status     │ Details                        │
├───────────────────────────┼──────────┼────────────┼────────────┼────────────────────────────────┤
│ common                    │ 📁       │ Required   │ ✅ Pass    │ .                          │
│ docs                      │ 📁       │ Required   │ ✅ Pass    │ .                          │
│ modules                   │ 📁       │ Required   │ ✅ Pass    │ .                          │
│ resources                 │ 📁       │ Required   │ ❌ Fail    │ .                          │
│ test                      │ 📁       │ Optional   │ ❌ Fail    │ .                          │
│ .gitignore                │ 📄       │ Required   │ ✅ Pass    │                                │
│ .pre-commit-config.yaml   │ 📄       │ Required   │ ✅ Pass    │                                │
│ README.md                 │ 📄       │ Required   │ ✅ Pass    │                                │
│ root.hcl                  │ 📄       │ Required   │ ✅ Pass    │                                │
╰───────────────────────────┴──────────┴────────────┴────────────┴────────────────────────────────╯

                                        📁 Module Structure                                        
╭───────────────────────────┬──────────┬────────────┬────────────┬────────────────────────────────╮
│ Item                      │ Type     │ Required   │ Status     │ Details                        │
├───────────────────────────┼──────────┼────────────┼────────────┼────────────────────────────────┤
│ variables.tf              │ 📄       │ Required   │ ✅ Pass    │ terraform-aws-gitops-bridge-s… │
│ main.tf                   │ 📄       │ Required   │ ✅ Pass    │ terraform-aws-gitops-bridge-s… │
│ outputs.tf                │ 📄       │ Required   │ ✅ Pass    │ terraform-aws-gitops-bridge-s… │
│ README.md                 │ 📄       │ Required   │ ✅ Pass    │ terraform-aws-gitops-bridge-s… │
╰───────────────────────────┴──────────┴────────────┴────────────┴────────────────────────────────╯

╭──────────────────────────────────────────────────────────────────────────────────────────────────────────── Summary ─────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ ❌ IaC project structure validation failed                                                                                                                                                                                       │
│ 💡 Review the issues above and ensure your project follows the expected structure                                                                                                                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Configuration

The command uses configuration from `.thothcf_project.toml` files. If no configuration is found, it uses default template rules.

### Default Project Structure Rules

```toml
[project_structure]
root_files = [
    ".gitignore",
    ".pre-commit-config.yaml", 
    "README.md",
    "root.hcl"
]

[[project_structure.folders]]
name = "common"
mandatory = true
type = "root"

[[project_structure.folders]]
name = "docs"
mandatory = true
type = "root"

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

[[project_structure.folders]]
name = "resources"
mandatory = true
type = "root"

[[project_structure.folders]]
name = "test"
mandatory = false
type = "root"
```

## Validation Behavior

### Exit Codes
- **Exit Code 0**: Validation passed successfully
- **Exit Code 1**: Validation failed (required items missing)

### Validation Logic
- **Required items**: Must be present for validation to pass
- **Optional items**: Can be missing without causing validation failure
- **Dynamic detection**: Uses file extensions and validation output patterns instead of hardcoded lists
- **Template-based**: Reads structure rules from thothcf configuration files

## Key Features

### Professional Output
- Rich-formatted tables with color-coded status indicators
- Separate tables for root structure vs module structure
- Clear distinction between required and optional items
- Detailed summary with actionable guidance

### Dynamic Configuration
- No hardcoded folder or file lists in the CLI code
- Reads structure rules from `.thothcf_project.toml` template files
- Falls back to default templates when no configuration is found
- Supports custom project structure definitions

### Proper Categorization
- **Root Structure**: Items detected by patterns like "root exists! in ." or "exists!" (no path)
- **Module Structure**: Items detected by patterns like "exists in [subfolder]" or "missing in [subfolder]"
- **Type Detection**: Uses file extensions to determine if item is file (📄) or folder (📁)

## Examples

### Basic Project Structure Check
```bash
thothctl check project iac
```

### Strict Validation
```bash
thothctl check project iac --mode strict
```

### Check from Specific Directory
```bash
thothctl -d /path/to/project check project iac
```

## Best Practices

1. **Template Configuration**: Define project structure rules in `.thothcf_project.toml` for consistency
2. **CI/CD Integration**: Add validation to CI/CD pipelines to enforce structure requirements
3. **Version Control**: Include thothcf configuration files in version control
4. **Regular Validation**: Run validation during development to catch issues early
5. **Custom Rules**: Adapt structure rules to match your organization's standards

## Troubleshooting

### Common Issues

#### Using Default Options
```
Using default options
```
**Solution**: Create a `.thothcf_project.toml` file with your project structure rules.

#### Validation Failures
```
❌ - resources doesn't exist in .
Project structure is invalid
```
**Solution**: Create the missing required folder or update your structure rules.

#### Permission Issues
```
Error: [Errno 13] Permission denied: '/path/to/directory'
```
**Solution**: Ensure you have read permissions for all directories being validated.

### Debugging
For detailed logs, run with debug flag:
```bash
thothctl --debug check project iac
```

## Related Commands

- [thothctl check environment](../check_environment.md): Check development environment setup
- [thothctl init project](../../init/init.md): Initialize a new project with correct structure
- [thothctl inventory iac](../../inventory/inventory_overview.md): Create inventory of infrastructure components
