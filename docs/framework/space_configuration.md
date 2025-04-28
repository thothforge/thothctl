# Space Configuration

A Space in ThothForge represents a logical container for your Internal Developer Platform (IDP) resources. It defines the context in which your projects, templates, and configurations operate.

## Creating a Space

You can create a new space using the `thothctl init space` command:

```bash
thothctl init space -sn my-space -vcss github --ci github-actions --description "My development space" --terraform-registry "https://registry.terraform.io"
```

This will create a new space configuration file in the `~/.thothcf/` directory.

## Space Configuration File

The space configuration is stored as a TOML file in the `~/.thothcf/` directory. The file name is the space name with a `.toml` extension.

Here's an example of a space configuration file:

```toml
# ThothForge Space Configuration

[space]
name = "my-space"
description = "My development space"
version_control = "github"
ci_system = "github-actions"
created_at = "2025-04-28T02:33:21"
updated_at = "2025-04-28T02:33:21"

# Registry configurations
[[registries]]
name = "terraform-registry"
url = "https://registry.terraform.io"
type = "terraform"
auth_required = false
default = true

# Endpoints for various services
[endpoints]
backstage = "https://backstage.example.com"
documentation = "https://docs.example.com"
```

## Configuration Options

### Space Section

The `[space]` section contains general information about the space:

- `name`: The name of the space
- `description`: A description of the space
- `version_control`: The version control system used by the space
- `ci_system`: The CI/CD system used by the space
- `created_at`: The date and time when the space was created
- `updated_at`: The date and time when the space was last updated

### Registries Section

The `[[registries]]` section contains information about module registries:

- `name`: The name of the registry
- `url`: The URL of the registry
- `type`: The type of registry (e.g., "terraform")
- `auth_required`: Whether authentication is required to access the registry
- `default`: Whether this is the default registry

### Endpoints Section

The `[endpoints]` section contains URLs for various services used by the space.

## Managing Spaces

### Listing Spaces

You can list all available spaces using the `thothctl list spaces` command:

```bash
thothctl list spaces
```

### Deleting a Space

You can delete a space using the `thothctl remove space` command:

```bash
thothctl remove space -sn my-space
```

## Using Spaces with Projects

When creating a new project, you can specify the space to use:

```bash
thothctl init project -sn my-space -pn my-project
```

This will create a new project in the specified space.
