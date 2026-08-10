# Phase 1.9: Composition-Aware Intent-to-IaC Generation — Spec

> **Version**: 1.0 | **Target**: v0.26.0 | **Effort**: ~8 days
> **Author**: ThothForge | **Status**: Ready for implementation
> **Depends on**: Phase 1 (Intent-to-IaC) ✅, Phase 2.4 (Rules integration) ✅

## Overview

Extend `thothctl generate iac` to produce **full multi-stack projects** following the ThothForge scaffold composition rules — not just single flat modules. The AI decomposes a high-level intent into multiple stacks organized by layers, wires dependencies between them, and produces a complete project ready for `terragrunt run-all plan`.

## Design Principles

1. **Scaffold-driven** — output structure comes from `.thothcf_project.toml`, not AI invention
2. **Layer-aware** — foundation → platform → application → observability (ordered dependencies)
3. **Org policy compliant** — naming, tagging, security rules enforced at generation time
4. **Incremental** — can generate into an existing project (adds stacks, doesn't overwrite)
5. **Framework-agnostic** — supports terraform-terragrunt, terraform, cdkv2, cloudformation

## Architecture

```
User Intent (complex, multi-service)
       ↓
┌──────────────────────────────────────────────────────────────────┐
│  1. Intent Decomposer                                             │
│     - Breaks intent into discrete infrastructure components       │
│     - Assigns each component to a layer (foundation/platform/app) │
│     - Identifies dependencies between components                  │
│     Output: CompositionPlan (list of stacks + dependency graph)   │
└──────────────┬───────────────────────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────────────────────┐
│  2. Stack Generator (per stack)                                    │
│     - Uses existing CodeGenerator for each stack's code            │
│     - Adds terragrunt.hcl with includes + dependencies             │
│     - Places in correct path: stacks/<layer>/<domain>/<service>/   │
│     Output: List[GeneratedFile] per stack                          │
└──────────────┬───────────────────────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────────────────────┐
│  3. Project Assembler                                              │
│     - Creates root.hcl + common/ if needed                         │
│     - Merges all stack files into project structure                 │
│     - Runs validation on the full project                          │
│     Output: Complete project directory                              │
└──────────────────────────────────────────────────────────────────┘
```

## Layer Model

| Layer | Purpose | Examples | Dependencies |
|-------|---------|----------|--------------|
| `foundation` | Core networking & security | VPC, subnets, NAT, KMS keys, IAM baselines | None (root layer) |
| `platform` | Shared services | ECS/EKS cluster, RDS, ElastiCache, S3 buckets | → foundation |
| `application` | Workload-specific | Lambda functions, API Gateway, DynamoDB tables | → platform |
| `observability` | Monitoring & alerting | CloudWatch dashboards, alarms, log groups | → platform |

## CLI Interface

```bash
# Full project generation (new project)
thothctl generate iac \
  -i "Microservices platform: VPC with 3 AZs, ECS Fargate cluster, RDS PostgreSQL, S3 data lake, API Gateway" \
  --project-type terraform-terragrunt \
  --composition full \
  -o ./my-platform \
  --apply

# Add stacks to existing project (incremental)
thothctl generate iac \
  -i "Add Redis cache for session management" \
  --project-type terraform-terragrunt \
  --composition incremental \
  --apply

# Single stack (current behavior, default)
thothctl generate iac \
  -i "S3 bucket with encryption" \
  --apply
```

## CompositionPlan Model

```python
@dataclass
class StackPlan:
    """A single stack to generate."""
    name: str                    # e.g., "vpc"
    layer: str                   # foundation | platform | application | observability
    domain: str                  # e.g., "networking", "data", "compute"
    intent: str                  # Specific intent for this stack
    depends_on: List[str]        # Stack names this depends on
    module_source: Optional[str] # Official module if applicable

@dataclass
class CompositionPlan:
    """Full project composition plan."""
    stacks: List[StackPlan]
    project_type: str
    needs_root_config: bool      # True if root.hcl doesn't exist
    needs_common: bool           # True if common/ doesn't exist
```

## Intent Decomposition Prompt

The AI receives the high-level intent + layer model and returns a structured decomposition:

```
SYSTEM: You are an infrastructure architect. Decompose the user's intent into
discrete infrastructure stacks following the layer model:
- foundation: networking, security baselines, encryption keys
- platform: shared compute, databases, storage
- application: workload-specific resources
- observability: monitoring, alerting

Return JSON:
{
  "stacks": [
    {
      "name": "vpc",
      "layer": "foundation",
      "domain": "networking",
      "intent": "VPC with 3 private subnets, 3 public subnets, NAT gateway per AZ",
      "depends_on": [],
      "module_source": "terraform-aws-modules/vpc/aws"
    },
    ...
  ]
}
```

## Terragrunt.hcl Generation

For each stack, generate the orchestration file:

```hcl
# Auto-generated by ThothCTL — stacks/platform/data/s3/terragrunt.hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "vpc" {
  config_path = "../../../foundation/networking/vpc"

  mock_outputs = {
    vpc_id     = "vpc-mock-12345"
    subnet_ids = ["subnet-mock-1", "subnet-mock-2"]
  }

  mock_outputs_merge_strategy_with_state = "shallow"
}

inputs = {
  vpc_id     = dependency.vpc.outputs.vpc_id
  subnet_ids = dependency.vpc.outputs.subnet_ids
}
```

## Root Config Generation (if needed)

```hcl
# root.hcl — Generated by ThothCTL
locals {
  # Environment from directory structure or tfvars
  environment = get_env("TF_VAR_environment", "dev")
  project     = "my-platform"
  region      = "us-east-1"
}

remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket         = "${local.project}-terraform-state"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.region
    encrypt        = true
    dynamodb_table = "${local.project}-state-lock"
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.region}"

  default_tags {
    tags = {
      Project     = "${local.project}"
      Environment = "${local.environment}"
      ManagedBy   = "terragrunt"
    }
  }
}
EOF
}
```

## Implementation Tasks

| # | Task | Effort | Dependencies |
|---|------|--------|-------------|
| 1.9.1 | Add `--composition` flag to CLI (full/incremental/single) | 1d | — |
| 1.9.2 | Create `IntentDecomposer` class (AI call to break intent into stacks) | 2d | — |
| 1.9.3 | Create `CompositionPlan` + `StackPlan` models | 0.5d | — |
| 1.9.4 | Create `ProjectAssembler` (root.hcl, common/, merge stacks) | 1.5d | 1.9.3 |
| 1.9.5 | Generate `terragrunt.hcl` per stack (Jinja2 template + dependency wiring) | 1d | 1.9.4 |
| 1.9.6 | Loop: generate code per stack using existing `CodeGenerator` | 1d | 1.9.2, 1.9.5 |
| 1.9.7 | Validate full project (terraform validate per stack + org rules) | 0.5d | 1.9.6 |
| 1.9.8 | Write tests + docs | 0.5d | 1.9.7 |

## Example Output

```bash
$ thothctl generate iac \
  -i "Fintech platform: VPC, ECS cluster, PostgreSQL RDS, S3 data lake" \
  --project-type terraform-terragrunt \
  --composition full \
  -o ./fintech-infra \
  --apply

🎯 Intent: Fintech platform: VPC, ECS cluster, PostgreSQL RDS, S3 data lake
🤖 Provider: bedrock (model: us.anthropic.claude-sonnet-4-6)
📐 Composition: full project (terraform-terragrunt)

🧩 Decomposed into 4 stacks:
  foundation/networking/vpc     — VPC with 3 AZs, NAT, flow logs
  platform/compute/ecs          — ECS Fargate cluster (depends: vpc)
  platform/data/rds             — PostgreSQL RDS Multi-AZ (depends: vpc)
  platform/data/s3              — S3 data lake with KMS (depends: vpc)

📁 Generating project structure...
  ✅ root.hcl
  ✅ common/common.hcl
  ✅ stacks/foundation/networking/vpc/ (4 files)
  ✅ stacks/platform/compute/ecs/ (4 files)
  ✅ stacks/platform/data/rds/ (4 files)
  ✅ stacks/platform/data/s3/ (4 files)

🔒 Validating (Checkov + org rules)...
  ✅ All stacks pass validation

✨ Project generated: ./fintech-infra (18 files, 4 stacks)
   Next: cd fintech-infra && terragrunt run-all plan
```

## CDK Composition (cdkv2 project type)

For CDK projects, the composition generates the app entry point + stack classes:

```
my-cdk-app/
├── bin/app.ts                    ← CDK app entry (instantiates all stacks)
├── lib/
│   ├── stacks/
│   │   ├── foundation/
│   │   │   └── networking-stack.ts
│   │   ├── platform/
│   │   │   ├── compute-stack.ts
│   │   │   └── data-stack.ts
│   │   └── application/
│   │       └── api-stack.ts
│   └── constructs/               ← Shared L2/L3 constructs
├── cdk.json
├── package.json
└── tsconfig.json
```

## CloudFormation Composition

For CloudFormation, generates nested stacks with cross-stack references:

```
my-cfn-project/
├── templates/
│   ├── foundation/
│   │   └── networking.yaml       ← Exports VpcId, SubnetIds
│   ├── platform/
│   │   ├── compute.yaml          ← Imports !ImportValue VpcId
│   │   └── data.yaml
│   └── application/
│       └── api.yaml
├── parameters/
│   ├── dev.json
│   └── prd.json
└── deploy.sh                     ← Ordered deployment script
```

## Success Criteria

- [ ] `--composition full` generates complete project with root config + multiple stacks
- [ ] Stacks placed in correct layer paths
- [ ] Dependencies wired correctly (terragrunt.hcl has dependency blocks)
- [ ] Org rules enforced across all generated stacks
- [ ] Works for terraform-terragrunt, cdkv2, cloudformation
- [ ] Incremental mode adds stacks without overwriting existing
- [ ] `terragrunt run-all plan` succeeds on generated project (no syntax errors)
