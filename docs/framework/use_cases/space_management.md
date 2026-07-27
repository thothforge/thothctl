# ThothCTL Space Management

## Overview

ThothCTL's space management functionality allows you to organize projects within logical spaces. Each space can have its own configuration for version control systems, Terraform registries, and orchestration tools. This helps maintain consistency across related projects and simplifies credential management.

## Use Cases

- **Project Organization**: Group related projects within logical spaces
- **Consistent Configuration**: Ensure all projects in a space use the same tools and settings
- **Credential Management**: Centralize credentials for version control, Terraform, and other tools
- **Environment Separation**: Create separate spaces for development, staging, and production
- **Team Workspaces**: Create spaces for different teams or departments

## Commands

### Initialize a Space

```
Usage: thothctl init space [OPTIONS]

  Initialize a new space

Options:
  -s, --space-name TEXT         Name of the space  [required]
  -d, --description TEXT        Description of the space
  -vcs, --vcs-provider [azure_repos|github|gitlab]
                                Version Control System provider  [default:
                                azure_repos]
  -tr, --terraform-registry TEXT
                                Terraform registry URL  [default:
                                https://registry.terraform.io]
  -ta, --terraform-auth [none|token|env_var]
                                Terraform registry authentication method
                                [default: none]
  -ot, --orchestration-tool [terragrunt|terramate|none]
                                Default orchestration tool for the space
                                [default: terragrunt]
  --help                        Show this message and exit.
```

### Remove a Space

```
Usage: thothctl remove space [OPTIONS]

  Remove a space and optionally its associated projects

Options:
  -s, --space-name TEXT  Name of the space to remove  [required]
  -rp, --remove-projects  Remove all projects associated with this space
  --help                 Show this message and exit.
```

### List Spaces

```
Usage: thothctl list spaces

  List all spaces managed by thothctl
```

### Show Space Configuration

```
Usage: thothctl space show SPACE_NAME

  Show space configuration summary
```

### Update Space Configuration

```
Usage: thothctl space update SPACE_NAME [OPTIONS]

  Update an existing space's configuration

Options:
  -d, --description TEXT          New description for the space
  -vcs, --vcs-provider [azure_repos|github|gitlab]
  -ot, --orchestration-tool [terragrunt|terramate|none]
  -tr, --terraform-registry TEXT  Terraform registry URL
  -pr, --policy-repo TEXT         Git URL or path for IaC policies
```

### Activate a Space

```
Usage: thothctl space activate SPACE_NAME

  Set a space as the active context
```

### Deactivate a Space

```
Usage: thothctl space deactivate

  Clear the active space context
```

This removes the currently active space, allowing you to work without any space context or switch to a different space.

### List Projects with Space Information

```
Usage: thothctl list projects [OPTIONS]

  List all projects managed by thothctl

Options:
  -s, --show-space  Show space information for each project  [default: True]
```

## Basic Usage

### Creating a Space

```bash
thothctl init space --space-name development --description "Development environment" --vcs-provider github --terraform-auth token --orchestration-tool terragrunt
```

This creates a new space named "development" with GitHub as the VCS provider, token-based Terraform registry authentication, and Terragrunt as the orchestration tool.

### Creating a Project in a Space

```bash
thothctl init project --project-name my_project --space development
```

This creates a new project named "my_project" in the "development" space, inheriting all the space's configurations.

### Listing Spaces

```bash
thothctl list spaces
```

This displays a list of all spaces with their project counts.

### Showing Space Configuration

```bash
thothctl space show platform-team
```

This displays a full summary of the space including VCS provider, Terraform registry, orchestration tool, governance policies, associated projects, and credentials status.

### Listing Projects with Space Information

```bash
thothctl list projects
```

This displays a list of all projects with their associated spaces.

### Removing a Space

```bash
thothctl remove space --space-name development
```

This removes the "development" space but keeps its projects (they will no longer be associated with any space).

### Removing a Space and Its Projects

```bash
thothctl remove space --space-name development --remove-projects
```

This removes the "development" space and all projects associated with it.

## Space Structure

Space configuration is managed through the global registry at `~/.thothcf/spaces.toml`, which is the single source of truth for all space definitions. Each space also has an associated directory structure:

```
~/.thothcf/
├── spaces.toml                    # Global registry (single source of truth)
├── active_space                   # Currently active space name (plain text file)
└── spaces/<space_name>/
    ├── metadata.toml              # Directory identification (name, created_at, config_source)
    ├── credentials/               # Encrypted VCS/TF/cloud credentials (.enc files)
    ├── configs/                   # Space-level policy overrides
    │   └── scan_policy.toml       # Scan enforcement + supply chain thresholds
    ├── vcs/                       # Version control system configurations
    │   └── <provider>.toml        # Provider-specific configuration
    ├── terraform/                 # Terraform registry configurations
    │   └── registry.toml          # Registry configuration
    └── orchestration/             # Orchestration tool configurations
        └── <tool>.toml            # Tool-specific configuration
```

## Configuration Files

### spaces.toml (Global Registry)

The main configuration file at `~/.thothcf/spaces.toml` stores all space definitions:

```toml
[spaces.development]
name = "development"
description = "Development environment"
created_at = "2024-01-15T10:30:00Z"

[spaces.development.version_control]
provider = "github"

[spaces.development.terraform]
registry = "https://registry.terraform.io"
auth_method = "token"

[spaces.development.orchestration]
tool = "terragrunt"

[spaces.development.projects]
[spaces.development.projects.my-app]
registered_at = "2024-01-16T09:00:00Z"
[spaces.development.projects.vpc-network]
registered_at = "2024-01-17T14:00:00Z"
[spaces.development.projects.ecs-service]
registered_at = "2024-01-18T11:00:00Z"

[spaces.production]
name = "production"
description = "Production environment"
created_at = "2024-02-01T09:00:00Z"

[spaces.production.version_control]
provider = "azure_repos"

[spaces.production.terraform]
registry = "https://registry.terraform.io"
auth_method = "env_var"

[spaces.production.orchestration]
tool = "terragrunt"

[spaces.production.governance]
policy_repo = "https://github.com/myorg/iac-policies.git"

[spaces.production.projects]
[spaces.production.projects.vpc-network]
registered_at = "2024-02-02T10:00:00Z"
[spaces.production.projects.eks-cluster]
registered_at = "2024-02-03T15:00:00Z"
```

!!! note "Namespace Scoping"
    Projects are registered under `spaces.<name>.projects` in the global `spaces.toml`. This enables **namespace scoping** — the same project name can exist in different spaces (e.g., `vpc-network` in both `development` and `production`). Each space acts as an independent namespace for project names.

### VCS Configuration

Example GitHub configuration (`vcs/github.toml`):

```toml
[provider]
provider = "github"

[settings]
organization = ""
project = ""
repository = ""
branch = "main"
auth_method = "pat"  # Options: pat, oauth, ssh
```

### Terraform Configuration

Example Terraform registry configuration (`terraform/registry.toml`):

```toml
[registry]
url = "https://registry.terraform.io"
auth_method = "token"
token_env_var = ""
token = ""

[providers]
[providers.aws]
version = "~> 4.0"
source = "hashicorp/aws"

[providers.azure]
version = "~> 3.0"
source = "hashicorp/azurerm"
```

### Orchestration Configuration

Example Terragrunt configuration (`orchestration/terragrunt.toml`):

```toml
[terragrunt]
version = "latest"

[terragrunt.remote_state]
backend = "s3"

[terragrunt.remote_state.config]
bucket = ""
key = "${path_relative_to_include()}/terraform.tfstate"
region = "us-east-1"
encrypt = true

[terragrunt.generate]
provider = true
backend = true
```

## Best Practices

1. **Logical Grouping**: Create spaces based on logical groupings (environments, teams, products)
2. **Consistent Naming**: Use consistent naming conventions for spaces
3. **Documentation**: Include descriptive information for each space
4. **Version Control**: Use the same VCS provider for all projects in a space
5. **Credential Management**: Store credentials securely and reference them in space configurations
6. **Namespace Awareness**: Leverage namespace scoping to use consistent project names across environments (e.g., `vpc-network` in both `dev` and `prod` spaces)
7. **Deactivate When Switching Context**: Use `thothctl space deactivate` before switching between unrelated workstreams to avoid accidental cross-space operations
8. **Non-Interactive Setup**: For CI/CD pipelines, use environment variables or flags for credential setup to avoid interactive prompts

## Examples

### Development Space

```bash
thothctl init space \
  --space-name development \
  --description "Development environment" \
  --vcs-provider github \
  --terraform-auth token \
  --orchestration-tool terragrunt
```

### Production Space

```bash
thothctl init space \
  --space-name production \
  --description "Production environment" \
  --vcs-provider azure_repos \
  --terraform-auth env_var \
  --orchestration-tool terragrunt
```

### Team Space

```bash
thothctl init space \
  --space-name data-team \
  --description "Data Engineering Team" \
  --vcs-provider gitlab \
  --terraform-auth token \
  --orchestration-tool terramate
```

## Troubleshooting

### Common Issues

- **Space Already Exists**: Ensure you're not trying to create a space that already exists
- **Missing Space**: Ensure the space exists when creating a project in it
- **Permission Issues**: Check permissions for the `.thothcf` directory
- **Configuration Errors**: Verify that space configuration files are valid

### Debugging

For more detailed logs, run ThothCTL with the `--debug` flag:

```bash
thothctl --debug init space --space-name development
```
