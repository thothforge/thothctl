# Deploying ThothCTL AI Agent to Amazon Bedrock AgentCore Runtime

Deploy the ThothCTL IaC security agent as a managed, serverless agent on AWS using Bedrock AgentCore Runtime.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Amazon Bedrock AgentCore Runtime               │
│                                                 │
│  main.py (entrypoint)                           │
│    POST /invocations  ──► AgentOrchestrator     │
│    GET  /ping         ──► health check          │
│                             │                   │
│              ┌──────────────┼──────────────┐    │
│              ▼              ▼              ▼    │
│         Security       Architecture      Fix   │
│          Agent           Agent          Agent   │
│              │              │              │    │
│              └──────────────┼──────────────┘    │
│                             ▼                   │
│                      Bedrock Models             │
│                   (Claude Sonnet 4)             │
│                                                 │
│  Memory: S3 (auto-detected in AgentCore)        │
└─────────────────────────────────────────────────┘
```

## Prerequisites

Before you start, make sure you have:

1. **AWS Account** with credentials configured (`aws configure`)
2. **Model access**: Anthropic Claude Sonnet 4 enabled in the [Amazon Bedrock console](https://console.aws.amazon.com/bedrock/home#/modelaccess)
3. **Python 3.13+** installed
4. **uv** installed — [installation guide](https://docs.astral.sh/uv/getting-started/installation/)
5. **AgentCore CLI** installed:
   ```bash
   npm install -g @aws/agentcore
   ```
6. **AWS Permissions**: your IAM user/role needs permissions to create AgentCore runtimes, access S3, and invoke Bedrock models. See [IAM Permissions](#iam-permissions) below.

## Step 1: Set Up the Project

Clone the repository and navigate to the agent directory:

```bash
git clone https://github.com/thothforge/thothctl.git
cd thothctl/src/thothctl/services/ai_review
```

Initialize a Python project and install dependencies:

```bash
uv init --python 3.13
uv add thothctl fastapi uvicorn boto3
```

Verify the entrypoint exists:

```bash
ls main.py
# main.py should be present — this is the AgentCore entrypoint
```

## Step 2: Create the Agent Project with AgentCore CLI

Run the interactive setup:

```bash
agentcore create
```

When prompted:
- **Framework**: choose `custom` (ThothCTL uses its own FastAPI-based entrypoint)
- **Project name**: `thothctl-iac-security-agent`
- **Template**: `basic`

This generates the `agentcore/agentcore.json` configuration. If you already have it from the repo, you can skip this step — the config is at `agentcore/agentcore.json`:

```json
{
  "name": "thothctl-iac-security-agent",
  "description": "ThothCTL AI Agent for IaC security analysis, code review, and auto-fix generation",
  "framework": "custom",
  "runtime": "PYTHON_3_13",
  "entryPoint": ["main.py"],
  "networkConfiguration": {
    "networkMode": "PUBLIC"
  },
  "lifecycleConfiguration": {
    "idleRuntimeSessionTimeout": 300,
    "maxLifetime": 1800
  },
  "environmentVariables": {
    "THOTH_AI_PROVIDER": "bedrock",
    "THOTH_MEMORY_MODE": "auto",
    "AWS_DEFAULT_REGION": "us-east-1"
  }
}
```

## Step 3: Test Locally

Start the agent locally using the AgentCore dev server:

```bash
agentcore dev --no-browser
```

You should see output like:

```
✔ Agent started on http://localhost:8080
```

Open a **second terminal** and run the following tests:

### Test 1: Health probe

```bash
curl http://localhost:8080/ping
```

Expected response:

```json
{"status": "healthy"}
```

### Test 2: Analyze IaC (auto-detect mode)

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze my terraform for security issues", "directory": "/path/to/your/terraform"}'
```

Expected: JSON response with `risk_score`, `findings`, and `recommendations`.

### Test 3: Multi-agent review

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Full security review",
    "mode": "review",
    "directory": "/path/to/your/terraform",
    "roles": ["security", "architecture", "fix"]
  }'
```

Expected: JSON with `security`, `architecture`, and `fixes` sections.

### Test 4: Generate fixes

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Fix high severity findings", "mode": "fix", "directory": "/path/to/your/terraform"}'
```

Expected: JSON with `fixes` array and `summary`.

### Test 5: Pipeline isolation (repository + run_id)

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "review",
    "prompt": "Review PR changes",
    "directory": "/path/to/your/terraform",
    "repository": "myorg/infra",
    "run_id": "pr/42",
    "roles": ["security", "fix"]
  }'
```

Expected: results are stored in memory scoped to `myorg/infra` + `pr/42`.

Stop the local server with `Ctrl+C` when done.

## Step 4: Enable Observability (Optional)

Enable CloudWatch tracing for your agent before deploying:

1. Go to the [Amazon Bedrock AgentCore console](https://console.aws.amazon.com/bedrock-agentcore/)
2. Follow the instructions at [Enabling AgentCore runtime observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-observability-enable.html)

To add OpenTelemetry instrumentation to the agent:

```bash
uv add aws-opentelemetry-distro
```

Then update `agentcore.json` entrypoint:

```json
"entryPoint": ["opentelemetry-instrument", "main.py"]
```

## Step 5: Deploy to AgentCore Runtime

Deploy with a single command:

```bash
agentcore deploy
```

The CLI will:
1. Validate the project structure
2. Package dependencies into a ZIP (ARM64-compatible)
3. Upload to S3
4. Create/update the AgentCore Runtime
5. Show the deployment status

First deployment takes longer (installs dependencies). Subsequent updates reuse cached dependencies and are significantly faster.

Expected output:

```
✔ Project validated
✔ Dependencies packaged
✔ Uploaded to S3
✔ AgentCore Runtime created
  ARN: arn:aws:bedrock-agentcore:us-east-1:123456789:runtime/thothctl-iac-security-agent-xxxxx
  Status: ACTIVE
```

## Step 6: Invoke the Deployed Agent

### Using AgentCore CLI

```bash
# Simple prompt
agentcore invoke "Analyze my terraform for security issues"

# With JSON input
agentcore invoke '{"prompt": "Full review", "mode": "review", "roles": ["security", "fix"]}'
```

### Using curl (programmatic)

Get the endpoint first:

```bash
ENDPOINT=$(aws bedrock-agentcore get-agent-runtime-endpoint \
  --agent-runtime-id <YOUR_RUNTIME_ID> \
  --query 'endpoint' --output text)

echo "Agent endpoint: $ENDPOINT"
```

Then invoke:

```bash
curl -X POST "$ENDPOINT/invocations" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze terraform for security issues",
    "mode": "analyze",
    "directory": "."
  }'
```

### Using boto3 (Python)

```python
import boto3
import json

client = boto3.client("bedrock-agentcore", region_name="us-east-1")

response = client.invoke_runtime_session(
    agentRuntimeArn="arn:aws:bedrock-agentcore:us-east-1:123456789:runtime/thothctl-iac-security-agent-xxxxx",
    qualifier="DEFAULT",
    payload=json.dumps({
        "prompt": "Review my terraform",
        "mode": "review",
        "repository": "myorg/infra",
        "run_id": "pr/42",
    }),
)

result = json.loads(response["body"].read())
print(json.dumps(result, indent=2))
```

## Step 7: Update the Agent

After making code changes, redeploy:

```bash
agentcore deploy
```

The CLI detects the existing runtime and updates it in place.

## Step 8: Stop Sessions and Cleanup

### Stop a running session (save costs)

Sessions auto-expire after `idleRuntimeSessionTimeout` (default: 5 min), but you can stop them early:

```bash
aws bedrock-agentcore stop-runtime-session \
  --agent-runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789:runtime/thothctl-iac-security-agent-xxxxx \
  --runtime-session-id <SESSION_ID> \
  --qualifier DEFAULT
```

### Delete the agent entirely

```bash
agentcore remove all
agentcore deploy
```

This tears down all AWS resources (CloudFormation stack, S3 artifacts, runtime).

## Invocation Contract

### POST /invocations

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | string | required | Natural language request (mode auto-detected) |
| `mode` | string | auto | `analyze`, `review`, or `fix` |
| `directory` | string | `.` | Path to IaC code (or `$THOTH_SCAN_DIR`) |
| `provider` | string | `bedrock` | AI provider (`bedrock`, `bedrock_agent`, `ollama`) |
| `model` | string | | Override model (e.g. `anthropic.claude-sonnet-4-20250514`) |
| `roles` | list | `["security","architecture","fix"]` | Agents to run (review mode) |
| `repository` | string | | Repo ID for memory isolation |
| `run_id` | string | | Pipeline/PR ID for memory isolation |

**Mode auto-detection from prompt:**

| Keywords in prompt | Detected mode |
|-------------------|---------------|
| fix, improve, remediate, patch | `fix` |
| review, orchestrate, multi-agent, full | `review` |
| anything else | `analyze` |

### GET /ping

Returns `{"status": "healthy"}`. Used by AgentCore for health probes.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `THOTH_AI_PROVIDER` | `bedrock` | AI provider for analysis |
| `THOTH_SCAN_DIR` | `.` | Default directory to scan |
| `THOTH_MEMORY_MODE` | `auto` | Memory backend (`auto`, `local`, `agentcore`) |
| `THOTH_MEMORY_S3_BUCKET` | | S3 bucket for agentcore memory |
| `AWS_DEFAULT_REGION` | `us-east-1` | AWS region |
| `AGENTCORE_RUNTIME` | | Set automatically by AgentCore Runtime |

When running in AgentCore, `AGENTCORE_RUNTIME` is set automatically, which triggers the S3 memory backend.

## Memory in AgentCore

The agent auto-detects the AgentCore runtime and switches to S3-backed memory:

```
s3://{THOTH_MEMORY_S3_BUCKET}/thothctl/ai_sessions/
├── repos/
│   └── myorg_infra/
│       ├── decisions.json           # Shared audit trail
│       └── runs/
│           └── pr_42/
│               └── analysis.json    # Pipeline-isolated
├── sessions/
│   └── {session_id}.json
└── state/
    └── {agent_id}.json
```

## IAM Permissions

The AgentCore execution role needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": "arn:aws:bedrock:*::foundation-model/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::${THOTH_MEMORY_S3_BUCKET}/thothctl/*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## CI/CD Integration

### GitHub Actions → AgentCore

```yaml
name: IaC Security Review via AgentCore
on: [pull_request]

jobs:
  security-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Get AgentCore endpoint
        id: endpoint
        run: |
          ENDPOINT=$(aws bedrock-agentcore get-agent-runtime-endpoint \
            --agent-runtime-id ${{ secrets.AGENTCORE_RUNTIME_ID }} \
            --query 'endpoint' --output text)
          echo "url=$ENDPOINT" >> $GITHUB_OUTPUT

      - name: Run security review
        run: |
          curl -X POST "${{ steps.endpoint.outputs.url }}/invocations" \
            -H "Content-Type: application/json" \
            -d '{
              "mode": "review",
              "directory": ".",
              "repository": "${{ github.repository }}",
              "run_id": "pr/${{ github.event.pull_request.number }}",
              "roles": ["security", "fix"]
            }' > review.json
          cat review.json | jq '.result.security.risk_score'
```

### Azure DevOps Pipelines → AgentCore

```yaml
- script: |
    ENDPOINT=$(aws bedrock-agentcore get-agent-runtime-endpoint \
      --agent-runtime-id $(AGENTCORE_RUNTIME_ID) \
      --query 'endpoint' --output text)

    curl -X POST "$ENDPOINT/invocations" \
      -H "Content-Type: application/json" \
      -d '{
        "mode": "review",
        "directory": "$(Build.SourcesDirectory)",
        "repository": "$(Build.Repository.Name)",
        "run_id": "pr/$(System.PullRequest.PullRequestId)",
        "roles": ["security", "fix"]
      }' > review.json
  displayName: 'Run AgentCore Security Review'
  env:
    AWS_ACCESS_KEY_ID: $(AWS_ACCESS_KEY_ID)
    AWS_SECRET_ACCESS_KEY: $(AWS_SECRET_ACCESS_KEY)
    AWS_DEFAULT_REGION: us-east-1
```

## Manual Deployment (ZIP + boto3)

If you prefer not to use the AgentCore CLI, you can build and deploy manually.

### Build deployment package

```bash
cd src/thothctl/services/ai_review

# Install ARM64-compatible dependencies (AgentCore runs on arm64)
uv pip install \
  --python-platform aarch64-manylinux2014 \
  --python-version 3.13 \
  --target=deployment_package \
  --only-binary=:all: \
  thothctl fastapi uvicorn boto3

# Create ZIP archive
cd deployment_package
zip -r ../deployment_package.zip .
cd ..
zip deployment_package.zip main.py
```

### Upload and create runtime

```python
import boto3

account_id = "<YOUR_ACCOUNT_ID>"
agent_name = "thothctl-iac-security-agent"
region = "us-east-1"
bucket = f"bedrock-agentcore-code-{account_id}-{region}"

# Upload ZIP to S3
s3 = boto3.client("s3", region_name=region)
s3.upload_file(
    "deployment_package.zip",
    bucket,
    f"{agent_name}/deployment_package.zip",
    ExtraArgs={"ExpectedBucketOwner": account_id},
)

# Create AgentCore Runtime
client = boto3.client("bedrock-agentcore-control", region_name=region)
response = client.create_agent_runtime(
    agentRuntimeName=agent_name,
    agentRuntimeArtifact={
        "codeConfiguration": {
            "code": {
                "s3": {
                    "bucket": bucket,
                    "prefix": f"{agent_name}/deployment_package.zip",
                }
            },
            "runtime": "PYTHON_3_13",
            "entryPoint": ["main.py"],
        }
    },
    networkConfiguration={"networkMode": "PUBLIC"},
    roleArn=f"arn:aws:iam::{account_id}:role/AmazonBedrockAgentCoreSDKRuntime-{region}",
    lifecycleConfiguration={
        "idleRuntimeSessionTimeout": 300,
        "maxLifetime": 1800,
    },
)
print(f"ARN: {response['agentRuntimeArn']}")
print(f"Status: {response['status']}")
```

## Running Locally (Without AgentCore)

The agent runs locally without the AgentCore CLI or any AWS infrastructure. Three options:

### Option 1: ThothCTL CLI (simplest)

```bash
pip install thothctl
thothctl ai-review serve --port 8080
```

### Option 2: Uvicorn directly

```bash
uvicorn thothctl.services.ai_review.main:app --port 8080
```

### Option 3: AgentCore dev server

```bash
agentcore dev --no-browser
```

All three start the same `/invocations` + `/ping` endpoints on `localhost:8080`.

### Using Ollama for fully offline analysis

No data leaves your machine when using Ollama as the AI provider:

```bash
# Pull a model
ollama pull llama3

# Set as default provider
export THOTH_AI_PROVIDER=ollama

# Invoke
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze my terraform", "directory": "./terraform"}'
```

Or pass `"provider": "ollama"` in each request body.

### Local vs AgentCore differences

| Feature | Local | AgentCore Runtime |
|---------|-------|-------------------|
| Memory backend | Filesystem (`.thothctl/ai_sessions/`) | S3 (auto-detected) |
| AI provider | Any (ollama, bedrock, openai) | Typically `bedrock` |
| Scaling | Single process | Managed serverless |
| Session management | Manual | Auto idle timeout |
| Observability | Logs only | CloudWatch + OpenTelemetry |

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|---------|
| `CREATE_FAILED` | Wrong architecture binaries | Rebuild with `--python-platform aarch64-manylinux2014` |
| `ImportError` at runtime | Missing dependency in ZIP | Add missing package to `uv add` and redeploy |
| `/invocations` returns 500 | No Bedrock model access | Enable Claude Sonnet 4 in Bedrock console |
| S3 memory not working | Missing `THOTH_MEMORY_S3_BUCKET` | Set env var in `agentcore.json` or runtime config |
| Timeout on large repos | `maxLifetime` too short | Increase `maxLifetime` in `agentcore.json` |
| Permission denied on S3 | Execution role missing S3 policy | Add `s3:GetObject`/`s3:PutObject` to the role |

## File Structure

```
services/ai_review/
├── main.py                  # AgentCore entrypoint (/invocations + /ping)
├── agentcore/
│   └── agentcore.json       # AgentCore Runtime configuration
├── bedrock_agent_api.py     # Original FastAPI REST API (still works standalone)
├── orchestrator.py          # Multi-agent coordinator
├── ai_agent.py              # Single-agent analysis + fix generation
├── memory.py                # Adaptive local/S3 memory backend
└── ...
```
