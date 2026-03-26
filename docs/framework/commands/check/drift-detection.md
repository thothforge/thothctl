# Drift Detection

The drift detection feature identifies infrastructure drift — discrepancies between what your IaC defines and what actually exists in the cloud. It analyses terraform/tofu plan output to classify resources as changed, deleted, or unmanaged, and assigns severity levels based on resource type and change impact.

## Overview

Infrastructure drift occurs when cloud resources are modified outside of IaC workflows (e.g., manual console changes, scripts, or other tools). Drift detection helps teams:

- **Spot configuration drift** before it causes incidents
- **Measure IaC coverage** as a percentage of managed resources
- **Prioritise remediation** with severity-based classification
- **Enforce compliance** with policy-based drift response
- **Track trends** with coverage history over time
- **AI-powered analysis** for risk assessment and remediation guidance
- **Filter by tags** to scope checks to specific environments or teams
- **Integrate with CI/CD** via PR comments and reports

## Command Usage

### Basic Drift Detection
```bash
thothctl check iac -type drift
```

### Recursive Across All Stacks
```bash
thothctl check iac -type drift --recursive
```

### Filter by Resource Tags
```bash
# Only check production resources
thothctl check iac -type drift --recursive --filter-tags "env=prod"

# Multiple tags (AND logic)
thothctl check iac -type drift --filter-tags "env=prod,team=platform"
```

### With AI Analysis
```bash
thothctl check iac -type drift --recursive --ai-provider ollama
```

### Post Results to a Pull Request
```bash
thothctl check iac -type drift --recursive --post-to-pr
```

### Command Options

| Option | Description | Default |
|--------|-------------|---------|
| `--recursive` | Scan subdirectories for tfplan.json files or terraform roots | `false` |
| `--tftool` | Tool to use (`terraform` or `tofu`) | `tofu` |
| `--filter-tags` | Filter results by resource tags (e.g. `env=prod,team=*`) | `None` |
| `--ai-provider` | AI provider for drift analysis (`openai`, `bedrock`, `azure`, `ollama`) | `None` |
| `--ai-model` | AI model override (e.g. `gpt-4`, `llama3`) | `None` |
| `--project-name` | Project name for drift history tracking | directory name |
| `--post-to-pr` | Post markdown results as a PR comment | `false` |
| `--vcs-provider` | VCS provider for PR comments (`auto`, `github`, `azure_repos`) | `auto` |
| `--space` | Space name for credential resolution | `None` |

## How It Works

### Detection Pipeline

```
┌──────────────────────┐
│  1. DETECT            │
│  tfplan.json or live  │
│  terraform/tofu plan  │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  2. CLASSIFY          │
│  changed / deleted /  │
│  unmanaged + severity │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  3. FILTER            │
│  .driftignore +       │
│  --filter-tags        │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  4. POLICY            │
│  .driftpolicy rules   │
│  (ignore/accept/block)│
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  5. HISTORY           │
│  Save snapshot, show  │
│  coverage trend       │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  6. AI ANALYSIS       │
│  Risk assessment +    │
│  remediation guidance │
│  (if --ai-provider)   │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  7. ENFORCE           │
│  Block deploy if      │
│  policy requires it   │
└──────────────────────┘
```

### Drift Types

| Drift Type | Description | Plan Actions |
|------------|-------------|--------------|
| **Changed** | Resource exists but attributes differ from IaC definition | `update`, or `delete` + `create` (replace) |
| **Deleted** | Resource is in state but was removed from cloud | `delete` |
| **Unmanaged** | Resource exists in cloud but is not in IaC state | `create` |

### Severity Classification

| Severity | Criteria | Examples |
|----------|----------|---------|
| 🔴 **Critical** | Destructive changes on stateful resources | RDS instance replacement, S3 bucket deletion |
| 🟠 **High** | Changes on critical infrastructure or non-destructive on stateful | EKS cluster update, IAM role change |
| 🟡 **Medium** | Deletions on non-critical resources, changes on compute/network | Security group drift, EC2 instance deletion |
| 🟢 **Low** | Minor attribute changes on non-critical resources | Tag changes, description updates |

### IaC Coverage

```
coverage = ((total_resources - drifted_resources) / total_resources) * 100
```

## Tag-Based Filtering

Use `--filter-tags` to scope drift detection to resources matching specific tags. This is useful for large environments where you want to check drift per environment, team, or cost center without needing separate state files.

### Syntax

```bash
--filter-tags "key=value,key2=value2"
```

| Pattern | Meaning |
|---------|---------|
| `env=prod` | Tag `env` must equal `prod` |
| `env=*` | Tag `env` must exist (any value) |
| `env` | Same as `env=*` (shorthand) |
| `env=prod,team=data` | Both tags must match (AND logic) |

Resources with no tags are excluded when any filter is active.

### Examples

```bash
# Only production drift
thothctl check iac -type drift --filter-tags "env=prod"

# Resources owned by platform team in any environment
thothctl check iac -type drift --filter-tags "team=platform"

# Resources that have a cost-center tag (any value)
thothctl check iac -type drift --filter-tags "cost-center=*"

# Combine multiple filters
thothctl check iac -type drift --filter-tags "env=prod,team=platform,managed-by=terraform"
```

Tags are extracted from the resource's `tags` or `tags_all` attributes in the terraform plan JSON.

## .driftignore

Create a `.driftignore` file in any stack directory to exclude resources from drift detection by address pattern.

```
# Comments start with #
# One pattern per line, supports glob matching

# Ignore all S3 buckets
aws_s3_bucket.*

# Ignore a specific resource
aws_instance.bastion

# Ignore all resources in a module
module.legacy.*
```

## Policy-Based Drift Response

Create a `.driftpolicy` file (YAML or JSON) to codify per-resource drift tolerance. This lets teams define which drift is acceptable, which should block deployments, and which can be auto-accepted.

### .driftpolicy Format

```yaml
# Minimum IaC coverage — blocks deploy if below this
coverage_threshold: 90.0

rules:
  # Security group drift blocks deployment
  - resource: "aws_security_group.*"
    severity_override: critical
    action: block_deploy

  # Tag-only changes on instances are fine
  - resource: "aws_instance.*"
    attribute: "tags.*"
    action: auto_accept

  # Database drift triggers an alert but doesn't block
  - resource: "aws_db_instance.*"
    action: alert

  # Log group changes are noise — hide from reports
  - resource: "aws_cloudwatch_log_group.*"
    action: ignore
```

### Actions

| Action | Behavior | CI/CD Effect |
|--------|----------|--------------|
| `block_deploy` | Fail the check, prevent deployment | Exit code non-zero |
| `alert` | Show in report, warn but allow deployment | Default for unmatched resources |
| `auto_accept` | Silently accept the drift | Removed from drifted count |
| `ignore` | Remove from report entirely | Not shown in output |

### Rule Matching

- Rules are evaluated top-to-bottom, first match wins
- `resource` uses glob patterns against the terraform resource address
- `attribute` (optional) further filters by which attributes changed
- `severity_override` (optional) overrides the auto-detected severity
- Resources not matching any rule default to `alert`

### Coverage Threshold

If `coverage_threshold` is set and the actual IaC coverage falls below it, the check is blocked regardless of individual resource rules.

## Drift History & Trending

ThothCTL automatically saves a snapshot of each drift check and tracks coverage over time. This turns drift detection from a point-in-time check into a continuous observability signal.

### How It Works

- Each run saves a timestamped snapshot to `.thothctl/drift_history/`
- Up to 365 snapshots are retained per project
- Trend analysis shows whether coverage is improving, degrading, or stable

### Console Output

```
╭──────────────── 📊 Drift Trend ────────────────╮
│ Trend: 📉 DEGRADING (Δ -5.2% over 30 snapshots)│
│ Coverage range: 87.3% — 96.1%                   │
│ Current: 87.3% | Peak drifted: 12               │
╰──────────────────────────────────────────────────╯
```

### Threshold Alerts

When coverage drops below the policy threshold (default 90%), a warning is displayed:

```
⚠️ IaC coverage (87.3%) is below threshold (90.0%). Drifted resources: 12
```

### Project Naming

Use `--project-name` to control how history is tracked:

```bash
# Uses directory name by default
thothctl check iac -type drift --recursive

# Explicit project name
thothctl check iac -type drift --recursive --project-name "prod-infra"
```

## AI-Powered Drift Analysis

When an AI provider is configured, drift results are analysed by a specialized drift analyst agent that provides:

- **Security impact assessment** — could any drift introduce vulnerabilities?
- **Root cause hypothesis** — likely cause of each drift (manual change, external automation, provider update)
- **Prioritised remediation plan** — which drifts to fix first and how
- **Risk score** (0-100) for the overall drift state
- **Deploy/block recommendation** based on the analysis

### Usage

```bash
# Using Ollama (local, no data leaves your machine)
thothctl check iac -type drift --recursive --ai-provider ollama

# Using OpenAI
thothctl check iac -type drift --recursive --ai-provider openai

# Using AWS Bedrock
thothctl check iac -type drift --recursive --ai-provider bedrock --ai-model claude-3-sonnet
```

### Console Output

```
╭──────────── 🤖 AI Drift Analysis ─────────────╮
│ Risk score: 72/100                              │
│ Security risks: 1                               │
│ Block deploy: YES                               │
│ Recommendation: Resolve security group drift    │
│ before deploying                                │
╰─────────────────────────────────────────────────╯
  💡 1 security-sensitive resource(s) have drifted — investigate immediately
  💡 Run `thothctl check iac -type drift --post-to-pr` in CI to track drift per PR
```

### Offline Fallback

If no AI provider is configured, a heuristic-based offline analysis runs automatically. It detects security-sensitive resources (IAM, security groups, KMS, secrets) and provides basic risk scoring and recommendations.

### Supported Providers

| Provider | Model | Use Case |
|----------|-------|----------|
| OpenAI | GPT-4 Turbo | Best quality analysis |
| AWS Bedrock | Claude 3 Sonnet | AWS-native environments |
| Azure OpenAI | GPT-4 | Enterprise Azure environments |
| Ollama | Llama 3, Mistral, etc. | Local/offline, no data leaves your machine |

## Output

### Console Output

```
╭──────── 🔍 Drift Detection Summary ────────╮
│ Status: DRIFT DETECTED                      │
│ Stacks scanned: 3                           │
│ Total resources: 47                         │
│ Drifted resources: 5                        │
│ IaC coverage: 89.4%                         │
╰─────────────────────────────────────────────╯

📋 Policy: 2 resource(s) ignored by .driftpolicy
✅ Policy: 1 resource(s) auto-accepted by .driftpolicy

✅ ./networking: no drift (12 resources)

                📂 ./database
┌──────────┬─────────────────────┬──────────────┬─────────┬────────────────────┐
│ Severity │ Resource            │ Type         │ Drift   │ Changed Attributes │
├──────────┼─────────────────────┼──────────────┼─────────┼────────────────────┤
│ 🔴 CRIT  │ aws_db_instance.main│ aws_db_inst… │ changed │ instance_class     │
│ 🟡 MED   │ aws_security_group… │ aws_securit… │ changed │ ingress            │
└──────────┴─────────────────────┴──────────────┴─────────┴────────────────────┘

╭──────────────── 📊 Drift Trend ────────────────╮
│ Trend: 📉 DEGRADING (Δ -5.2% over 30 snapshots)│
│ Coverage range: 87.3% — 96.1%                   │
│ Current: 89.4% | Peak drifted: 8                │
╰──────────────────────────────────────────────────╯

╭──────────── 🤖 AI Drift Analysis ─────────────╮
│ Risk score: 65/100                              │
│ Security risks: 1                               │
│ Block deploy: NO                                │
│ Recommendation: Review drifted resources        │
╰─────────────────────────────────────────────────╯
```

### Generated Reports

Reports are saved to `Reports/drift-detection/`:

| Format | File | Use Case |
|--------|------|----------|
| JSON | `drift_YYYYMMDD_HHMMSS.json` | CI/CD pipelines, programmatic access |
| HTML | `drift_YYYYMMDD_HHMMSS.html` | Browser viewing, sharing with stakeholders |
| Markdown | (via `--post-to-pr`) | Pull request comments |

## CI/CD Integration

### GitHub Actions

```yaml
name: Drift Detection
on:
  schedule:
    - cron: '0 8 * * *'  # Daily at 8am
  workflow_dispatch:

jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Install ThothCTL
        run: pip install thothctl

      - name: Generate plans
        run: |
          for dir in stacks/*/; do
            cd "$dir"
            terraform init -input=false
            terraform plan -out=tfplan.bin
            terraform show -json tfplan.bin > tfplan.json
            cd ../..
          done

      - name: Detect drift (prod only)
        run: |
          thothctl check iac -type drift --recursive \
            --filter-tags "env=prod" \
            --project-name "${{ github.repository }}" \
            --post-to-pr
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Azure DevOps Pipeline

```yaml
trigger: none
schedules:
  - cron: '0 8 * * *'
    displayName: Daily drift check

pool:
  vmImage: 'ubuntu-latest'

steps:
  - script: pip install thothctl
    displayName: Install ThothCTL

  - script: |
      thothctl check iac -type drift --recursive \
        --filter-tags "env=prod" \
        --post-to-pr --vcs-provider azure_repos
    displayName: Detect drift
    env:
      SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

### Policy Enforcement in CI

Add a `.driftpolicy` file to your repo to enforce drift rules in CI:

```yaml
coverage_threshold: 90.0
rules:
  - resource: "aws_security_group.*"
    action: block_deploy
  - resource: "aws_instance.*"
    attribute: "tags.*"
    action: auto_accept
```

When `block_deploy` is triggered, the command exits with a non-zero code, failing the pipeline.

## MCP Integration

Drift detection is available as an MCP tool (`thothctl_drift_detection`):

```json
{
  "directory": "./terraform",
  "recursive": true,
  "tftool": "tofu",
  "filter_tags": "env=prod,team=platform",
  "ai_provider": "ollama",
  "ai_model": "llama3",
  "project_name": "my-infra"
}
```

All parameters except `directory` are optional. The response includes:

- Drift summary with drifted resources and severity
- Policy evaluation results (blocked, ignored, accepted)
- Coverage trend data (improving/degrading/stable)
- AI analysis with risk score and recommendations (if `ai_provider` is set)

## Best Practices

1. **Schedule daily drift checks** — Run drift detection on a schedule to catch manual changes early
2. **Use tag filters in CI** — Scope checks to `env=prod` to focus on what matters
3. **Define a `.driftpolicy`** — Codify your drift tolerance instead of treating all drift equally
4. **Set coverage targets** — Aim for 95%+ IaC coverage and track the trend over time
5. **Use AI analysis for triage** — Let the AI agent prioritise which drift to fix first
6. **Use `.driftignore` sparingly** — Only ignore resources that are intentionally unmanaged
7. **Combine with blast radius** — Use drift detection alongside blast radius assessment for a complete risk picture
8. **Remediate critical drift immediately** — Critical severity drift on stateful resources should be addressed before the next deployment

## Troubleshooting

### No tfplan.json Found

```
⚠️ No tfplan.json found. Running live tofu plan to detect drift...
```

**Solution**: Generate plan files first, or let the tool run a live plan (requires cloud credentials):

```bash
terraform plan -out=tfplan.bin && terraform show -json tfplan.bin > tfplan.json
```

### Plan Timed Out

**Solution**: The default timeout is 10 minutes. For large infrastructure, generate the plan separately and provide the `tfplan.json` file.

### Permission Errors

**Solution**: Ensure your cloud credentials have read access. Drift detection only needs read permissions — it never modifies infrastructure.

### Tag Filter Returns No Results

**Solution**: Verify your resources have the expected tags. Resources without tags are excluded when `--filter-tags` is active. Use `--filter-tags "env=*"` to see all resources that have an `env` tag regardless of value.

### Policy Blocks Deployment Unexpectedly

**Solution**: Review your `.driftpolicy` file. Rules are evaluated top-to-bottom (first match wins). Use `thothctl check iac -type drift` without `--post-to-pr` first to preview what would be blocked.

## Related Commands

- [`thothctl check iac -type tfplan`](plan.md) — Terraform plan analysis
- [`thothctl check iac -type deps`](deps.md) — Dependency visualization
- [`thothctl check iac -type blast-radius`](blast-radius.md) — ITIL v4 risk assessment
- [`thothctl check iac -type cost-analysis`](cost-analysis.md) — Cost estimation
- [`thothctl scan iac`](../scan/scan_overview.md) — Security scanning
- [`thothctl ai-review analyze`](../ai-review/README.md) — AI-powered security analysis
