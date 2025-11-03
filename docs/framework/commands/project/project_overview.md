# Project Command

The `project` command in ThothCTL provides tools to manage, convert, upgrade, and clean up your projects. It helps streamline project management tasks and enables easy conversion between different formats and frameworks.

## Overview

The project command helps developers and teams to:

- Convert projects to templates for reuse across the organization
- Create new projects from existing templates
- Convert between different Infrastructure as Code (IaC) frameworks
- Upgrade projects with latest changes from template repositories
- Clean up residual files and directories to keep projects tidy
- Standardize project structures and formats

## Subcommands

ThothCTL supports the following project subcommands:

- `convert` - Convert project to template, template to project, or between IaC frameworks
- `upgrade` - Upgrade project with latest changes from remote template repository
- `cleanup` - Clean up residual files and directories from your project

## Basic Usage

```bash
# Convert a project to a template
thothctl project convert --make-template

# Create a project from a template
thothctl project convert --make-project

# Upgrade project with latest template changes
thothctl project upgrade --dry-run

# Upgrade project interactively
thothctl project upgrade --interactive

# Clean up residual files from a project
thothctl project cleanup
```

## Common Options

| Subcommand | Description |
|------------|-------------|
| `convert`  | Convert between project formats and templates |
| `upgrade`  | Upgrade project with latest changes from remote template repository |
| `cleanup`  | Remove unnecessary files and directories from projects |

## Benefits of Project Management

1. **Standardization**: Ensure all projects follow consistent patterns and structures
2. **Reusability**: Convert projects to templates for reuse across teams
3. **Efficiency**: Quickly create new projects from proven templates
4. **Up-to-date**: Keep projects current with latest template improvements and security updates
5. **Maintainability**: Keep projects clean and free of unnecessary files
6. **Flexibility**: Convert between different IaC frameworks as needed
7. **Safety**: Intelligent upgrade process with conflict detection and interactive selection

## Next Steps

For more detailed information about project management, see:

- [Project Conversion](project_convert.md) - Learn how to convert projects to templates and between frameworks
- [Project Upgrade](project_upgrade.md) - Learn how to upgrade projects with latest template changes
- [Project Cleanup](project_cleanup.md) - Learn how to clean up residual files and directories
