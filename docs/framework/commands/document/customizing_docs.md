# Customizing Documentation Standards

## Overview

ThothCTL generates IaC documentation using [terraform-docs](https://terraform-docs.io/) under the hood. You can use the built-in standards as-is, or provide a custom configuration file to control exactly what gets generated.

## Prerequisites

`terraform-docs` must be installed and available in your PATH:

```bash
# macOS
brew install terraform-docs

# Linux
curl -sSLo ./terraform-docs.tar.gz https://terraform-docs.io/dl/v0.18.0/terraform-docs-v0.18.0-$(uname)-amd64.tar.gz
tar -xzf terraform-docs.tar.gz
chmod +x terraform-docs
sudo mv terraform-docs /usr/local/bin/

# Verify
terraform-docs --version
```

## Built-in Documentation Standards

ThothCTL ships with two documentation standards, selected via `--mood`:

### `stacks` (default)

Designed for **full infrastructure projects** (Terragrunt stacks, root modules).

```bash
thothctl document iac -f terragrunt --mood stacks
```

**Characteristics:**
- Output mode: `replace` (overwrites entire README)
- Includes dependency graph SVG reference
- Shows: header, requirements, providers, modules, resources, inputs, outputs
- Sorted by: name

**Generated README structure:**
```markdown
<!-- BEGIN_TF_DOCS -->
# Module Header (from main.tf)

## Code Dependencies Graph
![Graph](./graph.svg)

## Requirements
## Providers
## Modules
## Resources
## Inputs
## Outputs
<!-- END_TF_DOCS -->
```

### `modules`

Designed for **reusable Terraform modules** with examples.

```bash
thothctl document iac -f terraform --mood modules
```

**Characteristics:**
- Output mode: `inject` (preserves content outside markers)
- Includes inline example from `examples/complete/main.tf`
- Shows: header, requirements, providers, modules, resources, inputs, outputs
- Sorted by: required
- Adds "DO NOT EDIT" notice

**Generated README structure:**
```markdown
# Your custom content here (preserved)

<!-- BEGIN_TF_DOCS -->
# Module Header

## Example
```hcl
// Content of examples/complete/main.tf inlined here
```

## Requirements
## Providers
## Inputs
## Outputs
<!-- END_TF_DOCS -->

# More custom content (preserved)
```

> **Note:** `resources` is a backward-compatible alias for `stacks`.

## README Markers (Required)

Your `README.md` must contain these markers for documentation injection to work:

```markdown
<!-- BEGIN_TF_DOCS -->
<!-- END_TF_DOCS -->
```

Without these markers, `terraform-docs` cannot determine where to write the output and **will silently skip the file**.

For new projects, add them to your README template:

```markdown
# My Module

Description of what this module does.

<!-- BEGIN_TF_DOCS -->
<!-- END_TF_DOCS -->
```

## Custom Configuration File

To fully customize the documentation output, create a `terraform-docs.yml` and pass it with `--config-file`:

```bash
thothctl document iac -f terraform --config-file ./terraform-docs.yml --recursive
```

When `--config-file` is provided, it **completely overrides** the built-in standard. ThothCTL passes it directly to terraform-docs.

### Minimal Custom Config

```yaml
formatter: "markdown table"

sections:
  show:
    - requirements
    - inputs
    - outputs

output:
  file: "README.md"
  mode: inject
  template: |-
    <!-- BEGIN_TF_DOCS -->
    {{ .Content }}
    <!-- END_TF_DOCS -->

sort:
  enabled: true
  by: required
```

### Full Custom Config (all options)

```yaml
formatter: "markdown table"

# Pull header text from this file
header-from: main.tf
footer-from: ""

# Which sections to include
sections:
  hide: []
  show:
    - header
    - requirements
    - providers
    - modules
    - resources
    - inputs
    - outputs
    - footer

# Custom content template with Golang template syntax
content: |-
  {{ .Header }}

  ## Architecture

  ![Architecture](./docs/architecture.png)

  ## Usage

  ```hcl
  module "this" {
    source = "git::https://github.com/myorg/this-module.git?ref=v1.0.0"

    // Required
    name        = "example"
    environment = "dev"
  }
  ```

  {{ .Requirements }}
  {{ .Providers }}
  {{ .Modules }}
  {{ .Resources }}
  {{ .Inputs }}
  {{ .Outputs }}
  {{ .Footer }}

# Output configuration
output:
  file: "README.md"
  mode: inject           # "inject" preserves content outside markers
                         # "replace" overwrites the entire file
  template: |-
    <!-- BEGIN_TF_DOCS -->
    {{ .Content }}
    <!-- END_TF_DOCS -->

# Sort inputs/outputs
sort:
  enabled: true
  by: required           # "required", "name", or "type"

# Display settings
settings:
  anchor: true
  color: true
  default: true
  description: false
  escape: true
  hide-empty: false
  html: true
  indent: 2
  lockfile: true
  required: true
  sensitive: true
  type: true
```

### Key Configuration Options

| Option | Values | Description |
|--------|--------|-------------|
| `output.mode` | `inject`, `replace` | `inject` preserves content outside markers; `replace` overwrites the file |
| `sort.by` | `name`, `required`, `type` | How to sort inputs and outputs |
| `header-from` | filename | File to extract the module description from (first comment block) |
| `content` | Go template | Full control over document structure using `{{ .Section }}` placeholders |
| `sections.show` | list | Which sections to include |
| `sections.hide` | list | Which sections to exclude |

### Available Template Placeholders

| Placeholder | Content |
|-------------|---------|
| `{{ .Header }}` | Module description from `header-from` file |
| `{{ .Footer }}` | Content from `footer-from` file |
| `{{ .Requirements }}` | Required Terraform and provider versions |
| `{{ .Providers }}` | Provider configurations |
| `{{ .Modules }}` | Child module calls |
| `{{ .Resources }}` | Resources created |
| `{{ .Inputs }}` | Input variables table |
| `{{ .Outputs }}` | Output values table |
| `{{ include "path" }}` | Inline content from a file |

## Per-Project Configuration

You can commit a `.terraform-docs.yml` in your project root. When using `--config-file`, point to it:

```bash
thothctl document iac -f terraform --config-file .terraform-docs.yml --recursive
```

Recommended project structure:

```
my-project/
├── .terraform-docs.yml    ← your custom standard
├── modules/
│   ├── networking/
│   │   ├── main.tf
│   │   └── README.md     ← generated
│   └── compute/
│       ├── main.tf
│       └── README.md     ← generated
└── stacks/
    └── prod/
        ├── main.tf
        └── README.md     ← generated
```

## Exclude Patterns

The `--exclude` option uses **substring matching** (not glob). Any directory whose path contains the pattern is skipped:

```bash
# Exclude .terraform caches and example directories
thothctl document iac -f terraform --recursive \
  --exclude .terraform \
  --exclude examples \
  --exclude test
```

⚠️ `--exclude modules` would skip **any** directory with "modules" in the path. Be specific.

## End-to-End Examples

### Generate docs for a Terragrunt stack project

```bash
# Default standard (stacks) + SVG dependency graph
thothctl document iac -f terragrunt --recursive

# With mermaid graph instead
thothctl document iac -f terragrunt --recursive --graph-type mermaid
```

### Generate docs for a reusable module

```bash
# Uses 'modules' standard — includes example code inline
thothctl document iac -f terraform --mood modules
```

### Use organization-wide standard

```bash
# Store your standard in the Space templates directory
# then reference it in all projects:
thothctl document iac -f terraform --recursive \
  --config-file ~/.thothcf/spaces/production/templates/terraform-docs.yml
```

### CI/CD: Auto-generate and commit

```yaml
- name: Generate documentation
  run: |
    thothctl document iac -f terragrunt --recursive --graph-type mermaid
    git diff --quiet || git commit -am "docs: auto-update IaC documentation"
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|---------|
| README not updated | Missing `<!-- BEGIN_TF_DOCS -->` markers | Add markers to your README.md |
| `command not found: terraform-docs` | Not installed | Install terraform-docs (see Prerequisites) |
| Empty output | No `.tf` files in directory | Ensure directory contains Terraform files |
| Sections missing | Not listed in `sections.show` | Add desired sections to your config |
| `include` fails | File path relative to module root | Use relative path from the documented directory |
