# Listing Spaces

The `thothctl list spaces` command allows you to view all spaces that are managed by ThothCTL. This helps you understand how your projects are organized and which spaces are available for new projects.

## Command Syntax

```bash
thothctl list spaces [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |

## Basic Usage

### Listing All Spaces

To list all spaces managed by ThothCTL:

```bash
thothctl list spaces
```

Example output:

```
                         🌌 Space List                          
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ SpaceName        ┃ Projects   ┃ Description                  ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 🌐 dev           │ 3 projects │ Development environment       │
├──────────────────┼────────────┼──────────────────────────────┤
│ 🌐 staging       │ 2 projects │ Staging environment          │
├──────────────────┼────────────┼──────────────────────────────┤
│ 🌐 production    │ 1 projects │ Production environment       │
└──────────────────┴────────────┴──────────────────────────────┘
```

## Understanding the Output

The space list output includes the following information:

- **SpaceName**: The name of the space
- **Projects**: The number of projects associated with the space
- **Description**: A description of the space's purpose

Spaces are marked with a globe icon (🌐) to indicate they are spaces managed by ThothCTL.

## Data Model

Spaces and their associated projects are tracked in the global registry at `~/.thothcf/spaces.toml`. Each space entry includes a `projects` list under `spaces.<name>.projects`:

```toml
[spaces.dev]
name = "dev"
description = "Development environment"

[spaces.dev.version_control]
provider = "github"

[spaces.dev.projects]
[spaces.dev.projects.ecs-service]
registered_at = "2024-01-16T09:00:00Z"
[spaces.dev.projects.vpc-network]
registered_at = "2024-01-17T14:00:00Z"
[spaces.dev.projects.api-gateway]
registered_at = "2024-01-18T11:00:00Z"

[spaces.production]
name = "production"
description = "Production environment"

[spaces.production.version_control]
provider = "github"

[spaces.production.projects]
[spaces.production.projects.vpc-network]
registered_at = "2024-02-02T10:00:00Z"
[spaces.production.projects.eks-cluster]
registered_at = "2024-02-03T15:00:00Z"
```

The project count displayed in the list output is derived from this registry. The same project name can appear in multiple spaces due to namespace scoping (e.g., `vpc-network` in both `dev` and `production`).

## Filtering Spaces

While ThothCTL doesn't provide built-in filtering options for the list command, you can combine it with standard command-line tools to filter the output:

```bash
# List spaces and filter by name using grep
thothctl list spaces | grep "dev"

# List spaces with specific project counts
thothctl list spaces | grep "0 projects"
```

## Use Cases

### Space Management

Use the list command to maintain an overview of all your spaces:

```bash
# Generate a list of all spaces
thothctl list spaces > spaces_inventory.txt
```

### Space Organization

Identify which spaces have many or few projects:

```bash
# List all spaces to review organization
thothctl list spaces
```

### Space Cleanup

Identify empty spaces that might need cleanup:

```bash
# List spaces with no projects
thothctl list spaces | grep "0 projects"
```

### Team Collaboration

Share information about available spaces with team members:

```bash
# Generate a formatted list of spaces
thothctl list spaces
```

## Best Practices

1. **Regular Review**: Periodically review your space list to identify unused or outdated spaces
2. **Meaningful Descriptions**: Ensure each space has a clear and meaningful description
3. **Logical Organization**: Group related projects within appropriate spaces
4. **Clean Up**: Remove spaces that are no longer needed using the `remove space` command

## Related Commands

- `thothctl init space` - Create a new space
- `thothctl remove space` - Remove an existing space
- `thothctl init project --space <space-name>` - Create a project in a specific space
