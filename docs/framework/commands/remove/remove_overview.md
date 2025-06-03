# Remove Command

The `remove` command in ThothCTL provides tools to remove projects and spaces that are tracked by ThothCTL. It helps you maintain a clean and organized development environment by removing projects and spaces that are no longer needed.

## Overview

The remove command helps developers and teams to:

- Remove projects that are no longer needed
- Delete spaces that are no longer in use
- Clean up the ThothCTL tracking system
- Maintain an organized development environment

## Subcommands

ThothCTL supports the following remove subcommands:

- `project` - Remove a project from ThothCTL tracking
- `space` - Remove a space and optionally its associated projects

## Basic Usage

```bash
# Remove a project
thothctl remove project --project-name my-project

# Remove a space
thothctl remove space --space-name my-space

# Remove a space and all its projects
thothctl remove space --space-name my-space --remove-projects
```

## Common Options

| Subcommand | Option | Description |
|------------|--------|-------------|
| `project` | `-pj, --project-name TEXT` | Project name to delete |
| `space` | `-s, --space-name TEXT` | Name of the space to remove (required) |
| `space` | `-rp, --remove-projects` | Remove all projects associated with this space |

## Benefits of Project and Space Removal

1. **Organization**: Keep your development environment clean and organized
2. **Clarity**: Maintain a clear view of active projects and spaces
3. **Resource Management**: Free up resources by removing unused projects and spaces
4. **Focus**: Focus on active and relevant projects

## Next Steps

For more detailed information about removing projects and spaces, see:

- [Removing Projects](remove_project.md) - Learn how to remove projects from ThothCTL tracking
- [Removing Spaces](remove_space.md) - Learn how to remove spaces and their associated projects
