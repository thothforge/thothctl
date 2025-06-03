# List Command

The `list` command in ThothCTL provides tools to view and manage projects and spaces that are tracked by ThothCTL. It helps you keep track of your projects and their organization within spaces.

## Overview

The list command helps developers and teams to:

- View all projects managed by ThothCTL
- See which spaces are available in your environment
- Understand the relationship between projects and spaces
- Get a quick overview of your development environment

## Subcommands

ThothCTL supports the following list subcommands:

- `projects` - List all projects managed by ThothCTL
- `spaces` - List all spaces managed by ThothCTL

## Basic Usage

```bash
# List all projects
thothctl list projects

# List all spaces
thothctl list spaces

# Default behavior (lists projects)
thothctl list
```

## Common Options

| Subcommand | Option | Description |
|------------|--------|-------------|
| `projects` | `-s, --show-space` | Show space information for each project |
| `spaces`   | (no options) | Lists all spaces with their projects and descriptions |

## Benefits of Project and Space Listing

1. **Organization**: Keep track of all your projects and their organization
2. **Visibility**: Quickly see which projects and spaces are available
3. **Management**: Easily identify projects that need attention or cleanup
4. **Collaboration**: Share information about available projects and spaces with team members

## Next Steps

For more detailed information about listing projects and spaces, see:

- [Listing Projects](list_projects.md) - Learn how to list and filter projects
- [Listing Spaces](list_spaces.md) - Learn how to list spaces and their associated projects
