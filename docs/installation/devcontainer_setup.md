# Development Container Setup

ThothCTL provides a ready-to-use [Dev Container](https://containers.dev/) for a fully configured local development environment. It works on **any OS** (Linux, macOS, Windows) and ensures all contributors have identical tooling.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [VS Code](https://code.visualstudio.com/) + [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

> Also works with GitHub Codespaces, JetBrains Gateway, and the [devcontainer CLI](https://github.com/devcontainers/cli).

## Quick Start

```bash
git clone https://github.com/thothforge/thothctl.git
cd thothctl
code .
# VS Code will prompt: "Reopen in Container" → click it
```

After the container builds (~2 min first time), ThothCTL is installed in editable mode and all tools are ready:

```bash
thothctl --version
tofu --version
terragrunt --version
trivy --version
checkov --version
```

## Included Tools

| Category | Tools |
|----------|-------|
| **IaC** | OpenTofu, Terragrunt, terraform-docs, TFLint |
| **Security** | Trivy, TFSec, Checkov, ShellCheck |
| **Cloud** | AWS CLI, Docker-in-Docker (for KICS) |
| **Dev Workflow** | GitHub CLI, pre-commit, Ruff |
| **Diagrams** | Graphviz, graph-easy |

## Exposed Ports

| Port | Service | Command |
|------|---------|---------|
| 8080 | Dashboard | `thothctl dashboard start --port 8080` |
| 5001 | MCP Server | `thothctl mcp start` |

## Environment Variables

Set these on your host to pass them into the container:

| Variable | Purpose | Default |
|----------|---------|---------|
| `THOTHCTL_DEBUG` | Enable debug logging | — |
| `THOTH_LOG_LEVEL` | Log level (DEBUG, INFO, etc.) | — |
| `AWS_PROFILE` | AWS profile to use | default |

AWS credentials are mounted from `~/.aws` automatically.

## Development Workflow

The container installs ThothCTL in editable mode, so code changes are reflected immediately:

```bash
# Run tests
python -m pytest tests/ -v --cov=src/

# Lint & format
ruff check src/ --fix
ruff format src/

# Run pre-commit hooks
pre-commit run --all-files
```

## Customizing

- **Add a tool**: Add a [Feature](https://containers.dev/features) to `.devcontainer/devcontainer.json`
- **Add a system package**: Edit `.devcontainer/Dockerfile`
- **Rebuild**: Command Palette → "Dev Containers: Rebuild Container"

## Using Without VS Code

```bash
# Install the devcontainer CLI
npm install -g @devcontainers/cli

# Build and start
devcontainer up --workspace-folder .

# Execute commands inside
devcontainer exec --workspace-folder . thothctl --version
```
