# Project IaC Command

## Overview

The `project iac` command manages Infrastructure as Code project lifecycle, including creation, validation, and maintenance.

## Usage

```bash
# Initialize IaC project
thothctl project iac init

# Validate project structure
thothctl project iac validate

# Clean project artifacts
thothctl project iac clean
```

## Features

- **Project Initialization**: Set up new IaC projects
- **Structure Validation**: Ensure proper project organization
- **Artifact Management**: Clean temporary files and caches
- **Template Integration**: Use project templates
- **Configuration Management**: Manage project settings

## Project Structure

The command helps maintain:
```
project/
├── modules/          # Reusable modules
├── stacks/           # Environment-specific stacks
├── common/           # Shared configurations
└── docs/             # Documentation
```

## Examples

### Initialize New Project
```bash
thothctl project iac init --template terraform-terragrunt
```

### Validate Project
```bash
thothctl project iac validate
```

### Clean Artifacts
```bash
thothctl project iac clean
```

## Related Commands

- [`init`](../init/init.md) - Initialize ThothCTL projects
- [`check iac`](../check/check_iac.md) - Validate structure
- [`generate stacks`](../generate/generate_stacks.md) - Generate infrastructure stacks
