# ThothForge Development Container

A modern devcontainer setup for ThothCTL development using the [Dev Container Features](https://containers.dev/features) specification.

## What's Included

### Tools (via Features — auto-updated)

| Tool | Purpose |
|------|---------|
| OpenTofu | IaC provisioning |
| Terragrunt | IaC orchestration |
| terraform-docs | Module documentation generation |
| Trivy | Vulnerability & misconfiguration scanning |
| TFSec | Terraform security scanner |
| TFLint | Terraform linter |
| ShellCheck | Shell script linter |
| AWS CLI | Cloud operations |
| GitHub CLI | PR workflows, code review |
| Docker-in-Docker | Required for KICS scanner |

### System Packages (via Dockerfile)

- **graphviz** — Diagram generation (`thothctl document`)
- **libgraph-easy-perl** — ASCII topology views (`--format boxart`)
- **wkhtmltopdf** — PDF report generation

### Python (via lifecycle hooks)

- ThothCTL installed in **editable mode** (`pip install -e '.[telemetry]'`)
- pre-commit hooks configured automatically
- Checkov for IaC security scanning

## Getting Started

1. Install [VS Code](https://code.visualstudio.com/) + [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Install [Docker](https://www.docker.com/products/docker-desktop/)
3. Clone the repository
4. Open in VS Code → "Reopen in Container"

Once built, the container is ready with all tools. ThothCTL runs from source:

```bash
thothctl --version
thothctl check iac -type security --recursive
thothctl dashboard start --port 8080
thothctl mcp start
```

## Ports

| Port | Service |
|------|---------|
| 8080 | ThothCTL Dashboard |
| 5001 | MCP Server |

## Environment Variables

Pass these from your host to configure behavior:

| Variable | Purpose |
|----------|---------|
| `THOTHCTL_DEBUG` | Enable debug logging |
| `THOTH_LOG_LEVEL` | Set log level |

AWS credentials are mounted from `~/.aws` automatically.

## Customizing

- **Add tools**: Add features to `devcontainer.json` from [containers.dev/features](https://containers.dev/features)
- **Add system packages**: Edit the `Dockerfile`
- **Add Python deps**: Modify `postCreateCommand` in `devcontainer.json`
- **Rebuild**: Command Palette → "Dev Containers: Rebuild Container"
