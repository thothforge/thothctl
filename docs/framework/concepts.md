# Concepts

## Environment

Define the development environment for IaC projects. For example, native OS like Debian/Linux, Windows or DevToContainers.

## Project

IaC project, could be around a use case, blueprint, starter template published in your Catalog or default setup. 

## Space

A Space is the top-level organizational unit in ThothForge. It represents an **Internal Developer Platform context** — a set of shared configuration (VCS provider, Terraform registry, orchestration tool, credentials) that all projects within that space inherit.

### Hierarchy

```
Space (IDP context)
└── Project (IaC codebase)
    └── Components (modules, stacks, templates)
```

### What a Space defines

| Configuration | Example |
|---------------|---------|
| Version control provider | GitHub, GitLab, Azure Repos |
| Terraform registry | `https://registry.terraform.io` or private |
| Orchestration tool | Terragrunt, Terramate, none |
| Credentials | PATs, tokens (encrypted per-space) |

### Storage layout

```
~/.thothcf/
├── spaces.toml          # Registry of all spaces
├── active_space         # Currently active space name
├── .thothcf.toml        # Project registry
└── spaces/
    └── <space_name>/
        ├── space.toml
        ├── credentials/
        ├── vcs/
        ├── terraform/
        └── orchestration/
```

### Active space

You can set an active space so that subsequent commands (like `init project`) automatically use it:

```bash
thothctl space activate production
thothctl init project -pn my-app  # uses "production" space
```

### Typical workflow

```bash
# 1. Create a space
thothctl init space -s production --vcs-provider github --orchestration-tool terragrunt

# 2. Activate it
thothctl space activate production

# 3. Create projects within it
thothctl init project -pn infra-networking
thothctl init project -pn infra-compute

# 4. Update space config later
thothctl space update production --terraform-registry https://private.registry.example.com

# 5. List and inspect
thothctl list spaces
thothctl check space -s production
```

