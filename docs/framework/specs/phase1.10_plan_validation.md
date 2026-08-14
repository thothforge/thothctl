# Phase 1.10: Secure Plan Validation for Intent-to-IaC Pipeline

> **Version**: 1.0 | **Target**: v0.27.0 | **Effort**: ~14 days  
> **Author**: ThothForge | **Status**: ✅ Implemented (v0.27.0, 2026-08-14)  
> **Depends on**: Phase 1 (Intent-to-IaC) ✅, Phase 1.9 (Composition) ✅  
> **Last updated**: 2026-08-14

## Problem Statement

The Intent-to-IaC pipeline validates generated code with `terraform validate` (syntax), Checkov (security), and OPA (policy). However, these static tools miss **deployability errors** that only `terraform plan` detects:

- Invalid resource attribute combinations (instance type not available in AZ)
- Cross-resource reference errors only visible at plan time
- Provider-specific constraints (name length, character restrictions)
- Missing required provider-level configuration

### Evidence

| Source | Finding |
|--------|---------|
| DPIaC-Eval (FSE 2026) | First-attempt deployment success: 20-30% for frontier LLMs |
| IaCGen (Zhang 2025) | Iterative plan feedback achieves 98% deployability |
| MACOG (Virginia Tech 2025) | Removing plan sandbox drops IaC-Eval by 23% |

### Core Challenge

Running `terraform plan` in the generation loop requires:
1. **Cloud credentials** — provider API access for resource validation
2. **State access** — remote state (S3) for incremental changes
3. **Provider plugins** — downloaded during `terraform init`

The existing `DriftDetectionService` already solves this problem for drift detection — it runs `terraform plan` using the user's ambient environment. Plan validation for generation should reuse this exact pattern.

## Design Principles

1. **Follow existing patterns** — `DriftDetectionService._run_plan()` is the reference implementation
2. **Trust user's environment** — same credential model as `thothctl check iac --type drift`
3. **Fail open** — if plan cannot run, skip gracefully (pipeline continues with validate+checkov+opa)
4. **No new credential system** — user configures `aws sso login`, env vars, or profile as they already do
5. **Leverage tftool selection** — respect `--tftool` flag (terraform vs tofu) consistently
6. **Temp workspace isolation** — plan runs in the existing temp directory (same as current validation)
7. **Configuration-driven** — disabled by default, opt-in via `.thothcf.toml`

## Architecture

### How It Fits Into the Existing Flow

```
Current pipeline (what exists):
  ContextBuilder → CodeGenerator → GenerationValidator → Self-Correction
                                          │
                                          ├── terraform validate (FV-i) ← uses init -backend=false
                                          ├── Checkov ← static, no credentials needed
                                          └── OPA/Conftest ← static, no credentials needed

Enhanced pipeline (what we add):
  ContextBuilder → CodeGenerator → GenerationValidator → Self-Correction
                                          │
                                          ├── terraform validate (FV-i) ← UNCHANGED
                                          ├── PlanValidator (FV-ii) ← NEW
                                          │     ├── StateResolver: configures project for plan
                                          │     ├── PlanRunner: uses terragrunt native commands
                                          │     │     ├── Per-stack: terragrunt plan (in stack dir)
                                          │     │     └── Full project: terragrunt run --all -- plan
                                          │     └── Parses plan JSON → Violation objects
                                          ├── Checkov ← UNCHANGED
                                          └── OPA/Conftest ← UNCHANGED
```

### Key Insight: Use Terragrunt v0.99+ Native Commands

Terragrunt v0.99.5 (installed) provides everything needed for secure plan validation natively:

| Terragrunt Capability | How We Use It |
|----------------------|---------------|
| `terragrunt plan` (per-stack) | Validate a single generated stack in its directory |
| `terragrunt run --all -- plan` | Validate entire generated project (DAG-aware) |
| `--iam-assume-role` | Temporary credentials via IAM role assumption |
| `--iam-assume-role-duration` | Short-lived session (15 min for validation) |
| `--auth-provider-cmd` | Dynamic credential provider (SSO, vault, etc.) |
| `--json-out-dir` | Structured JSON plan output for parsing |
| `--non-interactive` | No prompts during validation |
| `--provider-cache` | Avoid re-downloading providers per stack |
| `--graph` | Respect dependency ordering during multi-stack plan |
| `terragrunt find` | Discover all stacks in generated project |
| `terragrunt validate` | Per-stack schema validation (FV-i) |
| `--filter` | Validate specific stacks only |

### Execution Approaches

**Approach A: Per-Stack Validation (during generation loop)**

```bash
# For each generated stack, run plan in its directory
# Uses terragrunt which handles: backend config, provider generation, init
cd stacks/foundation/network/vpc/
terragrunt plan \
  --non-interactive \
  --iam-assume-role arn:aws:iam::ACCOUNT:role/thothctl-plan-readonly \
  --iam-assume-role-duration 900 \
  --provider-cache \
  --json-out-dir /tmp/thothctl-plan-out/
```

**Approach B: Full Project Validation (after all stacks generated)**

```bash
# Validate entire project at once, respecting DAG dependency order
cd /path/to/generated/project/
terragrunt run --all -- plan \
  --non-interactive \
  --iam-assume-role arn:aws:iam::ACCOUNT:role/thothctl-plan-readonly \
  --iam-assume-role-duration 900 \
  --provider-cache \
  --graph \
  --json-out-dir /tmp/thothctl-plan-out/
```

**Approach C: For plain Terraform (non-terragrunt) projects**

Follows the existing `DriftDetectionService._run_plan()` pattern:
```python
subprocess.run([self.tftool, "init", "-input=false"], cwd=directory, ...)
subprocess.run([self.tftool, "plan", "-json", "-lock=false", "-input=false"], ...)
```

### Credential Model: Terragrunt-Native Temporal Credentials

Instead of building a custom credential broker, we leverage **terragrunt's built-in `--iam-assume-role`**:

```
User's ambient credentials (env/profile/SSO/IMDS)
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ terragrunt --iam-assume-role $ROLE --iam-assume-role-duration 900 │
│                                                               │
│ Terragrunt internally:                                        │
│ 1. Uses ambient creds to call STS AssumeRole                 │
│ 2. Gets temporary session with 15-min TTL                    │
│ 3. Passes temp creds to terraform/tofu subprocess            │
│ 4. Session dies after plan completes                         │
│                                                               │
│ The assumed role should have:                                 │
│ - Read-only access to describe resources (for plan)          │
│ - Read access to state bucket (for stateful mode)            │
│ - NO write permissions                                        │
└─────────────────────────────────────────────────────────────┘
```

**Or with `--auth-provider-cmd`** for dynamic credentials (SSO, Vault, custom):
```bash
terragrunt plan \
  --auth-provider-cmd "aws sts assume-role --role-arn $ROLE --query Credentials" \
  --non-interactive
```

This means **ThothCTL does NOT need to implement STS calls or credential brokering** — terragrunt handles it all. We just pass through the configuration.

---

## Components

### 1. StateResolver (`services/generate/intent/state_resolver.py`)

**Responsibility**: Determine whether generated code can be validated in-place (if written to the project) or needs a temp workspace with backend configuration.

```python
class StateResolver:
    """Resolves the execution context for plan validation.
    
    Two modes:
    A) In-place validation (terragrunt projects):
       - Code is written to its target location in the project
       - terragrunt plan runs DIRECTLY (it handles backend, provider, init)
       - No backend_override needed — terragrunt does everything via root.hcl
    
    B) Temp workspace validation (plain terraform):
       - Code validated in temp dir (existing pattern)
       - Backend config extracted from project and injected
       - Follows DriftDetectionService pattern
    """
    
    def resolve(self, project_dir: str, project_type: str,
                stack_path: str = None) -> PlanContext:
        """Determine plan execution context.
        
        For terragrunt projects:
        - Returns PlanContext(mode="terragrunt", work_dir=project_dir/stack_path)
        - Terragrunt handles everything: backend, provider, init, credentials
        
        For terraform projects:
        - Returns PlanContext(mode="terraform", work_dir=temp_dir)
        - Backend config must be injected into temp workspace
        """
    
    def write_generated_files_to_project(
        self, files: List[GeneratedFile], project_dir: str
    ) -> List[Path]:
        """Write generated files to their target location for in-place plan.
        
        For terragrunt: writes to project_dir/stack_path/*.tf
        Returns list of written paths (for rollback on failure).
        """
    
    def rollback_written_files(self, written_paths: List[Path]) -> None:
        """Remove files that were written for in-place validation.
        
        Called when plan fails and user hasn't --apply'd.
        """
```

**Why terragrunt projects DON'T need a temp workspace**:

In terragrunt, the `terragrunt.hcl` + `root.hcl` handle:
- Provider configuration (via `generate "provider"`)
- Backend configuration (via `remote_state {}`)
- Dependency resolution (via `dependency {}`)
- Init + provider download (auto-init)

So the most natural way to validate is to write the generated `.tf` files to their target location and run `terragrunt plan` there. If validation fails or the user hasn't `--apply`'d, we rollback (remove) the files.

---

### 2. PlanRunner (`services/generate/intent/plan_runner.py`)

**Responsibility**: Execute plan using the appropriate tool based on project type.

```python
class PlanRunner:
    """Runs plan validation using terragrunt (v0.99+) or terraform/tofu.
    
    For terragrunt projects (v0.99+):
    - Per-stack: terragrunt plan --non-interactive --json-out-dir
    - Full project: terragrunt run --all -- plan --graph --json-out-dir
    - Credentials: --iam-assume-role (if configured in .thothcf.toml)
    - Provider cache: --provider-cache (automatic)
    
    For plain terraform projects:
    - Follows DriftDetectionService._run_plan() pattern
    - terraform init + terraform plan -json -lock=false
    """
    
    def __init__(self, project_type: str = "terraform-terragrunt",
                 tftool: str = "tofu"):
        self.project_type = project_type
        self.tftool = tftool  # For plain terraform: terraform or tofu
    
    def run_plan_per_stack(
        self, stack_dir: str, config: Dict
    ) -> PlanResult:
        """Validate a single stack.
        
        For terragrunt: runs `terragrunt plan` in the stack directory.
        For terraform: runs `terraform plan` in the workspace.
        """
    
    def run_plan_all(
        self, project_dir: str, config: Dict
    ) -> PlanResult:
        """Validate entire project (all stacks, DAG-aware).
        
        For terragrunt: runs `terragrunt run --all -- plan --graph`
        For terraform: runs `terraform plan` on the single root module
        """
    
    def run_plan_filtered(
        self, project_dir: str, stack_paths: List[str], config: Dict
    ) -> PlanResult:
        """Validate specific stacks only.
        
        Uses terragrunt --filter to target specific stacks.
        """
```

**Terragrunt plan execution** (per-stack):

```python
def _run_terragrunt_plan_stack(self, stack_dir: str, config: Dict) -> PlanResult:
    """Run terragrunt plan in a single stack directory."""
    cmd = ["terragrunt", "plan"]
    
    # Always non-interactive for automation
    cmd.append("--non-interactive")
    
    # Provider caching (avoids re-downloading per stack)
    cmd.append("--provider-cache")
    
    # JSON output for structured parsing
    json_out = tempfile.mkdtemp(prefix="thothctl_plan_")
    cmd.extend(["--json-out-dir", json_out])
    
    # Temporal credentials via IAM role assumption (if configured)
    iam_role = config.get("iam_assume_role")
    if iam_role:
        cmd.extend(["--iam-assume-role", iam_role])
        cmd.extend(["--iam-assume-role-duration", 
                    str(config.get("session_duration", 900))])
        session_name = f"thothctl-plan-{int(time.time())}"
        cmd.extend(["--iam-assume-role-session-name", session_name])
    
    # Auth provider command (alternative to IAM role)
    auth_cmd = config.get("auth_provider_cmd")
    if auth_cmd:
        cmd.extend(["--auth-provider-cmd", auth_cmd])
    
    # No color for parsing
    cmd.append("--no-color")
    
    result = subprocess.run(
        cmd,
        cwd=stack_dir,
        capture_output=True,
        text=True,
        timeout=config.get("plan_timeout", 120),
    )
    
    # Parse JSON plan output
    violations = self._parse_plan_json_dir(json_out)
    
    # Cleanup
    shutil.rmtree(json_out, ignore_errors=True)
    
    return PlanResult(
        violations=violations,
        plan_succeeded=(result.returncode == 0),
        execution_time_seconds=...,
        skipped=False,
    )
```

**Terragrunt plan execution** (full project, DAG-aware):

```python
def _run_terragrunt_plan_all(self, project_dir: str, config: Dict) -> PlanResult:
    """Run terragrunt plan on all stacks respecting DAG order."""
    cmd = ["terragrunt", "run", "--all", "--", "plan"]
    
    cmd.append("--non-interactive")
    cmd.append("--provider-cache")
    cmd.append("--graph")  # Respect DAG order
    
    json_out = tempfile.mkdtemp(prefix="thothctl_plan_all_")
    cmd.extend(["--json-out-dir", json_out])
    
    # Temporal credentials
    iam_role = config.get("iam_assume_role")
    if iam_role:
        cmd.extend(["--iam-assume-role", iam_role])
        cmd.extend(["--iam-assume-role-duration", 
                    str(config.get("session_duration", 900))])
    
    auth_cmd = config.get("auth_provider_cmd")
    if auth_cmd:
        cmd.extend(["--auth-provider-cmd", auth_cmd])
    
    cmd.append("--no-color")
    
    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=config.get("plan_timeout_all", 600),  # Longer for full project
    )
    
    violations = self._parse_plan_json_dir(json_out)
    shutil.rmtree(json_out, ignore_errors=True)
    
    return PlanResult(
        violations=violations,
        plan_succeeded=(result.returncode == 0),
        skipped=False,
    )
```

**For plain terraform** (follows drift service):

```python
def _run_terraform_plan(self, work_dir: str, config: Dict) -> PlanResult:
    """Run terraform/tofu plan (non-terragrunt projects)."""
    tf_cmd = self.tftool
    
    # Init
    subprocess.run(
        [tf_cmd, "init", "-input=false"],
        cwd=work_dir, capture_output=True, timeout=config.get("init_timeout", 60),
    )
    
    # Plan
    result = subprocess.run(
        [tf_cmd, "plan", "-input=false", "-json", "-lock=false",
         "-detailed-exitcode", "-no-color"],
        cwd=work_dir, capture_output=True, text=True,
        timeout=config.get("plan_timeout", 120),
    )
    
    violations = self._parse_streaming_json(result.stdout)
    return PlanResult(violations=violations, plan_succeeded=(result.returncode != 1))
```

---

### 3. PlanValidator (`services/generate/intent/plan_validator.py`)

**Responsibility**: Orchestrate the plan validation lifecycle.

```python
class PlanValidator:
    """Orchestrates plan validation using project-appropriate tool.
    
    Decision tree:
    1. Is plan validation enabled? (config) → if no, return []
    2. What project type? → terragrunt or terraform
    3. What scope? → per-stack (during generation) or full-project (after all stacks)
    4. Execute plan using the appropriate runner
    5. Parse results → List[Violation]
    
    For terragrunt (v0.99+):
    - Uses native terragrunt commands (plan, run --all)
    - Credentials via --iam-assume-role or --auth-provider-cmd
    - Provider caching via --provider-cache
    - JSON output via --json-out-dir
    
    For terraform:
    - Uses terraform/tofu directly
    - Follows DriftDetectionService pattern
    """
    
    def __init__(self, config: Dict, project_type: str = "terraform-terragrunt",
                 tftool: str = "tofu"):
        self.config = config
        self.state_resolver = StateResolver()
        self.plan_runner = PlanRunner(project_type=project_type, tftool=tftool)
    
    def validate_per_stack(
        self,
        files: List[GeneratedFile],
        project_dir: str,
        stack_path: str,
    ) -> List[Violation]:
        """Validate a single generated stack.
        
        For terragrunt:
        1. Write generated .tf files to project_dir/stack_path/
        2. Run `terragrunt plan` in that directory
        3. Parse results
        4. Rollback written files (unless --apply)
        
        For terraform:
        1. Write to temp dir (existing pattern)
        2. Run terraform plan
        3. Parse results
        4. Cleanup temp dir
        """
    
    def validate_full_project(
        self,
        project_dir: str,
    ) -> List[Violation]:
        """Validate entire generated project (all stacks).
        
        For terragrunt:
        Runs `terragrunt run --all -- plan --graph --json-out-dir`
        from the project root. DAG-aware: validates in dependency order.
        
        For terraform:
        Runs terraform plan on the root module.
        """
    
    def discover_stacks(self, project_dir: str) -> List[str]:
        """Find all stacks in the project using terragrunt find.
        
        Uses: terragrunt find --format json --working-dir project_dir
        Returns list of stack paths.
        """
```

---

## Validation Modes

Configured via `.thothcf.toml` `[generation.plan]`:

| Mode | Tool | Scope | Credentials | What it catches |
|------|------|-------|-------------|-----------------|
| `disabled` (default) | None | — | None | Nothing (plan not run) |
| `per-stack` | `terragrunt plan` | Single stack | IAM role / ambient | Type errors, invalid attrs per stack |
| `full-project` | `terragrunt run --all -- plan --graph` | All stacks | IAM role / ambient | Cross-stack deps + all per-stack errors |
| `terraform` | `terraform plan` | Root module | Ambient | For non-terragrunt projects |

### Mode: `per-stack` (recommended for generation loop)

During the self-correction loop, each generated stack is validated independently:

```bash
# ThothCTL writes generated .tf files to stacks/network/vpc/
# Then runs:
terragrunt plan \
  --non-interactive \
  --provider-cache \
  --iam-assume-role arn:aws:iam::123456789012:role/thothctl-plan-readonly \
  --iam-assume-role-duration 900 \
  --working-dir stacks/foundation/network/vpc/
```

Terragrunt handles:
- Backend resolution from root.hcl (state key auto-resolved from path)
- Provider generation (from root.hcl `generate "provider"` block)
- Auto-init (downloads providers, configures backend)
- Credential assumption (from `--iam-assume-role`)

### Mode: `full-project` (recommended for final validation)

After all stacks are generated, validate the entire project respecting dependency order:

```bash
# From project root:
terragrunt run --all -- plan \
  --non-interactive \
  --provider-cache \
  --graph \
  --iam-assume-role arn:aws:iam::123456789012:role/thothctl-plan-readonly \
  --iam-assume-role-duration 900 \
  --json-out-dir .thothctl/plan-output/
```

This catches:
- Cross-stack dependency issues (stack B references stack A's output)
- Global conflicts (duplicate resource names across stacks)
- Full DAG validation (cycles, missing deps)

### Mode: `terraform` (for non-terragrunt projects)

For plain terraform projects without terragrunt, follows the existing DriftDetectionService pattern:

```python
subprocess.run([tftool, "init", "-input=false"], cwd=work_dir)
subprocess.run([tftool, "plan", "-json", "-lock=false", "-input=false"], cwd=work_dir)
```

---

## Terragrunt v0.99+ Native Integration

### Why Native Terragrunt Commands (Not terraform directly)

In terragrunt projects, running `terraform plan` directly in a temp workspace requires reconstructing everything that terragrunt does:
- Resolve `include` chains
- Generate provider blocks
- Configure backend with path-relative keys
- Resolve `dependency {}` outputs
- Handle `inputs = {}`

This is fragile and duplicates terragrunt's logic. Instead, we **use terragrunt directly** — it already does all of this correctly.

### Per-Stack Validation (During Generation Loop)

When generating stacks one-by-one in composition mode:

```python
for stack in ordered_stacks:
    # 1. Generate code for this stack
    stack_files = generator.generate(stack.intent, ...)
    
    # 2. Write generated .tf files to their target location
    target_dir = Path(project_dir) / stack.path
    written_files = state_resolver.write_generated_files(stack_files, target_dir)
    
    # 3. Run terragrunt plan IN the stack directory (terragrunt handles everything)
    plan_result = plan_runner.run_plan_per_stack(
        stack_dir=str(target_dir), config=plan_config
    )
    
    # 4. If plan fails → feed violations to self-correction
    if plan_result.violations:
        # Remove bad files, fix via AI, rewrite, re-plan
        state_resolver.rollback_written_files(written_files)
        stack_files = generator.fix(stack_files, plan_result.violations, context)
        # ... loop
    
    # 5. If plan passes → keep files (or rollback if --dry-run)
    if not apply:
        state_resolver.rollback_written_files(written_files)
```

### Full Project Validation (After All Stacks Generated)

After all stacks are generated and written:

```python
# Validate entire project respecting DAG (catches cross-stack issues)
plan_result = plan_runner.run_plan_all(
    project_dir=project_dir, config=plan_config
)

# This catches:
# - Stack B referencing Stack A output that doesn't exist
# - Naming conflicts across stacks
# - DAG cycles from incorrect dependency declarations
```

### Stack Discovery

Use `terragrunt find` to discover all stacks:

```python
def discover_stacks(self, project_dir: str) -> List[str]:
    """Find all terragrunt units using native command."""
    result = subprocess.run(
        ["terragrunt", "find", "--format", "json", "--working-dir", project_dir],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        return json.loads(result.stdout)
    return []
```

### Filtered Validation

Validate only specific stacks (useful when generating incrementally):

```python
def validate_filtered(self, project_dir: str, stack_filter: str) -> PlanResult:
    """Validate specific stacks using terragrunt filter."""
    cmd = [
        "terragrunt", "run", "--all", "--", "plan",
        "--non-interactive", "--provider-cache", "--graph",
        "--filter", stack_filter,  # e.g., "stacks/foundation/**"
        "--working-dir", project_dir,
    ]
    # ... execute ...
```

### Credential Flow with Terragrunt

Terragrunt v0.99+ provides three credential mechanisms (all built-in, no custom code needed):

**Option 1: IAM Role Assumption (recommended for validation)**

```toml
# .thothcf.toml
[generation.plan]
iam_assume_role = "arn:aws:iam::123456789012:role/thothctl-plan-readonly"
session_duration = 900  # 15 min
```

Translates to:
```bash
terragrunt plan --iam-assume-role $ROLE --iam-assume-role-duration 900
```

The assumed role should have a **read-only policy** — terragrunt handles the STS call internally.

**Option 2: Auth Provider Command (for SSO/Vault/custom)**

```toml
# .thothcf.toml
[generation.plan]
auth_provider_cmd = "aws sts assume-role --role-arn arn:aws:iam::123456789012:role/plan-ro --output json"
```

Translates to:
```bash
terragrunt plan --auth-provider-cmd "aws sts assume-role ..."
```

**Option 3: Ambient credentials (simplest)**

```toml
# .thothcf.toml  
[generation.plan]
plan_validation = "per-stack"
# No iam_assume_role or auth_provider_cmd → uses ambient credentials
# Same as: user has run `aws sso login` or has env vars set
```

### Handling Cross-Stack Dependencies

When stack B depends on stack A's outputs (via `dependency {}` in terragrunt.hcl):

- **If stack A exists (incremental)**: terragrunt reads A's state, plan succeeds
- **If stack A was just generated (full project)**: use `terragrunt run --all -- plan --graph` which validates in dependency order, applying A first conceptually
- **If dependency cannot be resolved**: terragrunt uses `mock_outputs` from the dependency block — this is why the assembler generates `mock_outputs_merge_strategy_with_state = "shallow"` in terragrunt.hcl files

---

## Security Model

### Trust Boundary

```
Trusted (user's environment):
  ├── AWS credentials (env vars, profile, SSO, IRSA)
  ├── Terragrunt binary (v0.99+) — handles credential assumption internally
  ├── .thothcf.toml configuration (role ARN, session params)
  ├── Project directory (root.hcl, terragrunt.hcl, backend config)
  └── terraform/tofu binary (for non-terragrunt projects)

Untrusted (AI-generated):
  ├── Generated .tf files (resource definitions)
  └── Resource attribute values
```

### Credential Isolation (Terragrunt-Native)

```
User's ambient credentials
       │
       ▼
terragrunt --iam-assume-role $PLAN_ROLE --iam-assume-role-duration 900
       │
       ▼ (terragrunt calls STS internally)
       │
Temporary session (15 min, read-only by role policy)
       │
       ▼ (passed to terraform/tofu subprocess by terragrunt)
       │
terraform plan (uses temp session to call provider APIs)
       │
       ▼ (session expires after plan completes)
       │
Results parsed → Violation text only → fed to AI
```

**Key security properties**:
1. The assumed role has read-only policy (DenyAllMutations statement)
2. Terragrunt handles STS internally — ThothCTL never touches raw credentials
3. Session duration is minimized (900s = 15 min)
4. Only plan error messages are fed to the AI (no attribute values, no ARNs)
5. For in-place validation: generated files are rolled back if plan fails

### Security Controls

| Control | Implementation | Mechanism |
|---------|---------------|-----------|
| Temporal credentials | `--iam-assume-role` with 15-min session | Terragrunt native |
| Read-only enforcement | IAM role policy with explicit Deny on mutations | AWS IAM |
| No state locking | terragrunt plan doesn't acquire locks for read | Terragrunt default (plan is read-only) |
| No apply possible | Only `plan` command, never `apply` | ThothCTL never calls apply |
| Information boundary | Only error messages reach AI, not state/resource details | Violation parsing logic |
| Timeout protection | subprocess timeout kills stuck plan | Python subprocess.run |
| Rollback on failure | Generated files removed from project if plan fails | StateResolver.rollback |
| Provider isolation | `--provider-cache` shared, but plugins are from official registry | Terragrunt provider cache |

### What the AI Sees (Self-Correction Prompt)

Plan violation fed back to AI:

```
## PLAN ERRORS (2 violations):

1. [HIGH] TF_PLAN — main.tf:12
   Resource: aws_instance.web  
   Error: "t3.nano" is not a valid instance type for "us-east-1"
   Fix: Use a valid instance type (t3.micro, t3.small, m5.large)

2. [HIGH] TF_PLAN — main.tf:25
   Resource: aws_security_group_rule.ingress
   Error: "security_group_id" is required when "source_security_group_id" is not set
   Fix: Add security_group_id referencing the parent security group
```

**NOT included** (security boundary):
- Existing resource IDs or ARNs from state
- Account number, VPC IDs, subnet IDs
- State file contents or resource counts
- Credential values or role ARNs
- Other stacks' resource details

---

## Configuration

### `.thothcf.toml` Additions

```toml
[generation.plan]
# Plan validation mode: "disabled" (default) | "per-stack" | "full-project" | "terraform"
#   disabled      — no plan execution (current behavior, safest)
#   per-stack     — validate each stack individually via terragrunt plan
#   full-project  — validate all stacks via terragrunt run --all -- plan --graph
#   terraform     — for non-terragrunt projects, use terraform/tofu plan directly
plan_validation = "disabled"

# Terraform/tofu binary selection (for "terraform" mode only)
# Empty = auto-detect (prefers tofu, falls back to terraform)
tftool = ""

# Timeout for per-stack plan (seconds)
plan_timeout = 120

# Timeout for full-project plan (seconds) — longer because it runs all stacks
plan_timeout_all = 600

# Maximum self-correction iterations when plan validation is active
max_plan_iterations = 10

# -------------------------------------------------------------------
# Terragrunt Credential Configuration (native --iam-assume-role)
# -------------------------------------------------------------------

# IAM role to assume for plan validation (optional)
# Terragrunt handles the STS call internally via --iam-assume-role
# The role should have read-only access to:
#   - State bucket (s3:GetObject, s3:ListBucket)
#   - Provider APIs (ec2:Describe*, iam:Get*, rds:Describe*, etc.)
#   - NO write permissions
iam_assume_role = ""

# Session duration for the assumed role (seconds, min 900)
session_duration = 900

# Session name (auto-generated if empty)
session_name = ""

# Alternative: auth provider command (for SSO, Vault, custom auth)
# Terragrunt handles this via --auth-provider-cmd
# Example: "aws sts assume-role --role-arn arn:aws:iam::123:role/plan-ro --output json"
auth_provider_cmd = ""

# -------------------------------------------------------------------
# Provider Caching
# -------------------------------------------------------------------

# Enable terragrunt provider cache (avoids re-downloading per stack)
# Uses terragrunt's built-in --provider-cache
provider_cache = true

# Provider cache directory (auto-managed by terragrunt if empty)
provider_cache_dir = ""

# -------------------------------------------------------------------
# Filtering (for incremental generation)
# -------------------------------------------------------------------

# Stack filter pattern for partial validation
# Uses terragrunt's --filter syntax
# Example: "stacks/foundation/**" to validate only foundation stacks
stack_filter = ""
```

### Environment Variable Overrides

| Variable | Overrides | Example |
|----------|-----------|---------|
| `THOTH_PLAN_VALIDATION` | `[generation.plan].plan_validation` | `per-stack` |
| `THOTH_PLAN_IAM_ROLE` | `[generation.plan].iam_assume_role` | `arn:aws:iam::123:role/plan-ro` |
| `THOTH_PLAN_TIMEOUT` | `[generation.plan].plan_timeout` | `180` |
| `TG_IAM_ASSUME_ROLE` | Same as iam_assume_role (terragrunt native) | (direct terragrunt env var) |
| `TG_AUTH_PROVIDER_CMD` | Same as auth_provider_cmd (terragrunt native) | (direct terragrunt env var) |

### Recommended Read-Only IAM Policy for Plan Validation Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPlanReadOperations",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity",
        "s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation",
        "dynamodb:GetItem", "dynamodb:DescribeTable",
        "ec2:Describe*",
        "iam:Get*", "iam:List*",
        "s3:GetBucket*", "s3:GetEncryptionConfiguration",
        "rds:Describe*",
        "lambda:Get*", "lambda:List*",
        "ecs:Describe*", "ecs:List*",
        "eks:Describe*", "eks:List*",
        "kms:Describe*", "kms:List*",
        "elasticache:Describe*",
        "route53:Get*", "route53:List*",
        "tag:GetResources"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyAllMutations",
      "Effect": "Deny",
      "Action": [
        "s3:PutObject", "s3:DeleteObject",
        "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem",
        "ec2:RunInstances", "ec2:TerminateInstances", "ec2:Create*", "ec2:Delete*",
        "iam:Create*", "iam:Delete*", "iam:Update*", "iam:Put*", "iam:Attach*",
        "rds:Create*", "rds:Delete*", "rds:Modify*",
        "lambda:Create*", "lambda:Delete*", "lambda:Update*"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## CLI Changes

### New flags on `thothctl generate iac`

```bash
# Enable per-stack plan validation
thothctl generate iac --intent "Create VPC with subnets" --plan-validation per-stack

# Enable full-project plan validation (after all stacks generated)
thothctl generate iac --intent "Full microservices platform" \
  --composition full \
  --plan-validation full-project

# Use IAM role for temporal credentials
thothctl generate iac --intent "..." \
  --plan-validation per-stack \
  --plan-iam-role arn:aws:iam::123456789012:role/thothctl-plan-readonly

# Use terraform (non-terragrunt project)
thothctl generate iac --intent "..." --plan-validation terraform --tftool terraform

# Override iteration budget
thothctl generate iac --intent "..." --plan-validation per-stack --max-iterations 10

# Filter specific stacks for validation
thothctl generate iac --intent "..." \
  --plan-validation per-stack \
  --plan-filter "stacks/foundation/**"
```

### New standalone command: `thothctl generate plan-check`

```bash
# Validate already-generated project via terragrunt plan
thothctl generate plan-check --directory ./my-project/ --mode full-project

# Validate a specific stack
thothctl generate plan-check --directory ./my-project/ \
  --stack-path stacks/foundation/network/vpc

# With IAM role for temporal credentials
thothctl generate plan-check --directory ./my-project/ \
  --mode full-project \
  --iam-role arn:aws:iam::123:role/plan-readonly

# Discover all stacks first, then validate
thothctl generate plan-check --directory ./my-project/ --discover
```

---

## Implementation Plan

### Phase A: Core Components (Days 1-6) ✅

| # | Task | Effort | Status |
|---|------|--------|--------|
| A.1 | Data models: `StateConfig`, `PlanResult`, `PlanContext`, `PlanMode` in `models.py` | 0.5d | ✅ |
| A.2 | `StateResolver` — determine plan execution context | 1.5d | ✅ |
| A.3 | `StateResolver` — write/rollback generated files for in-place validation | 1d | ✅ |
| A.4 | `PlanRunner` — terragrunt per-stack execution | 1.5d | ✅ |
| A.5 | `PlanRunner` — terragrunt full-project execution | 1d | ✅ |
| A.6 | `PlanRunner` — terraform/tofu execution (non-terragrunt) | 0.5d | ✅ |

### Phase B: Integration (Days 7-10) ✅

| # | Task | Effort | Status |
|---|------|--------|--------|
| B.1 | `PlanValidator` — orchestrator (routes to correct runner based on project type) | 1d | ✅ |
| B.2 | Integrate into `GenerationValidator.validate()` | 0.5d | ✅ |
| B.3 | Integrate into `IntentToIaCService` — per-stack in composition loop | 1d | ✅ |
| B.4 | Self-correction prompt format for plan violations | 0.5d | ✅ |
| B.5 | Convergence detection (stagnation after 3 non-improvements) | 0.5d | ✅ |
| B.6 | Per-stack plan retry loop (max 3 attempts per stack) | 0.5d | ✅ |

### Phase C: CLI & Configuration (Days 11-12) ✅

| # | Task | Effort | Status |
|---|------|--------|--------|
| C.1 | CLI flags: `--plan-validation`, `--plan-iam-role`, `--plan-profile`, `--plan-filter` | 1d | ✅ |
| C.2 | Config loading from `.thothcf.toml` [generation.plan] with env var overrides | 0.5d | ✅ |
| C.3 | AWS profile support via `--plan-profile` and `THOTH_PLAN_AWS_PROFILE` | 0.5d | ✅ |

### Phase D: Testing & Documentation (Days 13-14) ✅

| # | Task | Effort | Status |
|---|------|--------|--------|
| D.1 | Unit tests: StateResolver, PlanRunner, PlanValidator (32 tests, all passing) | 1d | ✅ |
| D.2 | Integration test: Bedrock + terragrunt composition with plan validation | 0.5d | ✅ Manual (labvel-devsecops profile) |
| D.3 | Spec document: `docs/framework/specs/phase1.10_plan_validation.md` | 0.5d | ✅ |

### Additional Fixes Delivered (from 7-pass analysis)

| Fix | Impact |
|-----|--------|
| Bedrock provider JSON repair (`_repair_json_strings`) | Per-stack code generation now works with Bedrock |
| `self` in `@staticmethod` crash in CodeGenerator + IntentDecomposer | Runtime crash fixed |
| Diagram writes in `--dry-run` mode | `--dry-run` contract respected |
| Strict file separation enforcement (variables.tf / main.tf / outputs.tf) | Clean stack structure |
| Circular dependency crash (ValueError unhandled) | Graceful error message |
| Context shows 0 tokens in CLI | Now shows correct estimate |

---

## File Structure

```
src/thothctl/services/generate/intent/
├── __init__.py                 # existing
├── intent_service.py           # MODIFIED: load plan config, pass to validator
├── validator.py                # MODIFIED: call plan_validator between validate and checkov
├── models.py                   # MODIFIED: add StateConfig, PlanResult
├── plan_validator.py           # NEW: orchestrates state_resolver + plan_runner
├── state_resolver.py           # NEW: reads project backend config
├── plan_runner.py              # NEW: executes plan (follows drift_service pattern)
├── code_generator.py           # unchanged
├── context_builder.py          # unchanged  
├── prompts.py                  # MODIFIED: add plan violation prompt format
├── scaffold_loader.py          # unchanged
├── intent_decomposer.py        # unchanged
├── project_assembler.py        # unchanged
└── composition_models.py       # unchanged
```

---

## Graceful Degradation

The entire plan validation layer is designed to **skip, not crash**:

```
Plan validation mode = "per-stack" (terragrunt):
  ├── No terragrunt binary found? → SKIP, return []
  ├── No terragrunt.hcl in stack dir? → SKIP this stack
  ├── terragrunt plan timeout? → SKIP, return []
  ├── IAM role assumption fails? → Try with ambient credentials
  │     └── Ambient credentials also fail? → SKIP, return []
  ├── Provider download fails (no network)? → SKIP, return []
  ├── Dependency output unavailable? → SKIP stack (mock_outputs insufficient)
  └── All works? → return List[Violation]

Plan validation mode = "full-project" (terragrunt):
  ├── All of above, plus:
  ├── One stack fails → others still validate (terragrunt --queue-ignore-errors)
  ├── DAG cycle detected? → Return cycle as violation
  └── All stacks pass? → return combined List[Violation]

Plan validation mode = "terraform" (non-terragrunt):
  ├── No terraform/tofu binary? → SKIP, return []
  ├── terraform init fails? → SKIP, return []
  ├── terraform plan timeout? → SKIP, return []
  └── All works? → return List[Violation]
```

---

## Dependency on Existing ThothCTL Capabilities

| Existing Component | How Plan Validation Uses It |
|-------------------|---------------------------|
| `DriftDetectionService._run_plan()` | **Pattern reference** for terraform mode subprocess execution |
| `DriftDetectionService` tftool pattern | Same binary detection and selection (tofu vs terraform) |
| `GenerationValidator._validate_terraform()` | Existing terraform validate (FV-i) runs first; plan runs after it passes |
| `GenerationValidator._create_temp_workspace()` | Used for terraform mode; terragrunt mode writes to real project dir |
| `.thothcf.toml` config loading | Plan config loaded from same file, same mechanism |
| `Violation` model | Plan errors use the same model as checkov/opa violations |
| Self-correction loop in `intent_service.py` | Plan violations feed into the same loop (no new correction mechanism) |
| `ProjectAssembler` (composition) | Generates terragrunt.hcl with `mock_outputs` — critical for plan to work |
| `scaffold_loader.py` | Scaffold's root.hcl is what terragrunt uses for backend/provider |
| `IntentDecomposer.topological_order()` | Stacks validated in order; dependency info used for per-stack plan |

---

## Terragrunt v0.99+ Commands Reference

Commands used in this spec:

| Command | Purpose | Key Flags |
|---------|---------|-----------|
| `terragrunt plan` | Plan single stack | `--non-interactive`, `--iam-assume-role`, `--provider-cache` |
| `terragrunt run --all -- plan` | Plan all stacks (DAG-aware) | `--graph`, `--json-out-dir`, `--parallelism` |
| `terragrunt validate` | Schema validation (FV-i) per stack | `--non-interactive` |
| `terragrunt find` | Discover all stacks | `--format json`, `--dag` |
| `terragrunt find --filter "..."` | Discover filtered stacks | `--filter "path:stacks/foundation/**"` |
| `terragrunt run --all -- plan --filter "..."` | Plan filtered stacks | Combines --all with --filter |

---

## Open Questions

1. **In-place validation rollback atomicity**: If ThothCTL writes generated .tf files to the project and plan fails mid-execution (timeout), the rollback must handle partial state. Solution: track all written file paths, rollback in `finally` block.

2. **Concurrent usage**: If user runs `thothctl generate iac` while another `terragrunt plan` is running, could there be conflicts? Mitigation: write to a branch or temp git stash; or warn if working tree is dirty.

3. **Provider cache warming**: First run downloads providers (~100MB for AWS provider). Solution: use terragrunt's `--provider-cache` which shares across stacks automatically.

4. **CI/CD without role assumption**: In CI environments where credentials come from OIDC/IRSA, `--iam-assume-role` isn't needed (ambient creds are already scoped). Detect this and skip role assumption.

5. **Plan output size**: For large projects, `terragrunt run --all -- plan` output can be huge. Limit JSON parsing to error/warning diagnostics only (skip "resource will be created" info messages).

6. **Cross-stack dependency resolution**: The `ProjectAssembler` already generates `mock_outputs` blocks. For plan validation, terragrunt will use these mocks when the real dependency output isn't available. This should work for most cases. When it doesn't (complex output structures), skip that stack's plan.
