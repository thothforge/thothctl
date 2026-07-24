# Space Command

The `space` command manages ThothCTL spaces — logical contexts that group configuration, credentials, VCS providers, and governance policies. Spaces enable multi-team and multi-environment workflows.

## Overview

Spaces provide:

- Active context for credential resolution (Azure DevOps, GitHub, GitLab)
- Organization-level policy repository configuration
- Terraform registry and orchestration tool defaults
- Team-level isolation for projects

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `activate` | Set a space as the active context |
| `show` | Display space configuration summary |
| `update` | Modify space settings (policy repo, VCS, tools) |

## Usage

```bash
# Activate a space
thothctl space activate my-space

# Show space configuration
thothctl space show my-space

# Update space settings
thothctl space update my-space --policy-repo https://github.com/myorg/policies.git
thothctl space update my-space --vcs-provider azure_repos
thothctl space update my-space --orchestration-tool terragrunt
```

## Subcommand Reference

### activate

Set a space as the active context. All subsequent commands use this space for credential resolution and defaults.

```bash
thothctl space activate <SPACE_NAME>
```

**Effect:**
- Writes space name to `~/.thothcf/active_space`
- New projects default to this space unless `--space` is specified
- Commands that need VCS credentials (e.g., `--post-to-pr`) use this space's stored PAT

**Example:**
```bash
$ thothctl space activate lab-azure
🌐 Active space set to 'lab-azure'
New projects will use this space by default unless --space is specified.
```

---

### show

Display the full configuration of a space.

```bash
thothctl space show <SPACE_NAME>
```

**Displays:**
- Space name and version
- VCS provider and settings (organization, project, repository)
- Terraform registry configuration
- Orchestration tool (terragrunt, terramate, none)
- Policy repository URL (if configured)
- Credentials status (encrypted PAT present/missing)

---

### update

Modify space configuration settings.

```bash
thothctl space update <SPACE_NAME> [OPTIONS]
```

| Option | Type | Description |
|--------|------|-------------|
| `-pr, --policy-repo` | Text | Git URL or local path for organization policies |
| `-tr, --terraform-registry` | Text | Terraform registry URL |
| `-ot, --orchestration-tool` | Choice | `terragrunt`, `terramate`, or `none` |
| `-vcs, --vcs-provider` | Choice | `azure_repos`, `github`, or `gitlab` |
| `-d, --description` | Text | Space description |

**Examples:**
```bash
# Set organization policy repository
thothctl space update production --policy-repo https://github.com/myorg/iac-policies.git

# Change VCS provider
thothctl space update production --vcs-provider github

# Set orchestration tool
thothctl space update production --orchestration-tool terragrunt

# Update Terraform registry (private registry)
thothctl space update production --terraform-registry https://app.terraform.io
```

## Space Configuration Structure

Spaces are stored at `~/.thothcf/spaces/<space-name>/`:

```
~/.thothcf/spaces/my-space/
├── space.toml                    # Main configuration
├── vcs/
│   ├── azure_repos.toml          # Azure DevOps settings
│   ├── github.toml               # GitHub settings
│   └── gitlab.toml               # GitLab settings
├── credentials/
│   └── vcs.enc                   # Encrypted PAT token
├── terraform/
│   └── registry.toml             # Registry configuration
└── orchestration/
    └── terragrunt.toml           # Orchestration settings
```

### space.toml Example

```toml
[space]
name = "production"
version = "1.0.0"

[credentials]
path = "credentials"

[version_control]
path = "vcs"
default_provider = "azure_repos"
providers = ["azure_repos", "github", "gitlab"]

[terraform]
path = "terraform"
registry_url = "https://registry.terraform.io"
auth_method = "none"

[orchestration]
path = "orchestration"
default_tool = "terragrunt"
tools = ["terragrunt", "terramate", "none"]
```

### VCS Provider Configuration

#### Azure DevOps (`vcs/azure_repos.toml`)
```toml
provider = "azure_repos"

[settings]
organization = "myorg"
project = "infrastructure"
repository = "iac-modules"
branch = "main"
auth_method = "pat"
```

#### GitHub (`vcs/github.toml`)
```toml
provider = "github"

[settings]
organization = "myorg"
repository = "infrastructure"
branch = "main"
auth_method = "pat"
```

## Creating Spaces

Spaces are created with `thothctl init space`:

```bash
# Interactive creation
thothctl init space --space-name production

# The init wizard prompts for:
# - VCS provider (azure_repos, github, gitlab)
# - Organization/project details
# - PAT token (stored encrypted)
# - Terraform registry
# - Orchestration tool
```

## How Spaces Are Used

### Credential Resolution

When a command needs VCS credentials (e.g., `--post-to-pr`, `--reuse` for templates):

```
1. Check --space flag → use that space
2. Check active space (~/.thothcf/active_space) → use active
3. Check project .thothcf.toml [thothcf] space field → use project's space
4. Fail with "no space configured"
```

### Policy Repository

When `thothctl scan iac -t opa` needs policies:

```
1. Check --policy-dir flag → explicit path/URL
2. Check THOTH_ORG_POLICY env var → URL
3. Check active space → governance.policy_repo field
4. Check local ./policy directory → default
```

### PR Comments

When `--post-to-pr` is used:

```
1. Detect CI environment (Azure Pipelines, GitHub Actions)
2. Resolve space credentials for the VCS provider
3. Post scan summary as PR comment using the stored PAT
```

## Examples

### Multi-Environment Setup

```bash
# Create spaces for each environment
thothctl init space --space-name dev
thothctl init space --space-name staging
thothctl init space --space-name production

# Activate for current work
thothctl space activate dev

# Override for specific commands
thothctl scan iac --post-to-pr --space production
```

### Organization Policy Binding

```bash
# Bind org policies to a space
thothctl space update production \
  --policy-repo https://github.com/myorg/iac-policies.git

# Now any scan in this space auto-uses org policies
thothctl space activate production
thothctl scan iac -t opa  # Uses org policies automatically
```

## Related

- [Space Management Use Case](../../use_cases/space_management.md)
- [Init Space Command](../init/)
- [Scan Command — Policy Resolution](../scan/scan_overview.md)
- [Workflow Command](../workflow/workflow_overview.md)
