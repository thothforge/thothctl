# Phase 1: Intent-to-IaC Generation — Implementation Spec

> **Version**: 1.0 | **Target**: v0.23.0 | **Effort**: ~14 days  
> **Author**: ThothForge | **Status**: Ready for implementation

## Overview

Generate governed Terraform/Terragrunt/CDK code from natural language intent. The AI produces compliant code because it reads your organizational conventions (`.thothcf.toml`, steering docs, existing patterns) as context. Existing Checkov + OPA/Conftest validate the output — no new policy engine needed.

## Design Principles

1. **No new evaluation engine** — OPA and Checkov are the validators
2. **Context injection, not RAG** — compile rules into a text payload injected into the prompt
3. **Reuse everything** — providers, scanners, MCP server, topology generator
4. **Works offline** — Ollama + local policies = fully local pipeline
5. **Self-correction** — if validation fails, re-prompt AI with violations (max 3 retries)
6. **Framework-Defined Infrastructure** — the output follows your org framework, not generic best practices

## Architecture

```
User Intent (natural language)
       ↓
┌──────────────────────────────────────────────────────────────────────┐
│                    IntentToIaCService                                  │
│                                                                        │
│  1. ContextBuilder.build_context(directory)                           │
│     ├── Load .thothcf.toml (project_type, naming, tags, environment) │
│     ├── Load steering docs (.kiro/steering/ or CLAUDE.md)            │
│     ├── Load existing patterns (sample files from stacks/)           │
│     └── Summarize org policies (OPA .rego file headers)              │
│     → Structured context string (~4-8K tokens)                       │
│                                                                        │
│  2. CodeGenerator.generate(intent, context, project_type)            │
│     ├── Format system prompt with context + rules                    │
│     ├── Call AI provider (Ollama/Bedrock/OpenAI/Azure)               │
│     └── Parse JSON response → List[GeneratedFile]                    │
│                                                                        │
│  3. GenerationValidator.validate(files, org_policy_dir)              │
│     ├── Write files to temp directory                                │
│     ├── Run CheckovScanner.scan(temp_dir)                            │
│     ├── Run OPAScanner.scan(temp_dir) if policies available          │
│     └── Return ValidationResult(passed, violations)                  │
│                                                                        │
│  4. Self-Correction Loop (if --self-correct and violations > 0)      │
│     ├── Format violations as AI feedback                             │
│     ├── Re-prompt: "Fix these violations: [...]"                     │
│     └── Repeat step 3 (max 3 iterations)                            │
│                                                                        │
│  5. Output                                                            │
│     ├── --dry-run: display with Rich (syntax highlighted)            │
│     ├── --apply: write files to target directory                     │
│     └── Auto-generate Mermaid diagram (topology_generator)           │
└──────────────────────────────────────────────────────────────────────┘
```

## File Structure

```
src/thothctl/
├── commands/generate/commands/
│   └── iac.py                              # CLI command (Click)
├── services/generate/intent/
│   ├── __init__.py
│   ├── intent_service.py                  # Pipeline orchestrator
│   ├── context_builder.py                 # Builds AI context from project
│   ├── code_generator.py                  # Calls AI provider, parses output
│   ├── validator.py                       # Runs Checkov + OPA on generated code
│   ├── prompts.py                         # System prompts per project type
│   └── models.py                          # Data models (GeneratedFile, IntentResult, etc.)
└── services/mcp/stdio_server.py           # Add thothctl_generate_iac tool
```

## Data Models (`models.py`)

```python
@dataclass
class GeneratedFile:
    path: str          # Relative path (e.g., "stacks/foundation/network/vpc/main.tf")
    content: str       # Full file content

@dataclass
class ValidationResult:
    passed: bool
    violations: List[Dict[str, str]]  # [{check_id, severity, resource, message}]
    tool: str                          # "checkov" | "opa"

@dataclass
class IntentResult:
    files: List[GeneratedFile]
    validation: ValidationResult
    iterations: int                    # How many correction attempts
    explanation: str                   # AI's explanation of what was generated
    modules_used: List[str]           # Module sources used
    estimated_resources: List[str]    # Resource types that will be created
    context_tokens: int               # Tokens used for context
    generation_tokens: int            # Tokens used for generation
```

## Context Builder Spec (`context_builder.py`)

### Sources (in order)

| Source | Max Tokens | What's Extracted |
|--------|-----------|-----------------|
| `.thothcf.toml` | ~500 | project_type, template_input_parameters (naming patterns, region, environment, tags) |
| `.kiro/steering/iac-rules.md` or `.claude/rules/` | ~2000 | IaC composition rules (module sources, patterns, mandatory tags, prohibited practices) |
| `.kiro/steering/product.md` / `CLAUDE.md` | ~500 | Project purpose, target architecture, layers |
| Existing patterns (up to 3 files from `stacks/`) | ~2000 | Real terragrunt.hcl/main.tf examples showing team conventions |
| Org policies (`.rego` files) | ~500 | First 10 lines of each policy (rule names + comments for context) |
| **Total** | **~5500** | |

### Output Format

```markdown
# Organizational Context

## Project Configuration
- Project type: terraform-terragrunt
- Cloud provider: aws
- Environment: prod
- Naming pattern: {environment}-{project_name}-{resource}
- Required tags: Environment, Owner, CostCenter, ManagedBy

## IaC Rules
- Use terraform-aws-modules first (official AWS modules preferred)
- Pin exact versions (e.g., version = "5.17.0")
- All stacks must have: terragrunt.hcl, main.tf, variables.tf, outputs.tf
- Dependency pattern: include root, dependency with mock_outputs
- Stacks path: stacks/{layer}/{domain}/{service}/

## Existing Patterns (from this project)

### Example: stacks/foundation/network/vpc/terragrunt.hcl
```hcl
include "root" { path = find_in_parent_folders("root.hcl") }
...
```

## Organization Policies (OPA)
- deny_public_s3: S3 buckets must not have public ACL
- require_encryption: All storage resources must enable encryption
- require_tags: Resources must have Environment, Owner tags
```

## System Prompt Spec (`prompts.py`)

### Generation Prompt

```
You are an expert {project_type} code generator.
Generate complete, deployable infrastructure code following these organizational standards.

{context}

INSTRUCTIONS:
1. Generate ALL required files for a complete stack
2. Use modules from terraform-aws-modules when available
3. Pin exact versions on all module sources
4. Include all mandatory tags from the organizational rules
5. Follow the naming conventions specified
6. For terragrunt: include proper include, dependency, locals, and inputs blocks
7. For terraform: include provider, backend, and resource configurations

OUTPUT FORMAT (valid JSON):
{
  "files": [
    {"path": "relative/path/to/file.tf", "content": "full file content"},
    ...
  ],
  "explanation": "brief explanation of architecture decisions",
  "modules_used": ["source@version", ...],
  "estimated_resources": ["aws_vpc", "aws_subnet", ...]
}

Generate ONLY the JSON. No markdown fences, no extra text.
```

### Self-Correction Prompt

```
The generated code has validation violations. Fix them while maintaining all organizational rules.

VIOLATIONS:
{violations_formatted}

PREVIOUS CODE:
{previous_files_summary}

Generate the corrected files in the same JSON format.
Fix ALL violations while keeping the architecture intact.
```

## Validator Spec (`validator.py`)

### Flow

1. Create temp directory
2. Write all `GeneratedFile` contents to temp directory (preserving paths)
3. Run `CheckovScanner.scan(temp_dir, reports_dir, options={})`
4. If org policy available: Run `OPAScanner.scan(temp_dir, reports_dir, options={"policy_dir": ...})`
5. Parse results → `ValidationResult`
6. Clean up temp directory

### Violation Format (for self-correction prompt)

```
- [HIGH] CKV_AWS_130: Ensure VPC flow logs are enabled (resource: aws_vpc.main)
- [MEDIUM] CKV_AWS_178: Ensure NAT gateway is in multiple AZs (resource: aws_nat_gateway.main)
```

## CLI Command Spec (`commands/generate/commands/iac.py`)

### Options

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--intent` | `-i` | STRING | (required) | Natural language description of desired infrastructure |
| `--project-type` | `-pt` | CHOICE | auto | `terraform`, `terraform-terragrunt`, `terragrunt`, `cdkv2`, `cloudformation` |
| `--provider` | `-p` | CHOICE | ollama | AI provider: `ollama`, `bedrock`, `openai`, `azure` |
| `--model` | `-m` | STRING | None | Model override (e.g., `llama3`, `claude-sonnet-4-20250514`) |
| `--output-dir` | `-o` | PATH | . | Target directory for generated files |
| `--dry-run` | | FLAG | True | Preview generated code without writing |
| `--apply` | | FLAG | False | Write generated files to disk |
| `--self-correct` | | FLAG | True | Re-prompt AI on validation failures |
| `--max-iterations` | | INT | 3 | Maximum self-correction attempts |
| `--skip-validation` | | FLAG | False | Skip Checkov/OPA validation |
| `--include-diagram` | | FLAG | True | Generate Mermaid architecture diagram |

### Examples in Help Text

```
Examples:
  # Generate VPC with private subnets (dry-run by default)
  thothctl generate iac -i "VPC with 3 private subnets and NAT gateway"

  # Generate and write to specific directory
  thothctl generate iac -i "EKS cluster with managed node groups" \
    --output-dir ./stacks/platform/containers/eks --apply

  # Use AWS Bedrock instead of local Ollama
  thothctl generate iac -i "S3 bucket with versioning and replication" \
    -p bedrock -m claude-sonnet-4-20250514

  # Skip validation (trust AI output)
  thothctl generate iac -i "CloudWatch alarms for RDS" --skip-validation --apply
```

## MCP Tool Spec

Add to `services/mcp/stdio_server.py`:

```python
{
    "name": "thothctl_generate_iac",
    "description": "Generate governed Infrastructure as Code from natural language intent. "
                   "Uses organizational rules from .thothcf.toml and validates with Checkov/OPA.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "Natural language description of desired infrastructure"
            },
            "project_type": {
                "type": "string",
                "enum": ["auto", "terraform", "terraform-terragrunt", "cdkv2", "cloudformation"],
                "default": "auto"
            },
            "self_correct": {
                "type": "boolean",
                "default": True,
                "description": "Re-prompt AI to fix validation violations"
            },
            "apply": {
                "type": "boolean",
                "default": False,
                "description": "Write files to disk (False = dry-run only)"
            }
        },
        "required": ["intent"]
    }
}
```

## Reused Components (NO new code)

| Component | Location | Used For |
|-----------|----------|----------|
| AI providers (5) | `services/ai_review/providers/` | LLM calls |
| Provider config | `services/ai_review/config/ai_settings.py` | Model/temperature/tokens |
| Cost tracker | `services/ai_review/utils/cost_tracker.py` | Budget enforcement |
| Checkov scanner | `services/scan/scanners/checkov.py` | Validate generated code |
| OPA scanner | `services/scan/scanners/opa.py` | Policy validation |
| Org policy loader | `services/check/org_policy_loader.py` | Find .rego files |
| Rule merger | `services/check/rule_merger.py` | Load .thothcf.toml |
| Topology generator | `services/document/topology_generator.py` | Diagram from output |
| MCP server | `services/mcp/stdio_server.py` | Expose as tool |
| CliUI | `core/cli_ui.py` | Console output |

## Testing Strategy

### Unit Tests (`tests/test_generate_iac.py`)

| Test | What it validates |
|------|-------------------|
| `test_context_builder_loads_thothcf` | Reads .thothcf.toml correctly |
| `test_context_builder_loads_steering` | Reads .kiro/steering/ or CLAUDE.md |
| `test_context_builder_loads_patterns` | Finds and truncates example files |
| `test_context_builder_loads_rego_summaries` | Extracts policy rule names |
| `test_context_builder_no_files` | Returns sensible defaults when nothing exists |
| `test_context_token_limit` | Output stays under ~8K tokens |
| `test_code_generator_parses_json` | Correctly parses AI JSON response |
| `test_code_generator_handles_malformed` | Handles non-JSON AI responses gracefully |
| `test_validator_passes_clean_code` | No violations = passed |
| `test_validator_catches_violations` | Known-bad code triggers findings |
| `test_self_correction_loop` | Iterates and fixes |
| `test_self_correction_max_iterations` | Stops at max_iterations |
| `test_intent_service_dry_run` | Doesn't write files on dry-run |
| `test_intent_service_apply` | Writes files on --apply |
| `test_cli_requires_intent` | Fails without --intent |
| `test_mcp_tool_registered` | Tool appears in MCP server |

### Integration Test (manual, not automated)

```bash
# Requires Ollama running locally with llama3
thothctl generate iac \
  -i "VPC with 3 private subnets and NAT gateway for production" \
  -p ollama --dry-run
```

## Implementation Order

```
Day 1-2:  models.py + context_builder.py + tests
Day 3:    prompts.py (generation + self-correction prompts)
Day 4-5:  code_generator.py + tests
Day 6-7:  validator.py + tests
Day 8-9:  intent_service.py (orchestrator) + tests
Day 10:   CLI command (iac.py) + integration
Day 11:   MCP tool registration
Day 12-13: End-to-end testing + edge cases
Day 14:   Documentation + examples
```

## Out of Scope (deferred to later phases)

| Feature | Deferred To | Reason |
|---------|-------------|--------|
| Custom policy evaluation engine | Not needed | OPA + Checkov are sufficient |
| RAG / vector database | Not needed | Context injection is simpler, works offline |
| Multi-turn conversation | Phase 2.5 | Requires agent governance framework |
| Template registry service | Future | Use project patterns as few-shot examples for now |
| Cost estimation on generated code | Future | Needs `terraform plan` which requires `init` first |
| PR creation from generated code | Phase 4 | Requires workflow engine |

## Success Criteria

| Criterion | Target | How Verified |
|-----------|--------|--------------|
| Generates valid HCL from NL intent | Top 10 AWS resources | Manual test matrix |
| Checkov passes first attempt | >60% | Track over 20 generations |
| Checkov passes after self-correction | >90% | Track over 20 generations |
| Respects .thothcf.toml naming/tags | 100% | Context always injected |
| Works with Ollama (offline) | Yes | CI test without internet |
| Works without .thothcf.toml | Yes | Defaults to sensible patterns |
| End-to-end time (Ollama llama3) | <60s | Benchmark |
| End-to-end time (Bedrock Claude) | <30s | Benchmark |
| Unit tests pass | 16+ tests | pytest |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| AI returns invalid JSON | Generation fails | Regex JSON extraction fallback (same as ai_review) |
| AI hallucinates module names | Invalid code | Validation catches it; self-correction fixes |
| Context too large for model | Truncation/quality | Token budget per section; prioritize rules over examples |
| Checkov has false positives | Infinite correction loop | max_iterations cap; `--skip-validation` escape hatch |
| Ollama too slow for large prompts | Bad UX | Show progress spinner; recommend smaller model for generation |
