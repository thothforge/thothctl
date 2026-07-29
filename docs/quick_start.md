# Quick Start

## Installation

```bash
pip install thothctl
```

Verify:

```bash
thothctl --version
```

### Platform-Specific Notes

- **Windows**: See [Windows Installation Guide](installation/windows_installation.md)
- **Linux**: Requires `graphviz` — `sudo apt install graphviz -y`
- **macOS**: `brew install graphviz`

## Guided Onboarding (Recommended First Step)

```bash
thothctl quickstart
```

The `quickstart` command walks you through initial setup interactively — detecting your environment, selecting a VCS provider, configuring your first space, and running a sample scan. It's the fastest way to get productive with ThothCTL.

## Setup Autocomplete

```bash
thothctl-register-autocomplete
```

Configures **PowerShell** on Windows, **Bash/Zsh/Fish** on Linux/macOS.

## Basic Usage

```bash
thothctl --help
```

```
Usage: thothctl [OPTIONS] COMMAND [ARGS]...

  ThothForge CLI - The Open Source Internal Developer Platform CLI

Options:
  --version                  Show the version and exit.
  --debug                    Enable debug mode
  -d, --code-directory PATH  Configuration file path
  --help                     Show this message and exit.

Getting Started:
  quickstart  Guided onboarding for new users
  init        Initialize and setup project configurations and environments

Security & Compliance:
  scan        Scan infrastructure code for security issues and compliance
  ai-review   AI-powered security analysis and code review for IaC
  check       Validate environment, IaC, cost analysis, and blast radius

Infrastructure Management:
  inventory   Create inventory for IaC composition with version tracking
  document    Generate documentation for IaC projects with AI support
  generate    Generate IaC from rules, use cases, and components

Workflow & Orchestration:
  workflow    Composable DevSecOps pipelines (devsecops, run)
  dashboard   Web dashboard for visualizing results
  mcp         Model Context Protocol (MCP) server for AI integration

Project Management:
  project     Convert, clean up and manage the current project
  list        List projects and spaces managed by thothctl locally
  remove      Remove projects and spaces managed by thothctl
  upgrade     Upgrade thothctl to the latest version
```

> **New in v0.25.0**: Commands are now displayed in logical categories. The CLI also warns you on every invocation when a newer version is available.

## Create a Space

Spaces organize your projects with shared configuration (VCS provider, registry, orchestration tool):

```bash
thothctl init space -vcs github -d "My infrastructure projects" -s my-space
```

```
✅ 🎉 Space 'my-space' initialized successfully!
💡 You can now create projects in this space with:
   thothctl init project --project-name <name> --space my-space
```

## Create a Project

### From a void template

```bash
thothctl init project --project-name my-project --space my-space
```

### From an existing template (reuse)

Clone and customize a template from your GitHub/GitLab/Azure DevOps organization:

```bash
thothctl init project -reuse -s my-space -pj my-project
```

You'll be prompted to select a template and fill in project parameters (region, environment, backend config, etc.).

## Scan for Security Issues

```bash
thothctl scan .
```

Runs Checkov (and optionally Trivy, KICS) against your IaC code and generates reports.

## Check IaC Structure

```bash
# Validate project structure
thothctl check iac

# Cost analysis
thothctl check iac -type cost-analysis --recursive

# Drift detection
thothctl check iac -type drift --recursive

# Dump effective configuration (v0.25.0)
thothctl check config
```

## Create Inventory

```bash
thothctl inventory iac --check-versions
```

Generates a professional report with module versions, provider tracking, and outdated dependency detection.

## AI Security Review

```bash
# Analyze with local AI (no data leaves your machine)
thothctl ai-review analyze -d ./terraform -p ollama

# Multi-agent orchestrated review
thothctl ai-review orchestrate -d ./terraform -a security -a fix
```

## Next Steps

- [DevSecOps SDLC Guide](framework/use_cases/devsecops_sdlc.md) — Full lifecycle workflow
- [AI-DLC Use Case](framework/use_cases/ai_dlc.md) — AI-powered development with MCP
- [AI Review](framework/commands/ai-review/README.md) — Multi-agent security analysis
- [Check Command](framework/use_cases/check_command.md) — Validation and compliance workflows
- [Inventory Command](framework/use_cases/inventory_command.md) — Dependency management
