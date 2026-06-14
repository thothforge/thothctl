# Templates for Developers

> **Goal**: Start a new project quickly using pre-built, validated templates from your organization or ThothForge defaults.

## Quick Start

```bash
# Create a project from a default scaffold
thothctl init project --project-name my-infra --project-type terraform-terragrunt

# Create a CDK project (prompts for language)
thothctl init project --project-name my-app --project-type cdkv2

# Create from your organization's template catalog
thothctl init project --project-name my-service --project-type terraform --reuse --space my-team
```

## How It Works

When you run `thothctl init project`, the tool:

1. Fetches a scaffold template from GitHub (or your configured URL)
2. Creates the project directory with the full structure
3. Prompts you for project-specific values (name, region, environment, etc.)
4. Replaces `#{placeholder}#` expressions with your values
5. Initializes a Git repository

The result is a fully configured, production-ready project following your organization's standards.

## Two Ways to Get Templates

### 1. Default Scaffolds (no setup needed)

ThothForge provides default scaffold repositories for common project types. If you've configured a custom URL via `thothctl init template`, it takes precedence.

```bash
thothctl init project --project-name my-project --project-type <type>
```

| Type | Description |
|------|-------------|
| `terraform-terragrunt` | Terraform + Terragrunt orchestration |
| `terragrunt` | Standalone Terragrunt project |
| `terraform` | Plain Terraform project |
| `terraform_module` | Reusable Terraform module |
| `tofu` | OpenTofu project |
| `cdkv2` | AWS CDK v2 (prompts for language) |

**Resolution order**: Custom URL (`~/.thothcf/.thothctl_templates.toml`) → ThothForge default → local fallback.

### 2. Organization Templates (`--reuse`)

The `--reuse` flag uses a **different mechanism** — it connects directly to your team's VCS provider (GitHub or Azure DevOps) and dynamically discovers template repositories. No pre-registration needed; it lists repos from the org/project associated with your space.

```bash
# Browse and select from your team's VCS catalog
thothctl init project \
  --project-name my-service \
  --project-type terraform \
  --reuse \
  --space production-team
```

This will:
1. Connect to your VCS provider (using credentials saved in the space)
2. List available template repositories
3. Let you search/select a template
4. Clone it and configure it as your new project

#### Setting Up a Space (first time only)

```bash
# Create a space and configure VCS
thothctl init space --space-name my-team

# For GitHub-based templates
thothctl init project --project-name x --reuse --space my-team --github-username myorg

# For Azure DevOps
thothctl init project --project-name x --reuse --space my-team --az-org-name myorg
```

Credentials are saved securely for future use.

## After Project Creation

### Fill in Parameters

During creation, ThothCTL prompts for values defined by the template. Example:

```
? Project name: my-api-service
? Environment (dev|qa|stg|test|prod): dev
? AWS Region for deployment: us-east-1
? S3 bucket for Terraform state: my-api-service-tfstate
? Team owner: backend-team
```

These replace `#{placeholder}#` expressions throughout the project files.

### Batch Mode (CI/CD)

Skip prompts and use defaults:

```bash
thothctl init project \
  --project-name my-service \
  --project-type terraform-terragrunt \
  --batch
```

### Keep Your Project in Sync

If the template gets updated (new security rules, updated .kiro configs, etc.), sync your project:

```bash
# Check what changed upstream
thothctl project upgrade --dry-run

# Interactively pick which files to update
thothctl project upgrade --interactive

# Apply all updates
thothctl project upgrade --force
```

## Generating Components

Once inside a project, add new components based on the structure rules:

```bash
# Add a new Terraform module
thothctl generate component \
  --component-type modules \
  --component-name networking \
  --component-path ./modules
```

The component types come from the `[[project_structure.folders]]` section in your project's `.thothcf.toml`.

## CLI Reference

| Command | Purpose |
|---------|---------|
| `thothctl init project -p <name> -pt <type>` | Create project from default scaffold |
| `thothctl init project --reuse --space <name>` | Create from organization catalog |
| `thothctl project upgrade --dry-run` | Check for template updates |
| `thothctl project upgrade -i` | Interactive upgrade |
| `thothctl generate component` | Add component to existing project |
| `thothctl list templates` | Show available templates |

## Troubleshooting

**Template fetch fails**: The tool falls back to local templates. Check internet connectivity and that the repository URL is accessible. Use `--debug` for details.

**Missing parameters**: If `.thothcf.toml` doesn't have `[template_input_parameters]`, you'll get default prompts for project name, region, environment, and backend config.

**Upgrade shows no changes**: Your project is already in sync with the template (same commit hash).

## Related

- [Template Engine Overview](template_engine.md)
- [GitHub Scaffolds](github_templates.md)
- [For Platform Engineers](for_platform_engineers.md) — if you want to create templates for your team
