# Space Configuration

A Space in ThothForge represents a logical container for your Internal Developer Platform (IDP) resources. It defines the context in which your projects, credentials, and governance policies operate.

## Configuration Model

ThothCTL uses a **single source of truth** for all space configuration: the `spaces.toml` file located at `~/.thothcf/spaces.toml`. Individual space directories contain only operational files (credentials, policy overrides) and a minimal `metadata.toml` for directory identification.

## spaces.toml Schema

All space configuration lives under the `[spaces.<name>]` namespace:

```toml
[spaces.my-space]
name = "my-space"
description = "Production environment"
created_at = "2026-07-27T16:45:00"

[spaces.my-space.version_control]
provider = "github"

[spaces.my-space.terraform]
registry = "https://registry.terraform.io"
auth_method = "none"

[spaces.my-space.orchestration]
tool = "terragrunt"

[spaces.my-space.governance]
policy_repo = "https://github.com/org/iac-policies.git"

[spaces.my-space.projects]
[spaces.my-space.projects.vpc-stack]
registered_at = "2026-07-27T16:50:00"
```

## Configuration Sections

### Root Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | String | Space identifier (matches the key) |
| `description` | String | Human-readable description |
| `created_at` | DateTime | ISO 8601 creation timestamp |

### version_control

Configures the VCS provider for the space.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `provider` | String | `github`, `gitlab`, `azure_repos` | VCS provider |

### terraform

Configures Terraform registry access.

| Field | Type | Description |
|-------|------|-------------|
| `registry` | String | Registry URL (e.g., `https://registry.terraform.io`) |
| `auth_method` | String | Authentication method: `none`, `token`, `oidc` |

### orchestration

Configures the IaC orchestration tool.

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `tool` | String | `terragrunt`, `terramate`, `none` | Orchestration tool |

### governance

Configures organization-level policy enforcement.

| Field | Type | Description |
|-------|------|-------------|
| `policy_repo` | String | Git URL or local path to OPA/Rego policy repository |

### projects

Namespace-scoped project registry. Projects are registered under their parent space.

| Field | Type | Description |
|-------|------|-------------|
| `<project-name>.registered_at` | DateTime | When the project was registered to this space |

## Directory Structure

```
~/.thothcf/
├── spaces.toml              # Single source of truth for all space config
├── active_space             # Currently active space name (plain text file)
├── .thothcf.toml            # Global project registry (legacy, backward compat)
└── spaces/
    └── <space-name>/
        ├── metadata.toml    # Directory identification (name, created_at, config_source)
        ├── credentials/     # Encrypted VCS/TF/cloud credentials (.enc files)
        ├── configs/         # Space-level policy overrides
        │   └── scan_policy.toml  # Scan enforcement + supply chain thresholds
        ├── vcs/             # Provider-specific config (github.toml, etc.)
        ├── terraform/       # Registry config (registry.toml)
        └── orchestration/   # Tool config (terragrunt.toml, etc.)
```

### metadata.toml

A minimal identification file inside each space directory. It does **not** contain configuration — only enough to identify the directory and link it back to `spaces.toml`.

```toml
name = "my-space"
created_at = "2026-07-27T16:45:00"
config_source = "spaces.toml"
```

### configs/scan_policy.toml

Space-level overrides for security scanning and supply chain thresholds:

```toml
[enforcement]
mode = "hard"           # "soft" (report only) or "hard" (fail pipeline)
fail_on_severity = "high"

[supply_chain]
max_staleness_days = 90
require_pinned_versions = true
```

## Environment Variables

For non-interactive setup (CI/CD pipelines), use environment variables instead of interactive prompts:

| Variable | Description |
|----------|-------------|
| `THOTH_SPACE_TOKEN` | VCS personal access token (GitHub PAT, GitLab token, Azure DevOps PAT) |
| `THOTH_SPACE_ORG` | VCS organization name |
| `THOTH_SPACE_PASSWORD` | Password for credential encryption |
| `THOTH_SPACE_TF_TOKEN` | Terraform registry authentication token |

These variables are consumed during `thothctl init space` and `thothctl space update` to skip interactive prompts.

## Multi-Space Configuration Example

A `spaces.toml` with multiple environments:

```toml
[spaces.development]
name = "development"
description = "Development and testing"
created_at = "2026-07-01T10:00:00"

[spaces.development.version_control]
provider = "github"

[spaces.development.terraform]
registry = "https://registry.terraform.io"
auth_method = "none"

[spaces.development.orchestration]
tool = "terragrunt"

[spaces.development.projects]
[spaces.development.projects.networking]
registered_at = "2026-07-02T09:00:00"
[spaces.development.projects.compute]
registered_at = "2026-07-03T14:30:00"

# ---

[spaces.production]
name = "production"
description = "Production infrastructure"
created_at = "2026-07-01T10:05:00"

[spaces.production.version_control]
provider = "github"

[spaces.production.terraform]
registry = "https://app.terraform.io"
auth_method = "token"

[spaces.production.orchestration]
tool = "terragrunt"

[spaces.production.governance]
policy_repo = "https://github.com/myorg/iac-policies.git"

[spaces.production.projects]
[spaces.production.projects.vpc-stack]
registered_at = "2026-07-05T11:00:00"
[spaces.production.projects.eks-cluster]
registered_at = "2026-07-06T08:15:00"
```

## Managing Spaces

### Creating a Space

```bash
thothctl init space --name "production" --description "Production environment" --vcs-provider github
```

### Listing Spaces

```bash
thothctl list spaces
```

### Showing Space Details

```bash
thothctl space show my-space
```

Displays: space name, description, status (active/inactive), VCS provider, Terraform registry, orchestration tool, governance policy, associated projects, and credentials status.

### Activating a Space

```bash
thothctl space activate production
```

### Deactivating a Space

```bash
thothctl space deactivate
```

### Updating a Space

```bash
thothctl space update production --policy-repo https://github.com/myorg/policies.git
thothctl space update production --orchestration-tool terragrunt
```

### Deleting a Space

```bash
thothctl remove space -sn my-space
```

## Using Spaces with Projects

Projects are registered under their parent space in `spaces.toml`:

```bash
# Create a project in a specific space
thothctl init project --space production --name vpc-stack

# This adds to spaces.toml:
# [spaces.production.projects.vpc-stack]
# registered_at = "2026-07-27T16:50:00"
```

## Backward Compatibility

The legacy format (individual `space.toml` files per directory with `[space]`, `[[registries]]`, `[endpoints]` sections) is still recognized for reading. On first access, ThothCTL will offer to migrate legacy configurations to the new `spaces.toml` format. The global `.thothcf.toml` project registry is maintained for backward compatibility but new project registrations use the namespace-scoped `spaces.<name>.projects` section.
