# Generate IaC — Intent-to-Infrastructure

Generate governed Infrastructure as Code from natural language descriptions. ThothCTL reads your organizational conventions (`.thothcf.toml`, steering docs, existing patterns) and produces compliant code validated by Checkov and OPA.

## Quick Start

```bash
# Generate a VPC (dry-run by default — shows code without writing)
thothctl generate iac -i "VPC with 3 private subnets and NAT gateway for production"

# Write to disk
thothctl generate iac -i "EKS cluster with managed node groups" --apply -o ./stacks/platform/eks

# Use AWS Bedrock instead of local Ollama
thothctl generate iac -i "S3 bucket with versioning and encryption" -p bedrock
```

## How It Works

```
Your intent (natural language)
       ↓
1. Load Context — reads .thothcf.toml, steering docs, existing patterns, OPA policies
       ↓
2. Generate — AI produces IaC code following your org conventions
       ↓
3. Validate — Checkov + OPA scan the generated code
       ↓
4. Self-Correct — if violations found, AI fixes them (up to 3 attempts)
       ↓
5. Output — display (dry-run) or write to disk (--apply)
```

The AI produces compliant code because your organizational rules are injected directly into its context — not because of a separate policy engine. Existing Checkov and OPA validate the output as a safety net.

## Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--intent` | `-i` | (required) | What infrastructure to create |
| `--project-type` | `-pt` | auto | `terraform`, `terraform-terragrunt`, `terragrunt`, `cloudformation`, `cdkv2` |
| `--provider` | `-p` | ollama | AI provider: `ollama`, `bedrock`, `openai`, `azure` |
| `--model` | `-m` | (provider default) | Model override (e.g., `llama3`, `us.anthropic.claude-sonnet-4-6`) |
| `--output-dir` | `-o` | current dir | Where to write generated files |
| `--dry-run / --no-dry-run` | | dry-run | Preview without writing |
| `--apply` | | off | Write files to disk |
| `--self-correct / --no-self-correct` | | on | Fix validation violations automatically |
| `--max-iterations` | | 3 | Maximum self-correction attempts |
| `--skip-validation` | | off | Skip Checkov/OPA (trust AI output) |
| `--include-diagram / --no-diagram` | | on | Generate architecture diagram |
| `--composition` | | single | `single` (one stack), `full` (multi-stack project), `incremental` (add stacks to existing) |
| `--mode` | | project | `blueprint` (template with `#{...}#` placeholders) or `project` (resolved, ready to deploy) |
| `--space` | | — | Space name to load deployment parameters (for project mode) |
| `--plan-validation` | | disabled | `disabled`, `per-stack`, `full-project`, `terraform` |
| `--plan-profile` | | — | AWS profile for plan validation credentials |
| `--plan-iam-role` | | — | IAM role ARN for temporal credentials during plan |
| `--plan-filter` | | — | Terragrunt filter for targeted stack validation |

## Examples

### Basic VPC (Terragrunt)

```bash
thothctl generate iac \
  -i "VPC with 3 private subnets, 3 public subnets, NAT gateway per AZ, flow logs enabled" \
  -pt terraform-terragrunt \
  --apply -o ./stacks/foundation/network/vpc
```

Generates:
```
stacks/foundation/network/vpc/
├── terragrunt.hcl    # include root, dependency blocks, inputs
├── main.tf           # terraform-aws-modules/vpc/aws with flow logs
├── variables.tf      # cidr, environment, tags
└── outputs.tf        # vpc_id, subnet_ids, nat_gateway_ids
```

### EKS Cluster (Terraform)

```bash
thothctl generate iac \
  -i "Production EKS cluster with managed node groups, Karpenter autoscaler, and IRSA" \
  -pt terraform \
  -p bedrock -m claude-sonnet-4-20250514 \
  --apply -o ./modules/eks
```

### S3 with Security (validates automatically)

```bash
thothctl generate iac \
  -i "S3 bucket for application logs with encryption, versioning, lifecycle rules, and no public access"
```

The self-correction loop ensures:
- ✅ Server-side encryption enabled (CKV_AWS_145)
- ✅ Public access blocked (CKV_AWS_53, CKV_AWS_54, CKV_AWS_55, CKV_AWS_56)
- ✅ Versioning enabled (CKV_AWS_21)
- ✅ Logging configured (CKV_AWS_18)

## Composition Mode (v0.26.1+)

Generate entire multi-stack projects from a single intent:

```bash
# Full project: root.hcl + common/ + multiple stacks with dependencies
thothctl generate iac \
  -i "Create a microservices platform with VPC, EKS, RDS, and ElastiCache" \
  --composition full \
  -p bedrock -m us.anthropic.claude-sonnet-4-6 \
  --apply -o ./my-platform
```

Generates:
```
my-platform/
├── root.hcl                          # Backend + provider config
├── common/common.hcl                 # Shared variables and locals
├── common/common.tfvars              # Deployment parameters
├── .gitignore
├── .pre-commit-config.yaml
└── stacks/
    ├── foundation/networking/vpc/
    │   ├── terragrunt.hcl            # include root, inputs
    │   ├── main.tf                   # terraform-aws-modules/vpc/aws
    │   ├── variables.tf              # ONLY variable blocks
    │   └── outputs.tf                # ONLY output blocks
    ├── platform/compute/eks/
    │   ├── terragrunt.hcl            # dependency on vpc
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── platform/data/rds/
        ├── terragrunt.hcl            # dependency on vpc
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

**Composition modes:**
- `single` — one stack (default)
- `full` — complete project with root config, common, and multiple stacks
- `incremental` — add stacks to an existing project

## Blueprint vs Project Mode (v0.27.1+)

Control whether output is a reusable template or a ready-to-deploy project:

### Project Mode (default)

```bash
thothctl generate iac \
  -i "VPC with subnets in us-east-1 for production" \
  --mode project \
  --space labvel-devsecops \
  --composition full \
  --apply -o ./vpc-prod
```

Output has **resolved values** from space config + intent:
```hcl
# common/common.hcl
locals {
  profile           = "labvel-devsecops"   # From --space
  project           = "vpc-prod"           # From --output-dir
  deployment_region = "us-east-1"          # Extracted from intent
  environment       = "prod"              # Extracted from "for production"
}
```

### Blueprint Mode

```bash
thothctl generate iac \
  -i "VPC with subnets" \
  --mode blueprint \
  --composition full \
  --apply -o ./vpc-template
```

Output keeps **`#{...}#` placeholders** (for Backstage, `thothctl init project`, or CI/CD):
```hcl
# common/common.hcl
locals {
  profile           = "#{deployment_profile}#"
  project           = "#{project_name}#"
  deployment_region = "#{deployment_region}#"
}
```

### Value Resolution (Project Mode)

Values are resolved from these sources (priority order):

| Priority | Source | Example |
|----------|--------|---------|
| 1 | Intent NLP extraction | "in us-east-1" → `deployment_region` |
| 2 | Space config | `~/.thothcf/spaces/<name>/orchestration/terragrunt.toml` |
| 3 | CLI flags | `--output-dir vpc-prod` → `project_name` |
| 4 | Scaffold defaults | `template_input_parameters.template_value` |

## Plan Validation (v0.27.0+)

Validate generated code with `terraform/terragrunt plan` before output:

```bash
# Per-stack: runs terragrunt plan on each generated stack
thothctl generate iac \
  -i "VPC with subnets" \
  --composition full \
  --plan-validation per-stack \
  --plan-profile labvel-devsecops

# Full-project: runs terragrunt run --all -- plan --graph (DAG-aware)
thothctl generate iac \
  -i "VPC with subnets" \
  --composition full \
  --plan-validation full-project

# With IAM role for temporal credentials (15-min session)
thothctl generate iac \
  -i "VPC with subnets" \
  --plan-validation per-stack \
  --plan-iam-role arn:aws:iam::123456789012:role/thothctl-plan-readonly
```

**Plan validation modes:**

| Mode | What it does | Requires |
|------|-------------|----------|
| `disabled` (default) | No plan | Nothing |
| `per-stack` | `terragrunt plan` per stack during generation | AWS credentials + terragrunt |
| `full-project` | `terragrunt run --all -- plan --graph` after all stacks | AWS credentials + terragrunt |
| `terraform` | `terraform plan` for non-terragrunt projects | AWS credentials + terraform/tofu |

When plan fails, violations are fed back to the AI for self-correction (same loop as Checkov/OPA).

### Configuration (`.thothcf.toml`)

```toml
[generation.plan]
plan_validation = "per-stack"
iam_assume_role = "arn:aws:iam::123456789012:role/plan-readonly"
session_duration = 900
provider_cache = true
plan_timeout = 120
```

## Dashboard Integration (v0.27.4+)

Every generation run is recorded and viewable in the ThothCTL dashboard:

```bash
thothctl dashboard launch
# Navigate to ✨ Generation tab
```

The dashboard shows:
- **Metrics**: total runs, success rate, avg duration, token usage
- **History table**: intent, type, mode, status, files generated
- **Detail view**: stacks, violations, collapsible file browser with syntax preview

### CloudFormation

```bash
thothctl generate iac \
  -i "Application Load Balancer with HTTPS listener and WAF" \
  -pt cloudformation \
  --apply -o ./stacks/application/web-tier.yaml
```

### Skip Validation (fast iteration)

```bash
thothctl generate iac \
  -i "CloudWatch dashboard with CPU, memory, and request metrics" \
  --skip-validation --apply
```

## Context Sources

ThothCTL compiles organizational context from these sources (in priority order):

| Source | What's Used | Token Budget |
|--------|-------------|-------------|
| `.thothcf.toml` | Project type, naming patterns, environment, tags | ~500 |
| `.kiro/steering/iac-rules.md` or `.claude/rules/*.md` | IaC composition rules, module preferences, prohibited practices | ~2000 |
| `.kiro/steering/product.md` or `CLAUDE.md` | Project purpose, architecture layers | ~500 |
| Existing files in `stacks/` | Real examples from your project (few-shot) | ~2000 |
| `policies/*.rego` or `THOTH_ORG_POLICY` | OPA rule names and descriptions | ~500 |

**Total context: ~5,500 tokens** — leaves room for generation within most model limits.

### No Context? No Problem

If none of these files exist, the command still works — it generates standard Terraform following AWS best practices. Context just makes the output match *your* conventions.

## AI Providers

| Provider | Flag | Requires | Best For |
|----------|------|----------|----------|
| Ollama | `-p ollama` | Local Ollama running | Offline, private, fast iteration |
| AWS Bedrock | `-p bedrock` | AWS credentials | Production quality, Claude models |
| OpenAI | `-p openai` | `OPENAI_API_KEY` | GPT-4 Turbo |
| Azure OpenAI | `-p azure` | Azure endpoint configured | Enterprise Azure environments |

### Recommended Models

| Provider | Model | Quality | Speed |
|----------|-------|---------|-------|
| Ollama | `llama3` (default) | Good | Fast |
| Ollama | `codellama:34b` | Better | Slower |
| Bedrock | `claude-sonnet-4-20250514` | Excellent | Fast |
| OpenAI | `gpt-4-turbo` | Excellent | Medium |

## Self-Correction

When Checkov finds violations, the AI automatically fixes them:

```
🤖 Generating infrastructure code...
  ✅ Generated 4 files

🔒 Validating with Checkov...
  ⚠️ 2 findings: CKV_AWS_130 (VPC flow logs), CKV_AWS_178 (NAT HA)

🔄 Self-correcting (iteration 1/3)...
  ✅ Fixed: added flow logs + multi-AZ NAT

🔒 Re-validating...
  ✅ Validation passed
```

Disable with `--no-self-correct` if you want raw output without fixes.

## MCP Integration

The command is also available as an MCP tool for AI assistants (Kiro, Claude Code):

```json
{
  "name": "thothctl_generate_iac",
  "description": "Generate governed IaC from natural language intent",
  "parameters": {
    "intent": "VPC with 3 private subnets",
    "project_type": "terraform-terragrunt",
    "self_correct": true,
    "apply": false
  }
}
```

Start the MCP server: `thothctl mcp server`

## Tips

1. **Be specific** — "VPC with 3 private subnets, NAT per AZ, flow logs" produces better results than "create a VPC"
2. **Use your scaffold** — run from a project that has `.thothcf.toml` and existing stacks for best context
3. **Start with dry-run** — review the generated code before `--apply`
4. **Iterate** — if the output isn't perfect, refine your intent and re-run
5. **Use Bedrock for production** — Claude Sonnet produces the highest quality IaC

## Troubleshooting

### "AI returned no files"

The AI provider couldn't parse the intent or returned invalid JSON. Try:
- Simplify the intent
- Use a more capable model (`-p bedrock -m claude-sonnet-4-20250514`)
- Check provider connectivity (`thothctl check environment`)

### "Validation: N violations remain"

Self-correction reached max iterations without passing all checks. Options:
- Increase iterations: `--max-iterations 5`
- Skip validation: `--skip-validation` (fix manually)
- Fix the generated code yourself and run `thothctl scan iac -t checkov`

### Slow generation with Ollama

Large models + long context = slow. Solutions:
- Use a smaller model: `-m llama3` (7B is fastest)
- Reduce context: remove unnecessary steering files
- Switch to API provider: `-p bedrock` (faster inference)

### Provider not initialized

```
Failed to initialize AI provider: ...
```

Check provider configuration:
- Ollama: ensure `ollama serve` is running
- Bedrock: ensure AWS credentials are configured
- OpenAI: ensure `OPENAI_API_KEY` is set
