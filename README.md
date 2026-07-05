[![Publish Python Package](https://github.com/thothforge/thothctl/actions/workflows/python-publish.yml/badge.svg)](https://github.com/thothforge/thothctl/actions/workflows/python-publish.yml)
[![Documentation](https://github.com/thothforge/thothctl/actions/workflows/docs.yml/badge.svg)](https://thothforge.github.io/thothctl/)
[![PyPI version](https://img.shields.io/pypi/v/thothctl)](https://pypi.org/project/thothctl/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

# ThothCTL

**AI-Powered Infrastructure Lifecycle CLI** for DevSecOps, Platform Engineering, and IaC governance.

![ThothCTL](./docs/img/framework/thothctl_mcp.png)

ThothCTL accelerates the adoption of Internal Developer Platforms by combining security scanning, inventory management, cost analysis, AI-driven code review, and organizational policy enforcement into a single CLI.

## Quick Start

```bash
pip install --upgrade thothctl

# Scan for security issues
thothctl scan iac -t checkov -t trivy -t opa

# Create infrastructure inventory (SBOM)
thothctl inventory iac --check-versions

# Launch web dashboard
thothctl dashboard launch

# AI-powered security review
thothctl ai-review analyze -d ./terraform -p ollama
```

## Key Features

### 🔒 Security Scanning

Multi-tool scanning with unified HTML reports and enforcement:

```bash
# All scanners with hard enforcement (fails pipeline on violations)
thothctl scan iac -t checkov -t trivy -t kics -t opa -t terraform-compliance --enforcement hard
```

- **5 integrated tools**: Checkov, Trivy, KICS, OPA/Conftest, Terraform-compliance
- **Unified HTML reports** with severity badges, per-stack breakdown
- **Non-compliance findings table** on enforcement failure
- **SARIF output** for GitHub Code Scanning integration
- **Organization policy repos** via `THOTH_ORG_POLICY` env var (HCL + CloudFormation)
- **Scan trend tracking** with local SQLite history

### 📦 Infrastructure Inventory (SBOM)

CycloneDX 1.6 compliant Software Bill of Materials:

```bash
thothctl inventory iac --check-versions
```

- **Module & provider version tracking** with staleness detection
- **CycloneDX 1.6 SBOM** with formulation, evidence, standards, attestations, dependency graph, hashes, and licenses
- **Technical debt scoring** with risk levels and recommendations
- **Schema compatibility analysis** for safe upgrades
- **Professional HTML reports** with collapsible stack groups

### 📊 Web Dashboard

Modern FastAPI-based dashboard with dark mode:

```bash
thothctl dashboard launch
```

- **Security findings viewer** — filter by tool/severity/search, pagination, inline report iframe
- **SBOM details browser** — CycloneDX metadata, dependency graph, formulation, attestations
- **Inventory explorer** — collapsible stacks, module/provider tabs, version comparison
- **Cost analysis** — service breakdown, monthly/annual projections
- **Drift detection** — severity-classified drifted resources
- **AI usage tracking** — token counts, costs per request

### 🤖 AI Agent for IaC Security

Multi-agent system for automated code review and PR decisions:

```bash
thothctl ai-review analyze -d ./terraform -p ollama
thothctl ai-review decide -d ./terraform --pr-number 42 --dry-run
```

- **4 specialized agents**: Security, Architecture, Fix, Decision
- **Multi-provider**: OpenAI, AWS Bedrock, Azure OpenAI, Ollama (local)
- **Auto-decisions** with confidence thresholds and safety controls
- **Adaptive memory**: filesystem or S3 (auto-detects runtime)
- **MCP integration** for AI assistant interoperability

### 💰 Cost Analysis & Risk Assessment

```bash
thothctl check iac -type cost-analysis --recursive
thothctl check iac -type blast-radius --recursive
thothctl check iac -type drift --recursive
```

- **14 AWS services** supported (EC2, RDS, S3, Lambda, EKS, etc.)
- **Blast radius** with ITIL v4 risk classification
- **Drift detection** with severity scoring and IaC coverage tracking

### 🔄 Template Engine & Project Management

```bash
thothctl project convert --make-template --template-project-type terraform
thothctl init project --name my-infra --template terraform-aws
```

- **Bidirectional conversion** between projects and reusable templates
- **Backstage integration** for self-service consumption
- **Template upgrade workflow** to keep projects in sync

## All Commands

| Command | Description |
|---------|-------------|
| `scan iac` | Multi-tool security scanning with enforcement |
| `inventory iac` | Infrastructure SBOM with version tracking |
| `check iac` | Cost analysis, blast radius, drift detection, structure validation |
| `ai-review` | AI-powered security analysis and PR decisions |
| `dashboard launch` | Web dashboard for all reports |
| `document iac` | Auto-generate documentation |
| `project convert` | Template ↔ project conversion |
| `init project` | Scaffold new IaC projects |
| `mcp` | Model Context Protocol server |
| `generate` | Generate IaC from rules and components |

## Installation

```bash
pip install --upgrade thothctl
```

**Requirements**: Python 3.10+ | Linux, macOS, or Windows (WSL)

**Optional system packages**:
```bash
# Linux/Debian
sudo apt install graphviz libgraph-easy-perl -y

# macOS
brew install graphviz graph-easy
```

### Dev Container

A ready-to-use [Dev Container](.devcontainer/) is available with all tools pre-configured:

```bash
# Open in VS Code → "Reopen in Container"
# Or use the devcontainer CLI:
devcontainer up --workspace-folder .
```

## Documentation

📖 **Full docs**: [thothforge.github.io/thothctl](https://thothforge.github.io/thothctl/)

- [Quick Start](docs/quick_start.md)
- [DevSecOps SDLC Guide](docs/framework/use_cases/devsecops_sdlc.md)
- [Scan Command Reference](docs/framework/commands/scan/scan_overview.md)
- [Inventory & SBOM](docs/framework/commands/inventory/inventory_overview.md)
- [Dashboard](docs/dashboard/README.md)
- [AI Review](docs/framework/commands/ai-review/README.md)
- [Template Engine](docs/template_engine/template_engine.md)
- [Dev Container Setup](docs/installation/devcontainer_setup.md)

## CI/CD Integration

```yaml
# GitHub Actions
- name: Security scan
  run: thothctl scan iac -t checkov -t trivy -t opa --enforcement hard --post-to-pr

- name: Inventory check
  run: thothctl inventory iac --check-versions --report-type json
```

## Roadmap

- [x] Multi-tool security scanning with unified reports
- [x] AI Agent for IaC Security (multi-agent, auto-decisions)
- [x] CycloneDX 1.6 SBOM with full supply chain metadata
- [x] Organization policy engine (OPA/Rego, HCL + CloudFormation)
- [x] Web Dashboard with findings viewer and SBOM browser
- [ ] Intent-to-IaC generation (natural language → governed Terraform)
- [ ] Composable workflow engine (declarative YAML DAG pipelines)
- [ ] Graph-aware state visibility (tfstate → queryable resource graph)
- [ ] Architecture diagram generation (Mermaid/Graphviz from IaC)
- [ ] Strands Agents SDK integration

📖 [Full Roadmap](docs/framework/roadmap_fdi.md)

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[Apache-2.0](LICENSE)
