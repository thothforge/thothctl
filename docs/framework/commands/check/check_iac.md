# ThothCTL Check IaC Commands

## Overview

The `thothctl check iac` command analyzes Infrastructure as Code **generated artifacts** including terraform plans, dependency graphs, cost estimates, and blast radius assessments. This command helps ensure infrastructure changes are safe, cost-effective, and compliant before deployment.

## Command Structure

```
Usage: thothctl check iac [OPTIONS]

  Analyze IaC artifacts: plans, dependencies, costs, and blast radius

Options:
  -deps, --dependencies           Visualize dependency graph
  --recursive                     Check recursively through subdirectories
  --outmd TEXT                    Output markdown file [default: tfplan_check_results.md]
  --tftool [terraform|tofu]       Terraform tool to use [default: tofu]
  -type, --check_type [tfplan|deps|blast-radius|cost-analysis]
                                  Check type to perform [default: tfplan]
  --plan-file TEXT                Path to terraform plan JSON file (for blast-radius)
  --help                          Show this message and exit.
```

## Check Types

### 1. Terraform Plan Analysis (`tfplan`)

Analyzes terraform plan files and validates planned changes.

```bash
thothctl check iac -type tfplan --recursive
```

**What it does**:
- Parses tfplan.json files
- Analyzes resource changes (create/update/delete)
- Extracts dependencies between resources
- Generates summary reports

**Requirements**:
- Must have `tfplan.json` files (generate with `tofu show -json tfplan.bin > tfplan.json`)

### 2. Dependency Analysis (`deps`)

Visualizes infrastructure dependencies and relationships.

```bash
thothctl check iac -type deps --recursive
```

**What it does**:
- Generates dependency graphs using Terragrunt
- Displays ASCII tree visualization
- Calculates component risk scores
- Shows resource relationships

**Advanced Option**:
```bash
# Show explicit input variables from other stacks
thothctl check iac -type deps --show-inputs
```

The `--show-inputs` flag enables advanced visualization that shows:
- Input variables passed between stacks
- Output values consumed by dependent stacks
- External dependencies outside current directory

See [Advanced Dependency Visualization](deps-advanced.md) for detailed documentation.

**Requirements**:
- Terragrunt project structure
- Valid terragrunt.hcl files

### 3. Blast Radius Assessment (`blast-radius`)

ITIL v4 compliant risk assessment combining dependency analysis with planned changes.

```bash
thothctl check iac -type blast-radius --recursive
thothctl check iac -type blast-radius --recursive --plan-file tfplan.json
```

**What it does**:
- Component-level risk scoring
- ITIL v4 change type classification
- Impact analysis across dependencies
- Automated approval workflow recommendations
- Mitigation and rollback planning

See [Blast Radius Assessment](blast-radius.md) for detailed documentation.

### 4. Cost Analysis (`cost-analysis`)

Estimates AWS infrastructure costs from Terraform plans.

```bash
thothctl check iac -type cost-analysis --recursive
```

**What it does**:
- Analyzes Terraform plans for AWS resources
- Estimates monthly and annual costs
- Provides service-by-service breakdown
- Offers optimization recommendations
- Works offline with regularly updated pricing data

**Supported AWS Services**: EC2, RDS, S3, Lambda, ELB/ALB/NLB, VPC, EBS, DynamoDB, CloudWatch, EKS, ECS, Secrets Manager, API Gateway, Bedrock

See [Cost Analysis](cost-analysis.md) for detailed documentation.

## Basic Usage Examples

### Quick Plan Analysis
```bash
# Generate plan first
tofu plan -out=tfplan.bin
tofu show -json tfplan.bin > tfplan.json

# Analyze the plan
thothctl check iac -type tfplan --recursive
```

### Dependency Visualization
```bash
thothctl check iac -type deps --recursive
```

### Complete Pre-Deployment Analysis
```bash
# Generate terraform plan first
tofu plan -out=tfplan.bin
tofu show -json tfplan.bin > tfplan.json

# Analyze plan
thothctl check iac -type tfplan --recursive

# Estimate costs
thothctl check iac -type cost-analysis --recursive

# Assess blast radius with plan
thothctl check iac -type blast-radius --recursive --plan-file tfplan.json
```

## Integration Workflow

### Complete Pre-Deployment Workflow
```bash
# 1. Validate source structure first
thothctl check project iac -p stack -m strict

# 2. Generate terraform plan
tofu plan -out=tfplan.bin
tofu show -json tfplan.bin > tfplan.json

# 3. Analyze plan
thothctl check iac -type tfplan --recursive

# 4. Estimate costs
thothctl check iac -type cost-analysis --recursive

# 5. Analyze dependencies
thothctl check iac -type deps --recursive

# 6. Assess blast radius and risk
thothctl check iac -type blast-radius --recursive --plan-file tfplan.json

# 7. Follow ITIL v4 recommendations from output
```

## Output Examples

### Dependency Analysis Output
```
🔍 Infrastructure Dependency Analysis
=====================================

📊 Risk Assessment Summary
┌─────────────────┬────────────┬──────────────┬─────────────┐
│ Component       │ Risk Score │ Dependencies │ Dependents  │
├─────────────────┼────────────┼──────────────┼─────────────┤
│ vpc-main        │ 85%        │ 0            │ 8           │
│ security-groups │ 72%        │ 1            │ 3           │
└─────────────────┴────────────┴──────────────┴─────────────┘
```

### Blast Radius Assessment Output
```
🎯 BLAST RADIUS ASSESSMENT (ITIL v4 Compliant)
===============================================

📊 Risk Summary
Risk Level: HIGH
Change Type: NORMAL
Total Components: 12
Affected Components: 7

📋 ITIL v4 Recommendations
• ⚠️ HIGH: Require senior management approval
• ⚠️ Schedule during maintenance window
• ⚠️ Prepare detailed rollback procedures
```

## Configuration

### Terraform Tool Selection
```bash
# Use OpenTofu
thothctl check iac -type tfplan --tftool tofu

# Use Terraform
thothctl check iac -type tfplan --tftool terraform
```

### Output Customization
```bash
# Custom output file
thothctl check iac -type tfplan --outmd custom_results.md

# Recursive analysis
thothctl check iac -type tfplan --recursive
```

## Best Practices

### 1. Regular Dependency Analysis
Run dependency analysis regularly to understand component relationships:
```bash
thothctl check iac -type deps --recursive
```

### 2. Pre-Deployment Risk Assessment
Always assess blast radius before major deployments:
```bash
thothctl check iac -type blast-radius --recursive --plan-file tfplan.json
```

### 3. Automated Validation
Integrate checks into CI/CD pipelines:
```bash
# In CI/CD pipeline
thothctl check iac -type tfplan --recursive --mode hard
```

### 4. Documentation Generation
Generate documentation from validation results:
```bash
thothctl check iac -type tfplan --recursive --outmd deployment_validation.md
```

## Troubleshooting

### Common Issues

#### Plan File Not Found
```bash
# Generate plan first
terraform plan -out=tfplan.json
# or
tofu plan -out=tfplan.json
```

#### Dependencies Not Detected
```bash
# Ensure terragrunt.hcl files exist
ls -la */terragrunt.hcl

# Check directory structure
tree -L 2
```

#### High Risk False Positives
- Review component criticality settings
- Validate dependency graph accuracy
- Check change type detection logic

## Related Commands

- [`thothctl check project iac`](../project/iac.md) - Project structure validation
- [`thothctl inventory iac`](../inventory/iac.md) - Infrastructure inventory
- [`thothctl scan iac`](../scan/iac.md) - Security scanning
- [`thothctl document iac`](../document/iac.md) - Documentation generation
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

- [thothctl check project iac](check_project_iac.md): Validate source code structure
- [thothctl check environment](check_environment.md): Check development environment setup
- [thothctl inventory iac](../inventory/inventory_overview.md): Create inventory of infrastructure components

## Comparison: `check iac` vs `check project iac`

Understanding when to use each command:

| Aspect | `check iac` | `check project iac` |
|--------|-------------|---------------------|
| **Purpose** | Analyze generated artifacts | Validate source structure |
| **Focus** | Runtime analysis | Code organization |
| **Input** | tfplan.json, graphs | Source .tf files |
| **Validates** | Plans, costs, dependencies, impact | Folders, files, structure |
| **When to use** | Pre-deployment | Development, CI/CD |
| **Output** | Analysis reports | Structure validation |
| **Validation mode** | N/A (informational only) | `--mode soft/strict` |
| **Exit on issues** | No (always informational) | Yes (in strict mode) |

**Recommended workflow**:
```bash
# Step 1: Validate source structure (development/CI)
thothctl check project iac -p stack -m strict

# Step 2: Generate plan
tofu plan -out=tfplan.bin
tofu show -json tfplan.bin > tfplan.json

# Step 3: Analyze artifacts (pre-deployment)
thothctl check iac -type tfplan
thothctl check iac -type cost-analysis
thothctl check iac -type blast-radius
```

See [check project iac documentation](check_project_iac.md) for source structure validation.
