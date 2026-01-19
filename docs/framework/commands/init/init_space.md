# Init Space Command

## Overview

The `init space` command creates and configures workspaces (spaces) for organizing multiple ThothCTL projects.

## Usage

```bash
# Create new space
thothctl init space --name "production" --description "Production environment"

# List existing spaces
thothctl list spaces

# Initialize project in space
thothctl init project --space production --name web-app
```

## Features

- **Space Management**: Create isolated workspaces
- **Project Organization**: Group related projects
- **Environment Separation**: Separate dev, staging, production
- **Access Control**: Manage space permissions
- **Configuration Isolation**: Independent space settings

## Space Structure

```
~/.thothcf/
├── spaces.toml           # Space configurations
├── .thothcf.toml        # Global projects
└── spaces/
    ├── production/      # Production space
    ├── staging/         # Staging space
    └── development/     # Development space
```

## Examples

### Create Production Space
```bash
thothctl init space --name "production" \
  --description "Production infrastructure projects" \
  --vcs-provider "github"
```

### Create Development Space
```bash
thothctl init space --name "development" \
  --description "Development and testing projects"
```

### List All Spaces
```bash
thothctl list spaces
```

## Related Commands

- [`init project`](../init/init.md) - Initialize projects
- [`list spaces`](../list/list_spaces.md) - List available spaces
- [`remove space`](../remove/remove_space.md) - Remove spaces
