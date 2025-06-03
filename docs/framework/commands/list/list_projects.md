# Listing Projects

The `thothctl list projects` command allows you to view all projects that are managed by ThothCTL. This helps you keep track of your projects and understand their organization within spaces.

## Command Syntax

```bash
thothctl list projects [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-s, --show-space` | Show space information for each project |
| `--help` | Show help message and exit |

## Basic Usage

### Listing All Projects

To list all projects managed by ThothCTL:

```bash
thothctl list projects
```

Example output:

```
                     Project List                    
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ ProjectName                        ┃ Space      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ ☑️  terraform_module_example       │ -          │
├────────────────────────────────────┼────────────┤
│ ☑️  eks_cluster                    │ -          │
├────────────────────────────────────┼────────────┤
│ ☑️  vpc_network                    │ -          │
├────────────────────────────────────┼────────────┤
│ ☑️  ecs_service                    │ dev        │
└────────────────────────────────────┴────────────┘
```

### Showing Space Information

To show space information for each project:

```bash
thothctl list projects --show-space
```

This will display the same output as above, with the space column showing which space each project belongs to. Projects that are not associated with any space will show "-" in the Space column.

### Default List Command

When you run `thothctl list` without any subcommand, it defaults to listing projects:

```bash
thothctl list
```

This is equivalent to running `thothctl list projects`.

## Understanding the Output

The project list output includes the following information:

- **ProjectName**: The name of the project
- **Space**: The space the project belongs to (if any)

Projects are marked with a checkmark (☑️) to indicate they are being tracked by ThothCTL.

## Filtering Projects

While ThothCTL doesn't provide built-in filtering options for the list command, you can combine it with standard command-line tools to filter the output:

```bash
# List projects and filter by name using grep
thothctl list projects | grep "terraform"

# List projects and filter by space
thothctl list projects --show-space | grep "dev"
```

## Use Cases

### Inventory Management

Use the list command to maintain an inventory of all your projects:

```bash
# Generate a list of all projects
thothctl list projects > projects_inventory.txt
```

### Project Organization

Identify which projects need to be organized into spaces:

```bash
# List projects without spaces
thothctl list projects --show-space | grep " - "
```

### Project Cleanup

Identify old or unused projects that might need cleanup:

```bash
# List all projects to review for cleanup
thothctl list projects
```

### Team Collaboration

Share information about available projects with team members:

```bash
# Generate a formatted list of projects
thothctl list projects --show-space
```

## Best Practices

1. **Regular Review**: Periodically review your project list to identify unused or outdated projects
2. **Organize by Space**: Associate projects with appropriate spaces for better organization
3. **Document Projects**: Maintain documentation for each project listed in your inventory
4. **Clean Up**: Remove projects that are no longer needed using the `remove project` command
