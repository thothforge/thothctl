# Removing Spaces

The `thothctl remove space` command allows you to remove spaces that are tracked by ThothCTL. This helps you maintain a clean and organized development environment by removing spaces that are no longer needed.

## Command Syntax

```bash
thothctl remove space [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-s, --space-name TEXT` | Name of the space to remove (required) |
| `-rp, --remove-projects` | Remove all projects associated with this space |
| `--help` | Show help message and exit |

## Basic Usage

### Removing a Space

To remove a space from ThothCTL tracking:

```bash
thothctl remove space --space-name my-space
```

This command removes the space from ThothCTL's tracking system but does not remove any projects associated with the space. Projects that were in the space will remain tracked by ThothCTL but will no longer be associated with any space.

### Removing a Space and Its Projects

To remove a space and all projects associated with it:

```bash
thothctl remove space --space-name my-space --remove-projects
```

This command removes both the space and all projects associated with it from ThothCTL's tracking system.

## Understanding the Process

When you remove a space using the `remove space` command:

1. ThothCTL checks if the space exists in its tracking system
2. If the space exists, it removes the space's entry from the tracking file
3. If the `--remove-projects` flag is specified, it also removes all projects associated with the space
4. The space is no longer listed when you run `thothctl list spaces`
5. The actual space and project files remain untouched

## Use Cases

### Cleaning Up Old Spaces

Remove spaces that are no longer needed or used:

```bash
# List all spaces to identify candidates for removal
thothctl list spaces

# Remove an old space
thothctl remove space --space-name old-space
```

### Space Reorganization

Remove a space before reorganizing your project structure:

```bash
# Remove the space from tracking
thothctl remove space --space-name space-to-reorganize

# Create new spaces and reassign projects
thothctl init space --space-name new-space
```

### Space Retirement

Mark a space as retired by removing it from active tracking:

```bash
# Remove the space and its projects from tracking
thothctl remove space --space-name retired-space --remove-projects
```

### Fixing Tracking Issues

If a space's tracking information becomes corrupted or incorrect, you can remove it and re-add it:

```bash
# Remove the space from tracking
thothctl remove space --space-name problematic-space

# Re-initialize the space
thothctl init space --space-name problematic-space
```

## Best Practices

1. **Verify Before Removing**: Always verify that you're removing the correct space
2. **Consider Project Associations**: Decide whether to remove associated projects or keep them
3. **Backup Important Data**: Consider backing up important space configuration data before removing it
4. **Document Removals**: Keep a record of removed spaces for future reference
5. **Inform Team Members**: Notify team members when removing shared spaces

## Common Scenarios

### Removing Multiple Spaces

To remove multiple spaces, run the command for each space:

```bash
thothctl remove space --space-name space1
thothctl remove space --space-name space2
thothctl remove space --space-name space3
```

### Removing Empty Spaces

To identify and remove spaces that have no projects:

```bash
# List spaces to identify empty ones
thothctl list spaces

# Look for spaces with "0 projects" and remove them
thothctl remove space --space-name empty-space
```

### Removing a Space That Doesn't Exist

If you try to remove a space that doesn't exist in the tracking system, ThothCTL will display an error message:

```bash
thothctl remove space --space-name non-existent-space
# This will show an error indicating the space doesn't exist
```

## Impact on Projects

When removing a space without the `--remove-projects` flag:
- Projects previously associated with the space remain tracked by ThothCTL
- These projects will no longer be associated with any space
- They will show "-" in the Space column when listing projects

When removing a space with the `--remove-projects` flag:
- All projects associated with the space are removed from ThothCTL tracking
- These projects will no longer appear when listing projects
- The actual project files remain untouched
