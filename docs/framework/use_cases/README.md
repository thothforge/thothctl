# ThothCTL Use Cases

This directory contains comprehensive guides for using ThothCTL in real-world scenarios. Each use case demonstrates how ThothCTL enables modern infrastructure development workflows.

## 🎯 Featured Use Cases

### [🤖 AI-Powered Development Lifecycle (AI-DLC)](ai_dlc.md)
Complete AI-assisted IaC development workflow with Kiro CLI and MCP integration.

**What you'll learn:**
- Integrate ThothCTL with AI assistants
- Use natural language for IaC operations
- AI-powered code review and documentation
- Two workflow options: AI orchestration vs. manual + AI analysis

**Key Features:**
- 19 MCP tools for AI integration
- Natural language interface
- Automated documentation generation
- Intelligent troubleshooting

---

### [🔒 DevSecOps SDLC Guide](devsecops_sdlc.md)
8-phase DevSecOps lifecycle for Infrastructure as Code projects.

**What you'll learn:**
- Complete DevSecOps workflow (Plan → Monitor)
- Security scanning at every phase
- AWS cost analysis and blast radius assessment
- CI/CD integration patterns

**Key Features:**
- Multi-tool security scanning (Checkov, Trivy, TFSec, Snyk)
- Real-time AWS cost estimation
- ITIL v4 change impact assessment
- Compliance enforcement

**Quick Start:** [DevSecOps Quick Start Guide](devsecops_quickstart.md)

---

### [📦 Space Management](space_management.md)
Organize projects with logical boundaries and multi-tenancy support.

**What you'll learn:**
- Create and manage spaces
- Separate dev/prod environments
- Manage credentials and configurations
- Multi-team collaboration

---

### [✅ Check Command](check_command.md)
Validate environments, IaC, costs, and change impact.

**What you'll learn:**
- Environment validation
- IaC validation and planning
- AWS cost analysis
- Blast radius assessment

---

### [📊 Inventory Command](inventory_command.md)
Track dependencies and versions with professional reports.

**What you'll learn:**
- Create IaC inventory
- Track module and provider versions
- Generate modern HTML reports
- Identify outdated dependencies

---

## 🚀 Quick Start Workflows

### 1. Bootstrap Complete Environment
```bash
# Install all development tools
thothctl init env

# Creates: Terraform, Terragrunt, OpenTofu, Checkov, Trivy, Kiro CLI, etc.
```

### 2. Create Project from Scaffold
```bash
# Create a space
thothctl init space --space-name lab-github

# Create project from template
thothctl init project --project-name my-infra --reuse --space lab-github

# Choose from official scaffolds:
# - terraform-scaffold
# - terragrunt-scaffold
# - tofu-scaffold
```

### 3. DevSecOps Workflow
```bash
# 1. Validate IaC
thothctl check iac --path ./terraform

# 2. Cost analysis
thothctl check iac --type cost-analysis

# 3. Blast radius assessment
thothctl check iac --type blast-radius

# 4. Security scan
thothctl scan iac --path ./terraform

# 5. Generate documentation
thothctl document iac --ai --path ./terraform

# 6. Track dependencies
thothctl inventory iac --check-versions
```

### 4. AI-Assisted Development
```bash
# Start MCP server
thothctl mcp server

# In another terminal, use Kiro CLI
kiro-cli chat --agent thoth

# Example AI conversation:
# User: "Scan my Terraform code for security issues"
# AI: [Executes scan, analyzes results, suggests fixes]
```

## 📋 Command Categories

### Initialization
- `thothctl init env` - Bootstrap development environment
- `thothctl init space` - Create logical space
- `thothctl init project` - Create project from scaffold

### Validation & Analysis
- `thothctl check environment` - Validate tool versions
- `thothctl check iac` - Validate IaC configuration
- `thothctl check iac --type cost-analysis` - AWS cost estimation
- `thothctl check iac --type blast-radius` - Change impact assessment

### Security & Compliance
- `thothctl scan iac` - Security scanning with Checkov (default)
- `thothctl scan iac -t checkov -t trivy -t tfsec` - Multi-tool scanning

### Documentation
- `thothctl document iac` - Generate documentation
- `thothctl document iac --ai` - AI-powered documentation

### Dependency Management
- `thothctl inventory iac` - Create inventory
- `thothctl inventory iac --check-versions` - Version tracking

### Project Management
- `thothctl project iac` - Manage IaC projects
- `thothctl list projects` - List all projects
- `thothctl remove project` - Remove project

### Code Generation
- `thothctl generate stacks` - Generate infrastructure stacks
- `thothctl generate components` - Generate components

### AI Integration
- `thothctl mcp server` - Start MCP server for AI

### Maintenance
- `thothctl upgrade` - Self-update ThothCTL

## 🎓 Learning Path

### Beginner
1. [Quick Start Guide](../../quick_start.md)
2. [Space Management](space_management.md)
3. [DevSecOps Quick Start](devsecops_quickstart.md)

### Intermediate
1. [DevSecOps SDLC Guide](devsecops_sdlc.md)
2. [Check Command](check_command.md)
3. [Inventory Command](inventory_command.md)

### Advanced
1. [AI Development Lifecycle](ai_dlc.md)
2. [Framework Architecture](../framework_architecture.md)
3. [Software Architecture](../software_architecture.md)

## 🔧 Integration Patterns

### CI/CD Integration

**GitHub Actions:**
```yaml
- name: Security Scan
  run: thothctl scan iac --path ./terraform --format sarif

- name: Cost Analysis
  run: thothctl check iac --type cost-analysis --format json
```

**GitLab CI:**
```yaml
security_scan:
  script:
    - thothctl scan iac --path ./terraform
    - thothctl check iac --type blast-radius
```

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: thothctl-scan
      name: ThothCTL Security Scan
      entry: thothctl scan iac --path .
      language: system
```

### AI-Powered Code Review
```bash
# Manual execution + AI analysis
thothctl scan iac --path ./terraform > scan-results.txt
kiro-cli chat --agent thoth
# Paste results for AI analysis
```

## 🏗️ Architecture Patterns

### Multi-Environment Setup
```
organization/
├── spaces/
│   ├── dev/              # Development space
│   ├── staging/          # Staging space
│   └── prod/             # Production space
└── projects/
    ├── networking/       # Shared networking
    ├── compute/          # Compute resources
    └── data/             # Data infrastructure
```

### Multi-Tool Projects
```
project/
├── terraform/            # Terraform IaC
├── terragrunt/          # Terragrunt configs
├── cloudformation/      # CloudFormation templates
└── cdk/                 # CDK code
```

## 🎯 Best Practices

### Security
- ✅ Run security scans before every deployment
- ✅ Use compliance policies for governance
- ✅ Review high-severity issues immediately
- ✅ Integrate scanning into CI/CD pipelines

### Cost Management
- ✅ Analyze costs before deployment
- ✅ Set budget alerts and thresholds
- ✅ Review cost optimization recommendations
- ✅ Tag resources for cost allocation

### Documentation
- ✅ Generate documentation automatically
- ✅ Keep runbooks updated
- ✅ Use AI for comprehensive docs
- ✅ Version control documentation

### Collaboration
- ✅ Use spaces for team separation
- ✅ Share scaffolds across teams
- ✅ Document custom workflows
- ✅ Standardize naming conventions

## 🔗 Related Resources

- [Framework Architecture](../framework_architecture.md) - Conceptual framework overview
- [Software Architecture](../software_architecture.md) - Technical implementation
- [Command Reference](../commands/) - Complete command documentation
- [Template Engine](../../template_engine/template_engine.md) - Template system guide
- [Cross-Platform Support](../cross_platform_support.md) - Windows, Linux, macOS

## 💡 Need Help?

- **Quick Start**: [5-minute guide](../../quick_start.md)
- **DevSecOps**: [Quick start](devsecops_quickstart.md) or [Complete guide](devsecops_sdlc.md)
- **AI Integration**: [AI-DLC guide](ai_dlc.md)
- **Commands**: Run `thothctl <command> --help`

## 🚀 What's Next?

After mastering these use cases, explore:
- Custom scaffold creation
- Organization-specific templates
- Custom security policies
- Advanced CI/CD integration
- Multi-cloud deployments
