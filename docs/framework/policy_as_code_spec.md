# Design Spec: Organizational Policy Enforcement

## Problem

Today, `.thothcf.toml` lives in the project — project owners can weaken or remove structure rules. Organizations need a way to enforce standards that projects **cannot override** in CI/CD pipelines.

## Goals

1. Single policy repo for all governance (OPA + structure + naming/tagging rules)
2. Hierarchical rule merge: org → space → project (cannot weaken, can extend)
3. Works in CI/CD without special infrastructure (Git clone + env var)
4. Reuses existing `~/.thothcf/.policy_cache/` clone infrastructure

## Architecture

### Single Policy Repository

```
org-policies/                             # THOTH_ORG_POLICY repo
├── policy/                               # OPA/Rego (consumed by: scan iac -t opa)
│   ├── terraform/
│   │   ├── security.rego
│   │   ├── cost.rego
│   │   └── blast_radius.rego
│   └── main.rego
├── rules/                                # ThothCTL rules (consumed by: check project iac)
│   ├── base.toml                         # Applies to ALL project types
│   ├── terraform.toml                    # Extends base for --project-type terraform
│   ├── terraform-terragrunt.toml         # Extends base for terraform-terragrunt
│   ├── cdkv2.toml                        # Extends base for CDK projects
│   └── terraform_module.toml             # Extends base for modules
└── README.md
```

### Consumers

| Path | Consumed By | Already Works? |
|------|-------------|----------------|
| `policy/` | `thothctl scan iac -t opa -o "policy_dir=<repo>/policy"` | ✅ Yes (Git URL support added in v0.15.4) |
| `rules/` | `thothctl check project iac` | ❌ New (this spec) |

### Shared Cache

Both OPA and rule checking use the same `_clone_policy_repo()` infrastructure:
- Cache at `~/.thothcf/.policy_cache/<url_hash>/`
- Clone once, pull on subsequent runs
- Support `@tag` / `@branch` pinning

## Rule Format

### `rules/base.toml`

```toml
[metadata]
name = "MyOrg Infrastructure Standards"
version = "1.0.0"
enforcement = "mandatory"  # mandatory | recommended | informational

[project_structure]
root_files = [".gitignore", "README.md", ".thothcf.toml", ".pre-commit-config.yaml"]
ignore_folders = [".git", ".terraform", ".terragrunt-cache", "node_modules"]

[[project_structure.folders]]
name = "docs"
mandatory = true
enforcement = "mandatory"

[[project_structure.folders]]
name = "tests"
mandatory = true
enforcement = "recommended"

[rules.naming]
pattern = "^[a-z][a-z0-9-]*$"
resource_prefix = "{env}-{project}"
enforcement = "mandatory"

[rules.tagging]
required_tags = ["Environment", "Owner", "CostCenter", "Project"]
enforcement = "mandatory"

[rules.security]
public_ingress = "deny"
unencrypted_storage = "deny"
enforcement = "mandatory"
```

### `rules/terraform-terragrunt.toml`

```toml
# Extends base.toml for terraform-terragrunt projects

[[project_structure.folders]]
name = "stacks"
mandatory = true
enforcement = "mandatory"

[[project_structure.folders]]
name = "modules"
mandatory = true
enforcement = "mandatory"
content = ["main.tf", "variables.tf", "outputs.tf"]

[[project_structure.folders]]
name = "common"
mandatory = true
enforcement = "mandatory"
content = ["backend.tf", "common.hcl"]
```

## Enforcement Levels

| Level | Behavior | Project Can Override? |
|-------|----------|---------------------|
| `mandatory` | Fail pipeline if violated | ❌ No |
| `recommended` | Warn but don't fail | ⚠️ Can disable with explicit opt-out |
| `informational` | Report only | ✅ Yes |

## Rule Merge Logic

```
1. Load org rules:  <org_repo>/rules/base.toml
2. Load type rules: <org_repo>/rules/<project_type>.toml (merged, extends base)
3. Load project:    <project>/.thothcf.toml [project_structure]
4. Merge:
   - mandatory org rules: CANNOT be removed or weakened by project
   - recommended org rules: project can opt-out with explicit `skip = ["rule_id"]`
   - project can ADD additional rules (stricter than org)
5. Evaluate merged ruleset against project directory
```

## CLI Interface

```bash
# Explicit org policy (CI/CD)
thothctl check project iac --org-policy https://github.com/myorg/org-policies.git --enforcement hard

# Pin to version
thothctl check project iac --org-policy https://github.com/myorg/org-policies.git@v1.2.0

# Via env var (CI/CD friendly, no flag needed)
export THOTH_ORG_POLICY=https://github.com/myorg/org-policies.git@v1.0
thothctl check project iac --enforcement hard

# OPA scan also uses the same repo automatically
thothctl scan iac -t opa
# → resolves policy_dir from THOTH_ORG_POLICY/policy/ if no explicit policy_dir given
```

## Output

### Pass

```
✅ Organization policy check passed
   Source: https://github.com/myorg/org-policies.git@v1.2.0
   Rules evaluated: 12 mandatory, 3 recommended
   Project type: terraform-terragrunt
```

### Fail

```
❌ Organization policy violations (enforcement: hard)

  MANDATORY VIOLATIONS (pipeline will fail):
  ┌────────────────────────────────────────────────────────┐
  │ Rule                    │ Expected        │ Found       │
  ├─────────────────────────┼─────────────────┼─────────────┤
  │ project_structure.docs  │ docs/ exists    │ missing     │
  │ rules.tagging           │ CostCenter tag  │ not found   │
  └─────────────────────────┴─────────────────┴─────────────┘

  RECOMMENDATIONS (warnings):
  • tests/ folder recommended but not present

  Source: https://github.com/myorg/org-policies.git@v1.2.0
```

## OPA Integration

When `THOTH_ORG_POLICY` is set and no explicit `policy_dir` is provided to OPA scan:

```python
# In OPA scanner _resolve_policy_dir():
# Current resolution order:
# 1. Git URL (explicit policy_dir)
# 2. Relative to project
# 3. Absolute path
# 4. THOTH_POLICY_REPO env

# NEW: Add THOTH_ORG_POLICY as additional fallback:
# 5. THOTH_ORG_POLICY env → <cached_repo>/policy/
```

This means if the org repo has `policy/`, OPA automatically uses it without any extra flags.

## CI/CD Examples

### GitHub Actions

```yaml
- name: Check org compliance
  run: thothctl check project iac --enforcement hard
  env:
    THOTH_ORG_POLICY: https://github.com/myorg/org-policies.git@v1.0

- name: Security scan with org policies
  run: thothctl scan iac -t checkov -t trivy -t opa --enforcement hard
  env:
    THOTH_ORG_POLICY: https://github.com/myorg/org-policies.git@v1.0
```

### Azure Pipelines

```yaml
- script: |
    export THOTH_ORG_POLICY=https://github.com/myorg/org-policies.git@v1.0
    thothctl check project iac --enforcement hard
    thothctl scan iac -t checkov -t opa --enforcement hard
  displayName: 'Org compliance + security scan'
```

## Implementation Plan

| # | Task | Effort | Dependencies |
|---|------|--------|-------------|
| 1 | Create `OrgPolicyLoader` — clone/cache org repo (reuse `_clone_policy_repo`) | 1d | Existing Git clone infra |
| 2 | Create `RuleMerger` — load base.toml + type.toml + project .toml, enforce hierarchy | 2d | — |
| 3 | Add `--org-policy` flag + `THOTH_ORG_POLICY` env to `check project iac` | 1d | 1, 2 |
| 4 | Update OPA scanner to fallback to `THOTH_ORG_POLICY/policy/` | 0.5d | 1 |
| 5 | Implement enforcement output (pass/fail/warnings table) | 1d | 2, 3 |
| 6 | Write docs + example org-policies repo template | 1d | 5 |
| **Total** | | **~6.5 days** | |

## Relationship to Roadmap

This is a **subset of Phase 2 (Policy Engine)** — specifically the project structure enforcement piece. The full Phase 2 also includes:
- Naming pattern evaluation against HCL resources
- Tag validation against actual resource configurations
- Architecture rules (multi-AZ, encryption checks)
- OPA/Rego integration for custom advanced policies

This spec covers the **foundation** that the rest of Phase 2 builds on.
