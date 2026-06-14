# Templates for Platform Engineers

> **Goal**: Create reusable, governed infrastructure templates from working projects and publish them for self-service consumption.

## Quick Start

```bash
# Convert a working project into a reusable template
cd my-reference-architecture
thothctl project convert --make-template --template-project-type terraform-terragrunt

# Test it
thothctl project convert --make-project --template-project-type terraform-terragrunt

# Publish to Git
git init && git add . && git commit -m "feat: initial template"
git remote add origin https://github.com/myorg/my-template.git
git push -u origin main
```

## The Template Engine

The template engine converts concrete values in your project into parameterized `#{placeholder}#` expressions, creating a reusable pattern that other developers can instantiate with their own values.

### How Conversion Works

**Before** (working project):
```hcl
bucket = "my-api-prod-tfstate"
region = "us-east-1"
tags = { Team = "backend", Environment = "prod" }
```

**After** `--make-template`:
```hcl
bucket = "#{project}#-#{environment}#-tfstate"
region = "#{deployment_region}#"
tags = { Team = "#{owner}#", Environment = "#{environment}#" }
```

The engine reads `[project_properties]` from `.thothcf.toml` to know which values to parameterize.

## Step-by-Step: Creating a Template

### 1. Prepare Your Project

Ensure your project is production-ready and has a `.thothcf.toml` with project properties:

```toml
[thothcf]
project_id = "ecs-platform"

[project_properties]
project = "ecs-platform"
environment = "prod"
region = "us-east-1"
backend_bucket = "ecs-platform-tfstate"
backend_region = "us-east-2"
dynamodb_backend = "db-terraform-lock"
owner = "platform-team"
client = "myorg"
```

### 2. Convert to Template

```bash
thothctl project convert --make-template --template-project-type terraform-terragrunt
```

This:
- Scans all eligible files (skips binaries, `.git`, `.terraform`, etc.)
- Replaces values from `[project_properties]` with `#{key}#` placeholders
- Saves the template to `~/.thothcf/ecs-platform/`
- Backs up the original config
- Registers file hashes in the global registry

### 3. Define Input Parameters (recommended)

Add `[template_input_parameters]` to `.thothcf.toml` for validation and better prompts when developers use the template:

```toml
[template_input_parameters.project]
template_value = "#{project}#"
condition = "^[a-z0-9-]+$"
description = "Project name (lowercase, hyphens allowed)"

[template_input_parameters.environment]
template_value = "#{environment}#"
condition = "(dev|qa|stg|prod)"
description = "Target environment"

[template_input_parameters.region]
template_value = "#{deployment_region}#"
condition = "^[a-z]{2}-[a-z]+-\\d$"
description = "AWS deployment region"

[template_input_parameters.backend_bucket]
template_value = "#{backend_bucket}#"
condition = "^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"
description = "S3 bucket for Terraform state"

[template_input_parameters.owner]
template_value = "#{owner}#"
condition = "^[a-zA-Z0-9_-]+$"
description = "Team or owner name"
```

### 4. Define Project Structure Rules

Enforce required files/folders so developers don't accidentally break the pattern:

```toml
[project_structure]
root_files = [".gitignore", "README.md", ".thothcf.toml", ".pre-commit-config.yaml"]
ignore_folders = [".git", ".terraform", ".terragrunt-cache"]

[[project_structure.folders]]
name = "stacks"
mandatory = true
type = "root"

[[project_structure.folders]]
name = "modules"
mandatory = true
type = "root"
content = ["main.tf", "variables.tf", "outputs.tf"]
```

### 5. Test the Template

```bash
# Create a project from your template to verify it works
thothctl project convert --make-project --template-project-type terraform-terragrunt

# Validate the output
terraform init
terraform validate
```

### 6. Publish to Git

```bash
git init
git add .
git commit -m "feat: ecs-platform template v1.0.0"
git remote add origin https://github.com/myorg/ecs-platform-template.git
git push -u origin main
git tag -a v1.0.0 -m "Initial release"
git push origin v1.0.0
```

### 7. Make It Discoverable

**Option A — Register as custom scaffold URL:**
```bash
# Any developer can now use it via init project
thothctl init template --project-type terraform-terragrunt \
  --template-url https://github.com/myorg/ecs-platform-template.git
```

**Option B — Add to a space (team-wide):**

Place the template repo in your team's GitHub org or Azure DevOps project. Developers discover it with:
```bash
thothctl init project --reuse --space my-team
```

**Option C — Register in Backstage:**

Create a `catalog-info.yaml` and a Backstage scaffolder template for portal-based self-service. See [Platform Engineering Templates](../framework/use_cases/platform_engineering_templates.md) for the full Backstage integration guide.

## Template Maintenance

### Updating Templates

When you improve the template (new security rules, updated configs):

1. Update the template source project
2. Re-run `thothctl project convert --make-template`
3. Push changes to Git with a new tag

Developers sync via:
```bash
thothctl project upgrade --dry-run    # check
thothctl project upgrade              # apply
```

### File Hash Registry

ThothCTL tracks file hashes in `~/.thothcf/.thothcf.toml`. When a developer runs `--make-project`, it can detect which files have drifted from the template and suggest updates.

## Placeholder Rules

### What Gets Replaced

- Values from `[project_properties]` that are ≥4 characters are replaced with word-boundary matching
- Values ≤3 characters (e.g., "dev", "aws") are only replaced in assignment contexts (`key = "value"`)
- Sorting is longest-first to avoid partial replacements

### What Gets Skipped

- Binary files (PNG, PDF, ZIP, etc.)
- Directories: `.git`, `.terraform`, `.terragrunt-cache`, `node_modules`, `__pycache__`
- Files: `.terraform.lock.hcl`, `catalog-info.yaml`, `.gitignore`

### Manual Placeholders

You can also add `#{placeholder}#` expressions manually for values the automatic conversion doesn't catch:

```hcl
# Manually parameterized
vpc_cidr = "#{vpc_cidr}#"
max_az_count = #{max_az_count}#
```

Just make sure to add corresponding entries in `[template_input_parameters]`.

## CLI Reference

| Command | Purpose |
|---------|---------|
| `thothctl project convert --make-template` | Convert project → parameterized template |
| `thothctl project convert --make-project` | Instantiate template → working project |
| `thothctl init template --project-type X --template-url Y` | Register custom scaffold URL |
| `thothctl project upgrade --dry-run` | Check what would update in downstream projects |
| `thothctl generate component` | Test component generation from structure rules |
| `thothctl check project iac` | Validate project against structure rules |

## Best Practices

1. **Start from a working project** — don't write templates from scratch; convert a proven reference architecture
2. **Keep parameters minimal** — 5–10 parameters max; over-parameterization makes templates harder to use
3. **Validate strictly** — use specific regex in `condition` to catch mistakes at input time
4. **Include docs** — README, architecture decisions, and parameter descriptions in the template
5. **Tag releases** — use semver so downstream projects can pin to stable versions
6. **Test round-trip** — always verify `make-template` → `make-project` → `terraform validate` works

## Related

- [Template Engine Overview](template_engine.md)
- [For Developers](for_developers.md) — how developers consume your templates
- [Platform Engineering Templates](../framework/use_cases/platform_engineering_templates.md) — full end-to-end guide with Backstage
- [Project Convert Reference](../framework/commands/project/project_convert.md)
