# Thoth Framework

Thoth Framework is a framework to create and manage the [Internal Developer Platform](https://internaldeveloperplatform.org/what-is-an-internal-developer-platform/) tasks for infrastructure, DevOps, DevSecOps, software developers, and platform engineering teams aligned with business objectives:

| Business Objective | Mechanism | Implementation |
|---|---|---|
| Minimize mistakes | Meaningful defaults | Templates |
| Increase velocity | Automation | IaC Scripts |
| Improve products | Fill product gaps | New components |
| Enforce compliance | Restrict choices | Wrappers |
| Reduce lock-in | Abstraction | Service layers |

![Thoth and DCP](./img/framework/thothfr.png)

## ThothCTL

The CLI tool for accelerating IaC adoption, enabling reuse, and interacting with the Internal Developer Platform.

```bash
pip install thothctl
```

### Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize and configure projects, spaces, environments |
| `check` | Validate IaC structure, cost analysis, blast radius, drift detection |
| `scan` | Security scanning with Checkov, Trivy, KICS, TFSec |
| `inventory` | Dependency tracking, version analysis, professional reports |
| `document` | Auto-generate documentation for IaC modules |
| `generate` | Generate components and stacks from rules |
| `project` | Convert, upgrade, and manage projects |
| `ai-review` | Multi-agent AI security analysis and PR decisions |
| `mcp` | Model Context Protocol server for AI assistant integration |
| `list` / `remove` | Manage projects and spaces |
| `upgrade` | Upgrade thothctl to latest version |

### Supported IaC Frameworks

| Framework | Init | Scan | Inventory | Check | Document | Generate |
|-----------|:----:|:----:|:---------:|:-----:|:--------:|:--------:|
| **Terraform** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **OpenTofu** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Terragrunt** | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **CDK v2** | — | — | ✅ | — | — | — |

### Integrated Tools

| Category | Tool | Integration |
|----------|------|-------------|
| **Security** | [Checkov](https://www.checkov.io/) | Native (pip) |
| **Security** | [Trivy](https://trivy.dev/) | CLI binary |
| **Security** | [KICS](https://docs.kics.io/) | Docker container |
| **Security** | [TFSec](https://aquasecurity.github.io/tfsec/) | CLI binary |
| **Docs** | [Terraform-docs](https://terraform-docs.io/) | CLI binary |
| **AI** | [OpenAI](https://platform.openai.com/) | GPT-4 Turbo |
| **AI** | [AWS Bedrock](https://aws.amazon.com/bedrock/) | Claude Sonnet (InvokeModel + Agent) |
| **AI** | [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service) | GPT-4 |
| **AI** | [Ollama](https://ollama.com/) | Local models (Llama 3, Mistral) |
| **VCS** | GitHub / GitLab / Azure DevOps | PR integration, source control |

## Use Cases

- **[Template Engine](template_engine/template_engine.md)** — Build, configure, and scaffold projects from templates
- **[AI-Powered Development (AI-DLC)](framework/use_cases/ai_dlc.md)** — MCP integration with AI assistants for natural language IaC operations
- **[AI Agent for IaC Security](framework/commands/ai-review/README.md)** — Multi-agent orchestrator with auto-decision engine, code fixes, and CI/CD API
- **[DevSecOps SDLC](framework/use_cases/devsecops_sdlc.md)** — 8-phase lifecycle with scanning, cost analysis, blast radius, and drift detection
- **[Platform Engineering Templates](framework/use_cases/platform_engineering_templates.md)** — Create and publish reusable templates for your organization
- **[Space Management](framework/use_cases/space_management.md)** — Organize projects into spaces with shared configuration

## Cross-Platform Support

| Platform | Status | Shell Autocomplete |
|----------|:------:|---|
| **Linux** | ✅ | Bash / Zsh / Fish |
| **macOS** | ✅ | Bash / Zsh / Fish |
| **Windows 10/11** | ✅ | PowerShell |

## Requirements

- Python >= 3.8
- `graphviz` (for dependency graphs)
- Docker (optional, for KICS scanner)

```bash
# Linux/Debian
sudo apt install graphviz -y

# macOS
brew install graphviz

# Windows
choco install graphviz
```
