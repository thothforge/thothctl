# Init Space Command

## Overview

The `init space` command creates and configures workspaces (spaces) for organizing multiple ThothCTL projects. Spaces provide isolated contexts with their own credentials, VCS configuration, governance policies, and scan thresholds.

## Usage

```bash
# Interactive creation (prompts for details)
thothctl init space --name "production" --description "Production environment"

# Non-interactive creation (CI/CD pipelines)
thothctl init space --name "production" \
  --description "Production environment" \
  --vcs-provider github \
  --vcs-token ghp_xxxxxxxxxxxx \
  --vcs-org myorg \
  --credential-password mysecretpassword \
  --policy-repo https://github.com/myorg/iac-policies.git
```

## Options

### Standard Options

| Option | Type | Description |
|--------|------|-------------|
| `--name, -n` | Text | Name of the space (required) |
| `--description, -d` | Text | Human-readable description |
| `--vcs-provider` | Choice | VCS provider: `github`, `gitlab`, `azure_repos` |
| `--orchestration-tool` | Choice | Orchestration tool: `terragrunt`, `terramate`, `none` |
| `--terraform-registry` | Text | Terraform registry URL |

### Non-Interactive Options

These options enable fully automated space creation without interactive prompts, suitable for CI/CD pipelines and scripted environments:

| Option | Type | Description |
|--------|------|-------------|
| `--vcs-token` | Text | VCS personal access token (GitHub PAT, GitLab token, Azure DevOps PAT) |
| `--vcs-org` | Text | VCS organization or namespace |
| `--credential-password` | Text | Password used to encrypt stored credentials |
| `--policy-repo` | Text | Git URL or local path for organization-level IaC policies |

## Environment Variables

Environment variables can substitute for non-interactive CLI flags. They are consumed during `init space` and take precedence over interactive prompts (but CLI flags take precedence over env vars):

| Variable | Equivalent Flag | Description |
|----------|----------------|-------------|
| `THOTH_SPACE_TOKEN` | `--vcs-token` | VCS personal access token |
| `THOTH_SPACE_ORG` | `--vcs-org` | VCS organization name |
| `THOTH_SPACE_PASSWORD` | `--credential-password` | Credential encryption password |
| `THOTH_SPACE_TF_TOKEN` | *(used at registry auth time)* | Terraform registry authentication token |

**Precedence order:** CLI flag > environment variable > interactive prompt.

## Features

- **Space Management**: Create isolated workspaces with namespace-scoped project registration
- **Project Organization**: Group related projects under `spaces.<name>.projects` in `spaces.toml`
- **Environment Separation**: Separate dev, staging, production with distinct credentials and policies
- **Non-Interactive Setup**: Full CI/CD automation via flags and environment variables
- **Configuration Isolation**: Independent credentials, VCS config, and scan policies per space
- **Policy Overrides**: Space-level `configs/scan_policy.toml` for scan enforcement thresholds

## Space Structure

After creation, the space directory layout is:

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

### Key Files

- **`spaces.toml`** — Single source of truth. All space configuration (name, description, VCS, terraform, orchestration, governance, projects) is stored here under `[spaces.<name>]`.
- **`metadata.toml`** — Minimal directory identification file. Contains only `name`, `created_at`, and `config_source = "spaces.toml"`. Does NOT contain configuration.
- **`configs/scan_policy.toml`** — Space-level overrides for scan enforcement mode and supply chain thresholds.

## Examples

### Create Production Space (Interactive)

```bash
thothctl init space --name "production" \
  --description "Production infrastructure projects" \
  --vcs-provider "github"
```

The wizard will prompt for remaining details (PAT token, organization, registry).

### Create Development Space

```bash
thothctl init space --name "development" \
  --description "Development and testing projects" \
  --vcs-provider "github" \
  --orchestration-tool "terragrunt"
```

### CI/CD Usage (Fully Non-Interactive)

For automated pipelines where no interactive input is available:

```bash
# Using CLI flags
thothctl init space --name "ci-production" \
  --description "Production space for CI" \
  --vcs-provider github \
  --vcs-token ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
  --vcs-org myorg \
  --credential-password "${VAULT_CREDENTIAL_PASSWORD}" \
  --policy-repo https://github.com/myorg/iac-policies.git \
  --terraform-registry https://app.terraform.io \
  --orchestration-tool terragrunt
```

```bash
# Using environment variables
export THOTH_SPACE_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export THOTH_SPACE_ORG="myorg"
export THOTH_SPACE_PASSWORD="vault-managed-secret"
export THOTH_SPACE_TF_TOKEN="team-xxxxxxxxxxxx.atlasv1.xxxxxxxxxx"

thothctl init space --name "ci-production" \
  --description "Production space for CI" \
  --vcs-provider github \
  --policy-repo https://github.com/myorg/iac-policies.git
```

#### GitHub Actions Example

```yaml
name: Setup ThothCTL Space
on:
  workflow_dispatch:

jobs:
  setup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install ThothCTL
        run: pip install thothctl

      - name: Create space (non-interactive)
        env:
          THOTH_SPACE_TOKEN: ${{ secrets.GH_PAT }}
          THOTH_SPACE_ORG: ${{ github.repository_owner }}
          THOTH_SPACE_PASSWORD: ${{ secrets.CREDENTIAL_PASSWORD }}
          THOTH_SPACE_TF_TOKEN: ${{ secrets.TF_API_TOKEN }}
        run: |
          thothctl init space --name "production" \
            --description "Production infrastructure" \
            --vcs-provider github \
            --policy-repo https://github.com/${{ github.repository_owner }}/iac-policies.git \
            --terraform-registry https://app.terraform.io \
            --orchestration-tool terragrunt

          thothctl space activate production
```

### List All Spaces

```bash
thothctl list spaces
```

## Related Commands

- [`init project`](../init/init.md) - Initialize projects within a space
- [`list spaces`](../list/list_spaces.md) - List available spaces
- [`space activate`](../space/space_overview.md) - Set active space
- [`space deactivate`](../space/space_overview.md) - Clear active space
- [`space show`](../space/space_overview.md) - Display space configuration
- [`space update`](../space/space_overview.md) - Modify space settings
- [`remove space`](../remove/remove_space.md) - Remove spaces
