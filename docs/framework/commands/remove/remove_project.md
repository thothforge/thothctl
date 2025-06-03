# Removing Projects

The `thothctl remove project` command allows you to remove projects that are tracked by ThothCTL. This helps you maintain a clean and organized development environment by removing projects that are no longer needed.

## Command Syntax

```bash
thothctl remove project [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-pj, --project-name TEXT` | Project name to delete |
| `--help` | Show help message and exit |

## Basic Usage

### Removing a Project

To remove a project from ThothCTL tracking:

```bash
thothctl remove project --project-name my-project
```

This command removes the project from ThothCTL's tracking system but does not delete the actual project files. It only removes the project's entry from the `.thothcf.toml` tracking file.

## Understanding the Process

When you remove a project using the `remove project` command:

1. ThothCTL checks if the project exists in its tracking system
2. If the project exists, it removes the project's entry from the tracking file
3. The project is no longer listed when you run `thothctl list projects`
4. The actual project files remain untouched

## Use Cases

### Cleaning Up Old Projects

Remove projects that are no longer needed or maintained:

```bash
# List all projects to identify candidates for removal
thothctl list projects

# Remove an old project
thothctl remove project --project-name old-project
```

### Project Reorganization

Remove a project from tracking before moving it to a different location or system:

```bash
# Remove the project from tracking
thothctl remove project --project-name project-to-move

# Now you can move or reorganize the project files
```

### Project Retirement

Mark a project as retired by removing it from active tracking:

```bash
# Remove the project from tracking
thothctl remove project --project-name retired-project

# Optionally, move the project to an archive location
```

### Fixing Tracking Issues

If a project's tracking information becomes corrupted or incorrect, you can remove it and re-add it:

```bash
# Remove the project from tracking
thothctl remove project --project-name problematic-project

# Re-initialize the project
thothctl init project --project-name problematic-project
```

## Best Practices

1. **Verify Before Removing**: Always verify that you're removing the correct project
2. **Backup Important Data**: Consider backing up important project data before removing it from tracking
3. **Document Removals**: Keep a record of removed projects for future reference
4. **Clean Up Related Resources**: If a project has associated resources (e.g., in cloud environments), consider cleaning those up as well
5. **Inform Team Members**: Notify team members when removing shared projects

## Common Scenarios

### Removing Multiple Projects

To remove multiple projects, run the command for each project:

```bash
thothctl remove project --project-name project1
thothctl remove project --project-name project2
thothctl remove project --project-name project3
```

### Removing All Projects in a Space

To remove all projects in a space, first list the projects in that space, then remove each one:

```bash
# List projects to identify those in the space
thothctl list projects --show-space

# Remove each project in the space
thothctl remove project --project-name project1
thothctl remove project --project-name project2
```

Alternatively, you can use the `remove space` command with the `--remove-projects` flag to remove all projects in a space at once.

### Removing a Project That Doesn't Exist

If you try to remove a project that doesn't exist in the tracking system, ThothCTL will display an error message:

```bash
thothctl remove project --project-name non-existent-project
# This will show an error indicating the project doesn't exist
```
