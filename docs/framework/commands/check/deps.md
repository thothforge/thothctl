# Check Dependencies Command

## Overview

The `check deps` command visualizes and analyzes dependencies in your Infrastructure as Code projects.

## Usage

```bash
# Basic dependency check
thothctl check iac -type deps

# With recursive search
thothctl check iac --recursive -type deps

# Generate dependency graph
thothctl check iac -type deps --dependencies
```

## Features

- **Dependency Visualization**: Generate ASCII and SVG dependency graphs
- **Terragrunt Integration**: Analyze terragrunt.hcl dependencies
- **Recursive Analysis**: Process multiple directories
- **Graph Generation**: Create visual dependency maps

## Output

The command generates:
- ASCII dependency tree in terminal
- SVG graph files for visual representation
- Dependency analysis reports

## Examples

### Basic Dependency Analysis
```bash
thothctl check iac -type deps
```

### Generate Visual Graph
```bash
thothctl check iac -type deps --dependencies
```

## Related Commands

- [`check tfplan`](plan.md) - Analyze Terraform plans
- [`check blast-radius`](blast-radius.md) - Assess change impact
- [`inventory iac`](../inventory/iac.md) - Create dependency inventory
