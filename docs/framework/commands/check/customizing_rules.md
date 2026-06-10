# Customizing Project Structure Rules

## Overview

ThothCTL validates project structure using rules defined in TOML files. You can override the built-in rules by placing a `.thothcf.toml` file in your project root with a `[project_structure]` section.

## How Rule Resolution Works

```
thothctl check project iac
         │
         ▼
  Is there a .thothcf.toml in the project directory
  with a [project_structure] section?
         │
    ┌────┴────┐
    │ YES     │ NO
    ▼         ▼
  Use your    Check [thothcf].project_type
  custom      in .thothcf.toml
  rules       │
              ├─ "terragrunt" → built-in terragrunt template
              ├─ (default)    → built-in stack template
              └─ -p module    → built-in module template
```

**Key point:** If your `.thothcf.toml` contains `[project_structure]`, it replaces the built-in rules entirely. There is no partial merge — you must define the complete set of rules you want enforced.

## Rule File Location

The override file must be:
- Named `.thothcf.toml`
- Located in the directory being checked (the project root, or the path passed with `-d`)

```bash
# Checks ./  for .thothcf.toml
thothctl check project iac

# Checks ./infra/ for .thothcf.toml
thothctl -d ./infra check project iac
```

## Schema Reference

```toml
[project_structure]
# Files required at the project root
root_files = [
    ".gitignore",
    "README.md",
    "main.tf"
]

# Folders to skip during validation
ignore_folders = [
    ".git",
    ".terraform",
    "node_modules"
]

# Folder rules (repeatable section)
[[project_structure.folders]]
name = "modules"          # Folder name
mandatory = true          # true = fail if missing, false = warn only
type = "root"             # "root" = top-level, "child" = nested
content = [               # Files required inside this folder
    "main.tf",
    "variables.tf",
    "outputs.tf"
]

[[project_structure.folders]]
name = "examples"
mandatory = true
type = "child"            # This folder is nested inside another
parent = "modules"        # Parent folder name

[[project_structure.folders]]
name = "complete"
mandatory = true
type = "child"
parent = "examples"       # Nested under examples (which is under modules)
content = [
    "main.tf",
    "README.md"
]
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `root_files` | Yes | List of files that must exist at project root |
| `ignore_folders` | No | Folders excluded from validation |
| `folders[].name` | Yes | Folder name to validate |
| `folders[].mandatory` | Yes | `true` = error if missing, `false` = informational |
| `folders[].type` | Yes | `"root"` (top-level) or `"child"` (nested) |
| `folders[].parent` | If type=child | Name of the parent folder |
| `folders[].content` | No | Files required inside this folder |

### Folder Hierarchy

Use `type` and `parent` to define nested structures:

```toml
# Validates: project/modules/networking/main.tf
[[project_structure.folders]]
name = "modules"
mandatory = true
type = "root"
content = ["main.tf", "variables.tf", "outputs.tf"]

# Validates: project/modules/examples/
[[project_structure.folders]]
name = "examples"
mandatory = true
type = "child"
parent = "modules"

# Validates: project/modules/examples/complete/main.tf
[[project_structure.folders]]
name = "complete"
mandatory = true
type = "child"
parent = "examples"
content = ["main.tf", "terraform.tfvars"]
```

## End-to-End Example

**Goal:** Enforce that all projects have a `security/` folder with `iam.tf` and `policies.tf`, plus a `monitoring/` folder.

### 1. Create `.thothcf.toml` in your project root

```toml
[project_structure]
root_files = [
    ".gitignore",
    "README.md",
    "root.hcl",
    ".pre-commit-config.yaml"
]

ignore_folders = [
    ".git",
    ".terraform",
    ".terragrunt-cache"
]

[[project_structure.folders]]
name = "modules"
mandatory = true
type = "root"
content = ["main.tf", "variables.tf", "outputs.tf"]

[[project_structure.folders]]
name = "security"
mandatory = true
type = "root"
content = ["iam.tf", "policies.tf"]

[[project_structure.folders]]
name = "monitoring"
mandatory = true
type = "root"
content = ["dashboards.tf", "alarms.tf"]

[[project_structure.folders]]
name = "environments"
mandatory = true
type = "root"

[[project_structure.folders]]
name = "docs"
mandatory = false
type = "root"
```

### 2. Run validation

```bash
# Soft mode (reports issues, exit 0)
thothctl check project iac -m soft

# Strict mode (fails CI if structure doesn't match)
thothctl check project iac -m strict
```

### 3. Expected output

```
╭─────────────────────────────────────────────────────────────────╮
│ 🏗️ Infrastructure as Code Stack Structure Check                │
╰─────────────────────────────────────────────────────────────────╯
Using Custom options

                        🏗️ Root Structure
╭──────────────┬──────┬──────────┬──────────┬─────────────────────╮
│ Item         │ Type │ Required │ Status   │ Details             │
├──────────────┼──────┼──────────┼──────────┼─────────────────────┤
│ modules      │ 📁   │ Required │ ✅ Pass  │ .                   │
│ security     │ 📁   │ Required │ ✅ Pass  │ .                   │
│ monitoring   │ 📁   │ Required │ ❌ Fail  │ Folder missing      │
│ environments │ 📁   │ Required │ ✅ Pass  │ .                   │
│ docs         │ 📁   │ Optional │ ⚠️ Warn  │ Not found           │
╰──────────────┴──────┴──────────┴──────────┴─────────────────────╯
```

## Built-in Templates

ThothCTL ships with three built-in templates. Use these as starting points for customization:

### Stack (default)

Used when running `thothctl check project iac -p stack` without a local override.

| Root files | Mandatory folders |
|-----------|-------------------|
| `.gitignore`, `.pre-commit-config.yaml`, `README.md`, `root.hcl` | `common`, `docs`, `modules`, `stacks` |

### Stack (terragrunt variant)

Used when `.thothcf.toml` has `[thothcf] project_type = "terragrunt"`.

Same as default stack but with adjusted `stacks/` content requirements (includes `terragrunt.hcl`).

### Module

Used when running `thothctl check project iac -p module`.

| Root files | Mandatory folders |
|-----------|-------------------|
| `.git`, `.gitignore`, `.pre-commit-config.yaml`, `README.md` | `docs`, `examples` (with `complete/` child) |

To see the full definition:
```bash
cat $(python -c "import thothctl; import os; print(os.path.dirname(thothctl.__file__))")/common/.thothcf_project.toml
```

## Scaffold Templates (for `init project`)

Scaffold templates use the same `.thothcf.toml` format but add a `[template_input_parameters]` section for variable substitution during project creation.

### Template Input Parameters

```toml
[template_input_parameters.project_name]
template_value = "#{ProjectName}#"     # Placeholder in template files
condition = "^[a-z][a-z0-9_-]+$"       # Regex validation
description = "Project name (lowercase, hyphens allowed)"

[template_input_parameters.region]
template_value = "#{Region}#"
condition = "^[a-z]{2}-[a-z]+-\\d$"
description = "AWS region (e.g., us-east-1)"

[template_input_parameters.environment]
template_value = "#{Environment}#"
condition = "(dev|staging|prod)"
description = "Target environment"
```

When generating from a template, ThothCTL:
1. Parses `[template_input_parameters]` from the template's `.thothcf.toml`
2. Prompts for each parameter (or accepts `--variables` JSON)
3. Validates input against `condition` regex
4. Replaces all `#{ParameterName}#` occurrences in generated files

### IDP Metadata

Templates can include metadata for Internal Developer Platform catalog integration:

```toml
[idp]
tags = ["terraform", "aws", "networking", "module"]

[idp.spec]
lifecycle = "production"
owner = "platform-team"
system = "IaCPlatform"
type = "template"
```

This metadata is used by `thothctl list templates` and can be published to Backstage or similar catalogs.

## Tips

- **Start from a built-in template** — Copy the default and modify it rather than writing from scratch.
- **Use `mandatory = false`** for folders you want to track but not enforce yet (shows as warnings in soft mode).
- **CI/CD** — Commit your `.thothcf.toml` to version control so all team members validate against the same rules.
- **Per-space standards** — Store your organization's `.thothcf.toml` in the Space's `templates/` directory and copy it into new projects during `init project`.
