# Agent Specifications

This document defines the contract for each AI agent in ThothCTL's multi-agent orchestrator: what context it receives, what it produces, and how to customize its behavior.

## Agent Roles

| Role | System Prompt | Input Context | Output Schema |
|------|--------------|---------------|---------------|
| **Security** | `SYSTEM_SECURITY_ANALYST` | Scan findings + affected code | Prioritized findings with remediation |
| **Architecture** | `SYSTEM_CODE_REVIEWER` | Inventory + blast radius + code structure | Issues by category with suggestions |
| **Fix** | `SYSTEM_FIX_GENERATOR` | Findings + full source code | Actionable code patches |
| **Decision** | `DecisionEngine` (rule-based) | Merged results from other agents | approve / reject / request-changes |

## Security Agent

**Purpose:** Analyze scan results from Checkov, KICS, Trivy, OPA/Conftest and prioritize findings by business impact.

**Input context:**
- Scan result summaries (tool, pass/fail counts, individual checks)
- Affected `.tf` / `.hcl` source code snippets
- Enforcement mode per finding (soft or hard)

**Output schema:**

```json
{
  "summary": {
    "total_findings": 12,
    "critical": 1,
    "high": 3,
    "medium": 5,
    "low": 3
  },
  "findings": [
    {
      "id": "CKV_AWS_19",
      "severity": "HIGH",
      "title": "S3 bucket encryption not enabled",
      "description": "...",
      "resource": "aws_s3_bucket.data",
      "remediation": "Add server_side_encryption_configuration block",
      "code_example": "resource \"aws_s3_bucket_server_side_encryption_configuration\" ...",
      "compliance": ["CIS 2.1.1", "NIST SC-28"],
      "source_tool": "checkov",
      "enforce_hard": true
    }
  ],
  "risk_score": 72.5,
  "recommendations": ["Enable encryption on all S3 buckets", "..."]
}
```

## Architecture Agent

**Purpose:** Review module structure, dependency risks, blast radius, and best practice violations.

**Input context:**
- Module inventory (names, versions, sources, registry status)
- Dependency graph (Terragrunt `dependency` blocks)
- Blast radius analysis (affected components per change)
- Code structure overview

**Output schema:**

```json
{
  "summary": {
    "total_issues": 8,
    "security": 2,
    "best_practice": 3,
    "cost": 1,
    "reliability": 2
  },
  "issues": [
    {
      "severity": "MEDIUM",
      "category": "best_practice",
      "file": "modules/networking/main.tf",
      "line": 42,
      "title": "Hardcoded availability zone",
      "description": "AZ should be derived from data source, not hardcoded",
      "suggestion": "Use data.aws_availability_zones.available.names[0]"
    }
  ],
  "overall_assessment": "Module structure is well-organized but..."
}
```

## Fix Agent

**Purpose:** Generate precise, apply-ready code patches for security findings.

**Input context:**
- Findings list with check IDs and severity
- Full content of affected files (exact text needed for matching)

**Output schema:**

```json
{
  "fixes": [
    {
      "fix_id": "fix_001",
      "finding_id": "CKV_AWS_19",
      "file": "s3.tf",
      "fix_type": "add_block",
      "severity": "HIGH",
      "description": "Enable S3 bucket encryption",
      "original": "resource \"aws_s3_bucket\" \"data\" {\n  bucket = \"my-bucket\"\n}",
      "replacement": "resource \"aws_s3_bucket\" \"data\" {\n  bucket = \"my-bucket\"\n}\n\nresource \"aws_s3_bucket_server_side_encryption_configuration\" \"data\" {\n  ...\n}",
      "validation": "Run: terraform validate && checkov -f s3.tf --check CKV_AWS_19"
    }
  ],
  "skipped": [
    {"finding_id": "CKV_AWS_999", "reason": "Requires manual review"}
  ],
  "summary": {"total_findings": 5, "fixes_generated": 3, "skipped": 2}
}
```

**Fix types:**

| Type | Description |
|------|-------------|
| `replace_line` | Replace exact line(s) with corrected version |
| `add_block` | Add a new resource/block after existing code |
| `modify_attribute` | Change a value within an existing block |
| `add_attribute` | Add a missing attribute to an existing block |
| `remove_block` | Remove an insecure block (rare — only for explicitly dangerous config) |

## Decision Agent

**Purpose:** Determine PR action based on merged analysis from other agents.

**Implementation:** Rule-based engine (not an LLM call). Uses `DecisionEngine` with configurable thresholds.

**Input:** `OrchestratorResult` containing security, architecture, and fix results.

**Output:**

```json
{
  "action": "approve | reject | request_changes",
  "confidence": 0.92,
  "reason": "Risk score 15/100, no critical findings, all high findings have fixes",
  "blocking_findings": [],
  "suggestion_count": 3
}
```

**Decision logic:**

| Condition | Action |
|-----------|--------|
| Risk ≤ approve_threshold AND confidence ≥ 90% AND no blocking patterns | **approve** |
| Risk ≥ reject_threshold AND confidence ≥ 85% AND blocking patterns found | **reject** |
| Everything else | **request_changes** |

## Customizing Agent Behavior

### Override system prompts

Create `.thothctl/prompts/` in your project with custom prompt files:

```
.thothctl/prompts/
├── security.txt       # Overrides SYSTEM_SECURITY_ANALYST
├── architecture.txt   # Overrides SYSTEM_CODE_REVIEWER
└── fix.txt            # Overrides SYSTEM_FIX_GENERATOR
```

Not yet implemented — currently prompts are compiled into the package. To customize today, fork and modify `src/thothctl/services/ai_review/utils/prompts.py`.

### Model settings per agent

Configure in `.thothctl/ai_config.yaml`:

```yaml
ai_review:
  default_provider: bedrock_agent
  providers:
    bedrock_agent:
      model: "anthropic.claude-sonnet-4-20250514"
      max_tokens: 4000       # Max output tokens per agent call
      temperature: 0.1       # Low = deterministic, high = creative
      region: "us-east-1"
```

| Setting | Effect |
|---------|--------|
| `max_tokens` | Limits output length — increase for large codebases |
| `temperature` | 0.0–0.3 recommended for security analysis; higher for creative fixes |
| `model` | Applies to all agents using this provider |

### Decision thresholds

```bash
# Via CLI
thothctl ai-review configure-decisions \
  --approve-threshold 15 \
  --reject-threshold 90 \
  --daily-approve-limit 30

# Via config file (.thothctl/ai_config.yaml)
```

```yaml
ai_review:
  decision_rules:
    enabled: true
    approve_threshold: 15        # Max risk score to auto-approve
    reject_threshold: 90         # Min risk score to auto-reject
    approve_confidence: 0.92     # Min confidence for approve
    reject_confidence: 0.88      # Min confidence for reject
    daily_approve_limit: 30
    daily_reject_limit: 10
    cooldown_seconds: 300
    blocking_patterns:
      - "hardcoded_secret"
      - "public_s3"
      - "unrestricted_sg"
      - "admin_access"
      - "unencrypted_db"
```

### Cost controls

```yaml
ai_review:
  cost_controls:
    daily_limit: 100           # Max API calls per day
    monthly_budget: 200.0      # USD budget (tracked per provider)
    auto_fallback: true        # Fall back to offline patterns when budget exceeded
```

When budget is exceeded:
- AI agents are skipped
- Built-in fix patterns (13 Checkov rules) still run
- Risk scoring uses rule-based assessor (no LLM)

## Context Builder

The orchestrator builds a shared `IaCContext` object from the project directory before dispatching agents:

| Data Source | How Collected | Used By |
|-------------|---------------|---------|
| Scan results | Parses `Reports/` directory (Checkov JSON, KICS, Trivy) | Security, Fix |
| Code files | Reads `.tf`, `.hcl` files recursively | Security, Architecture, Fix |
| Inventory | Runs `thothctl inventory` internally | Architecture |
| Blast radius | Parses dependency graph | Architecture |
| Previous analysis | Loads from memory (if `--repository` provided) | All (enrichment) |

## Adding a Custom Agent Role

The orchestrator supports any role defined in the `AgentRole` enum. To add a new agent:

1. Add the role to `AgentRole` enum in `orchestrator.py`:

```python
class AgentRole(str, Enum):
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    FIX = "fix"
    DECISION = "decision"
    COST = "cost"  # new
```

2. Add a field to `OrchestratorResult`:

```python
@dataclass
class OrchestratorResult:
    ...
    cost_analysis: Dict[str, Any] = field(default_factory=dict)
```

3. Create the system prompt in `utils/prompts.py`

4. Add task creation logic in `_create_tasks()`:

```python
if AgentRole.COST in roles:
    cost_ctx = self._format_cost_context(ctx)
    if cost_ctx:
        tasks.append(AgentTask(
            role=AgentRole.COST,
            system_prompt=SYSTEM_COST_ANALYST,
            context=cost_ctx,
        ))
```

5. Pass it via CLI: `thothctl ai-review orchestrate -a cost`
