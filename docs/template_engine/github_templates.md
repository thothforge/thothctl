# GitHub Template Integration

ThothCTL automatically loads project templates from GitHub public repositories based on the project type. This provides standardized, up-to-date project scaffolding for different infrastructure frameworks.

## Default Behavior

When you run `thothctl init project`, the system will:

1. **Load from GitHub first**: Automatically clone the appropriate template repository based on project type
2. **Fallback to local templates**: If GitHub loading fails, use local hardcoded templates
3. **Apply template processing**: Replace placeholders and configure the project

## Supported Project Types and Templates

### Terraform / Terragrunt / OpenTofu

| Project Type | Default Repository |
|-------------|-------------------|
| `terragrunt` | https://github.com/thothforge/terragrunt_project_scaffold.git |
| `terraform` | https://github.com/thothforge/terraform_project_scaffold.git |
| `terraform-terragrunt` | https://github.com/thothforge/terraform_terragrunt_scaffold_project.git |
| `terraform_module` | https://github.com/thothforge/terraform_module_scaffold.git |
| `tofu` | https://github.com/thothforge/tofu_project_scaffold.git |

### AWS CDK v2

CDK projects support language selection. When `--project-type cdkv2` is used, thothctl prompts for the programming language (or defaults to TypeScript in batch mode).

| Project Type | Language | Default Repository |
|-------------|----------|-------------------|
| `cdkv2-typescript` | TypeScript | https://github.com/thothforge/cdkv2_typescript_scaffold.git |
| `cdkv2-python` | Python | https://github.com/thothforge/cdkv2_python_scaffold.git |
| `cdkv2-java` | Java | https://github.com/thothforge/cdkv2_java_scaffold.git |
| `cdkv2-csharp` | C# | https://github.com/thothforge/cdkv2_csharp_scaffold.git |
| `cdkv2-go` | Go | https://github.com/thothforge/cdkv2_go_scaffold.git |
| `cdkv2` | Generic (defaults to TypeScript) | https://github.com/thothforge/cdkv2_typescript_scaffold.git |

All CDK scaffolds include:

- **cdk-nag** AwsSolutions pack enabled by default
- Multi-environment support via YAML configuration
- Layered stack architecture (foundation / platform / application)
- `.kiro/` steering docs, skills, and agent configuration
- Backstage catalog integration
- `#{...}#` template placeholders for thothctl processing

## Usage Examples

### Terraform Projects
```bash
# Terraform + Terragrunt project
thothctl init project --project-name my-infrastructure --project-type terraform-terragrunt

# Terraform project
thothctl init project --project-name my-terraform --project-type terraform
```

### CDK Projects
```bash
# Interactive — prompts for language selection
thothctl init project --project-name my-app --project-type cdkv2

# Explicit language
thothctl init project --project-name my-app --project-type cdkv2 --language typescript
thothctl init project --project-name my-api --project-type cdkv2 -l python

# Batch mode — defaults to TypeScript
thothctl init project --project-name my-app --project-type cdkv2 --batch
```

### Managing Template Configurations

#### List Available Templates
```bash
# Show default GitHub templates
thothctl list templates

# Show templates from a specific space (VCS-based)
thothctl list templates --space my-space
```

#### Set Custom Template Repository
```bash
# Override default template for any project type
thothctl init template --project-type cdkv2-typescript --template-url https://github.com/myorg/custom-cdk-ts.git
thothctl init template --project-type terragrunt --template-url https://github.com/myorg/custom-terragrunt.git
```

## Configuration

Template URLs are stored in `~/.thothcf/.thothctl_templates.toml`:

```toml
[templates]
terragrunt = "https://github.com/myorg/custom-terragrunt-template.git"
cdkv2-typescript = "https://github.com/myorg/custom-cdk-ts-template.git"
cdkv2-python = "https://github.com/myorg/custom-cdk-python-template.git"
```

## CDK Scaffold Structure

Each CDK scaffold follows the ThothForge enterprise pattern:

```
project/
├── bin/                        # CDK app entry point
├── lib/
│   ├── stacks/                 # Stack definitions by domain
│   │   ├── foundation/         # VPC, IAM, S3
│   │   ├── platform/           # EKS, RDS, ElastiCache
│   │   └── application/        # Lambda, API Gateway
│   └── constructs/             # Reusable constructs
├── app/functions/              # Lambda source code
├── project_configs/
│   ├── environment_options.yaml  # Multi-env config (#{...}# placeholders)
│   └── config-loader.*          # Config loader
├── test/                       # Jest / pytest tests
├── .thothcf.toml               # ThothForge template config
├── .kiro/                      # Kiro steering, skills, agents, MCP settings
├── .pre-commit-config.yaml
└── docs/catalog/               # Backstage integration
```

## Benefits

- **Always Up-to-Date**: Templates are fetched from the latest version in the repository
- **Language-Aware**: CDK projects automatically select the right scaffold per language
- **Standardized**: Consistent project structure across teams and organizations
- **Customizable**: Organizations can override default templates with their own
- **Fallback Safety**: Local templates ensure functionality even without internet access
- **Zero Configuration**: Works out of the box with sensible defaults

## Requirements

- Internet access for GitHub template loading
- Git installed on the system
- GitPython dependency (automatically installed with thothctl)

## Troubleshooting

If template loading fails:
1. Check internet connectivity
2. Verify the repository URL is accessible
3. The system will automatically fall back to local templates
4. Check logs with `--debug` flag for detailed error information
