# Implementation Plan: DevSecOps Workflow Abstraction

## Objective

Provide two abstraction layers over the existing DevSecOps SDLC stages:

1. **Layer 1 (CLI)**: `thothctl workflow devsecops` — composite command that orchestrates existing commands per phase
2. **Layer 2 (Skill)**: Kiro CLI skill that teaches AI agents to drive the full SDLC via MCP

Both layers consume the same underlying services (`scan`, `check`, `inventory`, `document`) — no duplication.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User Entry Points                             │
├──────────────────────┬──────────────────────────────────────────────┤
│  Layer 1: CLI        │  Layer 2: AI Skill (Kiro CLI)                │
│                      │                                              │
│  thothctl workflow   │  kiro-cli chat --agent thoth                 │
│    devsecops         │  "prepare for production deployment"         │
│    --phase secure    │                                              │
│    --phase all       │  SKILL.md → decision logic → MCP calls       │
├──────────────────────┴──────────────────────────────────────────────┤
│                     MCP Server (thothctl mcp)                        │
├─────────────────────────────────────────────────────────────────────┤
│                     Workflow Service                                  │
│                     (orchestrates phases)                             │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┤
│  check   │  scan    │ inventory│ document │  check   │  generate    │
│  env     │  iac     │  iac     │  iac     │  iac     │  iac         │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┘
```

---

## Layer 1: CLI Workflow Command

### 1.1 File Structure

```
src/thothctl/
├── commands/
│   └── workflow/
│       ├── __init__.py
│       ├── cli.py                    # Click group (same pattern as scan/cli.py)
│       └── commands/
│           ├── __init__.py
│           └── devsecops.py          # thothctl workflow devsecops
│
├── services/
│   └── workflow/
│       ├── __init__.py
│       ├── models.py                 # Phase, StepResult, WorkflowResult dataclasses
│       ├── workflow_service.py       # Orchestrator: runs phases in sequence
│       ├── phases/
│       │   ├── __init__.py
│       │   ├── base.py              # Abstract PhaseExecutor
│       │   ├── plan.py              # Phase 1: cost-analysis, init
│       │   ├── develop.py           # Phase 2: check env, check project, document
│       │   ├── build.py             # Phase 3: inventory, versions, SBOM
│       │   ├── test.py              # Phase 4: tfplan validation, blast-radius
│       │   ├── secure.py            # Phase 5: scan iac (checkov, trivy, opa)
│       │   ├── deploy.py            # Phase 6: enforcement hard, approval gates
│       │   └── monitor.py           # Phase 7: drift detection, dashboard
│       └── config.py                # Default phase configs, tool selections
```

### 1.2 Models (`services/workflow/models.py`)

```python
"""Data models for the DevSecOps workflow engine."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Phase(Enum):
    """DevSecOps SDLC phases."""
    PLAN = "plan"
    DEVELOP = "develop"
    BUILD = "build"
    TEST = "test"
    SECURE = "secure"
    DEPLOY = "deploy"
    MONITOR = "monitor"
    ALL = "all"
    PRE_DEPLOY = "pre-deploy"  # Composite: test + secure + blast-radius


class StepStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class StepResult:
    """Result of a single step within a phase."""
    name: str
    status: StepStatus
    command: str                     # The thothctl command that was run
    duration_seconds: float = 0.0
    summary: str = ""               # Human-readable summary
    report_path: Optional[str] = None
    findings_count: int = 0
    details: Dict = field(default_factory=dict)


@dataclass
class PhaseResult:
    """Result of executing an entire phase."""
    phase: Phase
    steps: List[StepResult] = field(default_factory=list)
    passed: bool = True
    gate_blocked: bool = False      # True if enforcement stopped the pipeline

    @property
    def total_findings(self) -> int:
        return sum(s.findings_count for s in self.steps)

    @property
    def duration_seconds(self) -> float:
        return sum(s.duration_seconds for s in self.steps)


@dataclass
class WorkflowResult:
    """Complete workflow execution result."""
    phases: List[PhaseResult] = field(default_factory=list)
    enforcement: str = "soft"       # soft | hard
    stopped_at: Optional[Phase] = None  # Phase where hard enforcement blocked

    @property
    def passed(self) -> bool:
        return all(p.passed for p in self.phases)

    @property
    def total_findings(self) -> int:
        return sum(p.total_findings for p in self.phases)
```

### 1.3 Phase Executor Pattern (`services/workflow/phases/base.py`)

```python
"""Abstract base for phase executors."""
from abc import ABC, abstractmethod
from typing import Dict, Optional
from ..models import PhaseResult, Phase


class PhaseExecutor(ABC):
    """Base class for SDLC phase executors."""

    @property
    @abstractmethod
    def phase(self) -> Phase:
        """Which phase this executor handles."""
        ...

    @abstractmethod
    def execute(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
    ) -> PhaseResult:
        """Run all steps in this phase. Returns PhaseResult."""
        ...

    @property
    def description(self) -> str:
        """Human-readable phase description for UI."""
        return f"Phase: {self.phase.value}"
```

### 1.4 Example Phase Implementation (`services/workflow/phases/secure.py`)

```python
"""Secure phase: security scanning, compliance, vulnerability detection."""
import time
from typing import Dict, Optional

from ....services.scan.scan_service import ScanService
from ..models import Phase, PhaseResult, StepResult, StepStatus
from .base import PhaseExecutor


class SecurePhaseExecutor(PhaseExecutor):
    """Phase 5: Security scanning with multi-tool pipeline."""

    phase = Phase.SECURE

    def execute(
        self,
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
    ) -> PhaseResult:
        options = options or {}
        result = PhaseResult(phase=self.phase)

        # Determine tools based on options or defaults
        tools = options.get("tools", ["checkov", "trivy", "opa"])
        enforcement = options.get("enforcement", "soft")
        policy_dir = options.get("policy_dir")

        scan_options = {}
        if policy_dir:
            scan_options["policy_dir"] = policy_dir

        # Execute scan service (reuse existing scan infrastructure)
        scan_service = ScanService()
        start = time.perf_counter()

        scan_results = scan_service.execute_scans(
            directory=directory,
            reports_dir=reports_dir,
            selected_tools=tools,
            options=scan_options,
        )

        duration = time.perf_counter() - start

        # Convert scan results to StepResults
        for tool_name, tool_result in scan_results.items():
            if tool_name == "summary":
                continue
            rd = tool_result.get("report_data", {})
            failed = rd.get("failed_count", 0) + rd.get("error_count", 0)
            status = StepStatus.PASSED if failed == 0 else StepStatus.FAILED

            result.steps.append(StepResult(
                name=f"scan-{tool_name}",
                status=status,
                command=f"thothctl scan iac -t {tool_name}",
                duration_seconds=duration / len(tools),
                summary=f"{rd.get('passed_count', 0)} passed, {failed} failed",
                report_path=tool_result.get("report_path"),
                findings_count=failed,
                details=rd,
            ))

        # Gate logic
        total_failures = sum(s.findings_count for s in result.steps)
        if enforcement == "hard" and total_failures > 0:
            result.passed = False
            result.gate_blocked = True
        elif total_failures > 0:
            result.passed = False

        return result

    @property
    def description(self) -> str:
        return "🔒 Secure — Security scanning, compliance, vulnerability detection"
```

### 1.5 Workflow Service (`services/workflow/workflow_service.py`)

```python
"""Workflow orchestrator — executes SDLC phases in sequence."""
import logging
from typing import Dict, List, Optional

from .models import Phase, WorkflowResult
from .phases.base import PhaseExecutor
from .phases.develop import DevelopPhaseExecutor
from .phases.build import BuildPhaseExecutor
from .phases.test import TestPhaseExecutor
from .phases.secure import SecurePhaseExecutor
from .phases.deploy import DeployPhaseExecutor
from .phases.monitor import MonitorPhaseExecutor

logger = logging.getLogger(__name__)


# Phase execution order
PHASE_ORDER = [
    Phase.DEVELOP, Phase.BUILD, Phase.TEST,
    Phase.SECURE, Phase.DEPLOY, Phase.MONITOR,
]

# Composite phase mappings
COMPOSITE_PHASES = {
    Phase.PRE_DEPLOY: [Phase.TEST, Phase.SECURE],
    Phase.ALL: PHASE_ORDER,
}


class WorkflowService:
    """Orchestrates DevSecOps SDLC phases."""

    def __init__(self):
        self._executors: Dict[Phase, PhaseExecutor] = {
            Phase.DEVELOP: DevelopPhaseExecutor(),
            Phase.BUILD: BuildPhaseExecutor(),
            Phase.TEST: TestPhaseExecutor(),
            Phase.SECURE: SecurePhaseExecutor(),
            Phase.DEPLOY: DeployPhaseExecutor(),
            Phase.MONITOR: MonitorPhaseExecutor(),
        }

    def execute(
        self,
        phases: List[Phase],
        directory: str,
        reports_dir: str,
        options: Optional[Dict] = None,
        enforcement: str = "soft",
    ) -> WorkflowResult:
        """Execute one or more SDLC phases in order."""
        options = options or {}
        options["enforcement"] = enforcement
        result = WorkflowResult(enforcement=enforcement)

        # Resolve composite phases
        resolved = []
        for phase in phases:
            if phase in COMPOSITE_PHASES:
                resolved.extend(COMPOSITE_PHASES[phase])
            else:
                resolved.append(phase)

        # Deduplicate while preserving order
        seen = set()
        ordered = []
        for p in resolved:
            if p not in seen:
                seen.add(p)
                ordered.append(p)

        # Execute phases in sequence
        for phase in ordered:
            executor = self._executors.get(phase)
            if not executor:
                logger.warning(f"No executor for phase: {phase.value}")
                continue

            logger.info(f"Executing phase: {executor.description}")
            phase_result = executor.execute(directory, reports_dir, options)
            result.phases.append(phase_result)

            # Stop on hard enforcement failure
            if enforcement == "hard" and phase_result.gate_blocked:
                result.stopped_at = phase
                break

        return result
```

### 1.6 CLI Command (`commands/workflow/commands/devsecops.py`)

```python
"""thothctl workflow devsecops — composite DevSecOps SDLC command."""
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import rich.box

from ....core.commands import ClickCommand
from ....services.workflow.models import Phase, StepStatus
from ....services.workflow.workflow_service import WorkflowService


class DevSecOpsWorkflowCommand(ClickCommand):
    """Execute DevSecOps SDLC phases."""

    def _execute(self, phase: str, reports_dir: str, enforcement: str, **kwargs):
        console = Console()
        service = WorkflowService()

        # Resolve phase selection
        selected = [Phase(phase)]

        ctx = click.get_current_context()
        directory = ctx.obj.get("CODE_DIRECTORY", ".")

        # Execute workflow
        result = service.execute(
            phases=selected,
            directory=directory,
            reports_dir=reports_dir,
            options=kwargs,
            enforcement=enforcement,
        )

        # Display results table
        self._display_results(console, result)

        if result.stopped_at:
            raise SystemExit(1)

    def _display_results(self, console, result):
        """Render workflow results as Rich table."""
        # ... Rich table rendering per phase/step ...
        pass


# Click wiring
cli = DevSecOpsWorkflowCommand.as_click_command(
    help="Execute DevSecOps SDLC workflow phases."
)(
    click.option("--phase", "-p",
        type=click.Choice([p.value for p in Phase]),
        default="all",
        help="SDLC phase to execute"),
    click.option("--reports-dir", "-r", default="Reports"),
    click.option("--enforcement",
        type=click.Choice(["soft", "hard"]),
        default="soft"),
    click.option("--policy-dir", default=None,
        help="OPA policy directory or Git URL"),
    click.option("--tools", "-t", multiple=True, default=None,
        help="Override scan tools for secure phase"),
)
```

### 1.7 MCP Server Exposure

Add to `services/mcp/stdio_server.py`:

```python
Tool(
    name="thothctl_workflow_devsecops",
    description="Execute DevSecOps SDLC workflow phases. "
                "Phases: develop, build, test, secure, deploy, monitor, pre-deploy, all. "
                "Use --enforcement hard to fail on violations.",
    inputSchema={
        "type": "object",
        "properties": {
            "phase": {
                "type": "string",
                "enum": ["develop", "build", "test", "secure", "deploy", "monitor", "pre-deploy", "all"],
                "default": "all",
                "description": "SDLC phase to execute"
            },
            "enforcement": {
                "type": "string",
                "enum": ["soft", "hard"],
                "default": "soft"
            },
            "policy_dir": {
                "type": "string",
                "description": "OPA policy directory or Git URL"
            }
        },
        "additionalProperties": False,
    }
),
```

### 1.8 Registration in CLI Entry Point

In `src/thothctl/cli.py`, register the new group:

```python
from .commands.workflow.cli import cli as workflow_cli
app.add_command(workflow_cli, "workflow")
```

---

## Layer 2: Kiro CLI Skill

### 2.1 File Structure

```
thothctl-devsecops-skill/
├── SKILL.md                              # Main skill definition
├── references/
│   ├── sdlc_phases.md                    # Phase definitions + decision criteria
│   ├── command_reference.md              # All thothctl commands with parameters
│   ├── remediation_patterns.md           # Failure → fix mapping
│   ├── ci_cd_templates.md                # Pipeline examples (GitHub, Azure, GitLab)
│   └── project_type_routing.md           # Terraform vs CDK vs CFN differences
```

### 2.2 Skill Definition (`SKILL.md`)

```markdown
# ThothCTL DevSecOps Workflow Skill

## Purpose
Guide developers through the complete DevSecOps SDLC for Infrastructure as Code
using ThothCTL. Orchestrate phases intelligently based on project context, provide
remediation guidance, and enforce organizational policies.

## When to Use
- User wants to validate, secure, or deploy IaC
- User asks about security posture of their infrastructure code
- User wants to run "the full pipeline" or specific phases
- User mentions cost estimation, blast radius, drift, or compliance
- User asks to prepare for production deployment

## MCP Tools Required
- thothctl_check_environment
- thothctl_check_project
- thothctl_check_iac
- thothctl_scan_iac
- thothctl_inventory_iac
- thothctl_document_iac
- thothctl_workflow_devsecops (composite)
- thothctl_cost_analysis
- thothctl_drift_detection

---

## Decision Logic

### Phase Selection

When the user's intent is vague ("check my project"), follow this routing:

1. **First time in project** → Phase: `develop` (environment + structure)
2. **Before PR/merge** → Phase: `pre-deploy` (test + secure)
3. **Full audit** → Phase: `all`
4. **Security focus** → Phase: `secure`
5. **Cost concern** → Phase: `plan` (cost-analysis)
6. **Post-deployment** → Phase: `monitor` (drift)

### Project Type Detection

Before running commands, detect project type:
- Has `terragrunt.hcl` → terraform-terragrunt
- Has `main.tf` only → terraform
- Has `cdk.json` → cdkv2
- Has CloudFormation templates → cloudformation

This affects:
- Which scan tools to use (OPA needs hcl/ vs cloudformation/ policies)
- How to generate plans (terragrunt run-all vs terraform plan)
- Inventory command flags (--framework-type)

### Enforcement Decision

- Local development → `--enforcement soft` (report only)
- CI/CD pipeline → `--enforcement hard` (fail on violations)
- User says "strict" / "production" / "hard" → `--enforcement hard`

---

## Workflow Procedures

### Procedure: Full DevSecOps Pipeline

```
1. Detect project type (check for terragrunt.hcl, main.tf, cdk.json)
2. Run: thothctl_check_environment
3. Run: thothctl_check_project
4. Run: thothctl_inventory_iac (with --check-versions)
5. If tfplan/ exists:
   - Run: thothctl_check_iac (blast-radius)
   - Run: thothctl_cost_analysis
6. Run: thothctl_scan_iac (tools: checkov, trivy, opa)
7. Summarize findings with severity breakdown
8. If failures found → show remediation from references/remediation_patterns.md
9. If all pass → confirm ready for deployment
```

### Procedure: Security Audit

```
1. Run: thothctl_scan_iac --tools checkov trivy opa --enforcement soft
2. Analyze findings by severity (CRITICAL > HIGH > MEDIUM > LOW)
3. For each CRITICAL/HIGH finding:
   - Explain the risk
   - Provide specific fix (reference remediation_patterns.md)
4. Show compliance posture summary
```

### Procedure: Pre-Deployment Validation

```
1. Verify tfplan exists (prompt user to generate if missing)
2. Run: thothctl_check_iac -type blast-radius
3. If blast radius > threshold → WARN user, ask for confirmation
4. Run: thothctl_scan_iac --enforcement hard
5. If violations → BLOCK and show fixes
6. If clean → confirm safe to deploy
```

---

## Response Patterns

### On Success
"✅ All {N} checks passed across {tools}. Your infrastructure code is ready
for deployment. Report saved to {path}."

### On Failure (soft enforcement)
"⚠️ Found {N} issues ({critical} critical, {high} high).
Here are the top priority fixes: [remediation details].
Run with --enforcement hard to block deployments until resolved."

### On Failure (hard enforcement)
"⛔ Pipeline blocked: {N} violations detected.
You must resolve these before deploying:
[remediation details with file:line references]"

### On Missing Prerequisites
"I need a Terraform plan to run {phase}. Generate one with:
`terragrunt run-all plan --out-dir tfplan --json-out-dir tfplan`
Then I'll continue with the analysis."
```

### 2.3 References

#### `references/sdlc_phases.md`

Detailed description of each phase with:
- Purpose and objective
- ThothCTL commands with exact parameters
- Expected outputs and how to interpret them
- Gate criteria (what constitutes pass/fail)
- Dependencies on other phases

#### `references/command_reference.md`

Quick reference of all thothctl commands the skill can invoke via MCP:

| Command | MCP Tool | Key Parameters |
|---------|----------|----------------|
| `check environment` | `thothctl_check_environment` | (none) |
| `check project iac` | `thothctl_check_project` | (none) |
| `scan iac` | `thothctl_scan_iac` | tools, enforcement |
| `inventory iac` | `thothctl_inventory_iac` | check_versions, project_name |
| `check iac -type drift` | `thothctl_drift_detection` | tftool, recursive |
| `check iac -type cost` | `thothctl_cost_analysis` | recursive |
| `workflow devsecops` | `thothctl_workflow_devsecops` | phase, enforcement, policy_dir |

#### `references/remediation_patterns.md`

Common failure patterns and their fixes:

| Finding | Tool | Fix |
|---------|------|-----|
| S3 bucket public access | Checkov CKV_AWS_19 | Add `block_public_acls = true` |
| No encryption at rest | Checkov CKV_AWS_145 | Add `storage_encrypted = true` |
| Missing required tags | OPA/tagging.rego | Add tags block with Environment, Owner, CostCenter |
| IAM wildcard actions | OPA/iam.rego | Scope to specific actions |
| Outdated module version | Inventory | Update source version constraint |

#### `references/ci_cd_templates.md`

Ready-to-use pipeline templates for GitHub Actions, Azure Pipelines, and GitLab CI
that use `thothctl workflow devsecops --phase <X> --enforcement hard`.

#### `references/project_type_routing.md`

Decision matrix for project type → command variations:

| Project Type | Plan Command | Scan Extras | Policy Path |
|-------------|-------------|-------------|-------------|
| terraform-terragrunt | `terragrunt run-all plan` | `--framework-type terragrunt` | `shared/policy/hcl` |
| terraform | `terraform plan -out=tfplan` | (default) | `shared/policy/hcl` |
| cdkv2 | `cdk synth` | `--framework cloudformation` | `shared/policy/cloudformation` |
| cloudformation | N/A (static) | `--framework cloudformation` | `shared/policy/cloudformation` |

---

## Implementation Order

### Sprint 1: Foundation (Week 1)

| # | Task | Type | Effort |
|---|------|------|--------|
| 1 | Create `services/workflow/models.py` | Service | S |
| 2 | Create `services/workflow/phases/base.py` | Service | S |
| 3 | Implement `SecurePhaseExecutor` | Service | M |
| 4 | Implement `DevelopPhaseExecutor` | Service | M |
| 5 | Create `WorkflowService` orchestrator | Service | M |
| 6 | Create `commands/workflow/` CLI structure | Command | M |
| 7 | Wire `thothctl workflow devsecops --phase secure` | Integration | S |
| 8 | Unit tests for models + service | Test | M |

### Sprint 2: Complete Phases (Week 2)

| # | Task | Type | Effort |
|---|------|------|--------|
| 9 | Implement `BuildPhaseExecutor` (inventory) | Service | M |
| 10 | Implement `TestPhaseExecutor` (blast-radius, tfplan) | Service | M |
| 11 | Implement `DeployPhaseExecutor` (enforcement gate) | Service | S |
| 12 | Implement `MonitorPhaseExecutor` (drift) | Service | M |
| 13 | Implement composite phases (all, pre-deploy) | Service | S |
| 14 | Rich UI: workflow progress display + summary table | Command | M |
| 15 | Integration tests: full workflow on test project | Test | L |

### Sprint 3: MCP + Skill (Week 3)

| # | Task | Type | Effort |
|---|------|------|--------|
| 16 | Expose `thothctl_workflow_devsecops` in MCP server | MCP | S |
| 17 | Create `thothctl-devsecops-skill/SKILL.md` | Skill | L |
| 18 | Create `references/sdlc_phases.md` | Docs | M |
| 19 | Create `references/command_reference.md` | Docs | S |
| 20 | Create `references/remediation_patterns.md` | Docs | M |
| 21 | Create `references/project_type_routing.md` | Docs | S |
| 22 | Create `references/ci_cd_templates.md` | Docs | M |
| 23 | Test skill with Kiro CLI against real project | Test | L |

### Sprint 4: Polish + CI/CD (Week 4)

| # | Task | Type | Effort |
|---|------|------|--------|
| 24 | Workflow YAML config support (`.thothcf.toml` [workflow] section) | Feature | M |
| 25 | `--post-to-pr` support on workflow command | Feature | S |
| 26 | JSON/SARIF output for workflow results | Feature | M |
| 27 | GitHub Actions reusable workflow template | Docs | M |
| 28 | Azure Pipelines template | Docs | M |
| 29 | Documentation: `docs/framework/commands/workflow/` | Docs | M |
| 30 | Version bump + release | Release | S |

---

## Testing Strategy

### Unit Tests

```
tests/
├── test_workflow_models.py           # Phase, StepResult, WorkflowResult
├── test_workflow_service.py          # Orchestration logic, composite phases
├── test_phase_secure.py             # Secure executor with mocked ScanService
├── test_phase_develop.py            # Develop executor
└── test_workflow_command.py          # CLI integration
```

### Integration Tests

- Run `thothctl workflow devsecops --phase develop` on `terragrunt_aws_gitops_blueprint`
- Run `thothctl workflow devsecops --phase secure` with org-iac-policies
- Run `thothctl workflow devsecops --phase all` end-to-end
- Test `--enforcement hard` exits with code 1 on failures

### Skill Tests

- Test decision routing with different user intents
- Verify MCP tool calls match expected workflow for each scenario
- Validate remediation suggestions against known findings

---

## Configuration (`[workflow]` in `.thothcf.toml`)

```toml
[workflow.devsecops]
# Default tools for secure phase
scan_tools = ["checkov", "trivy", "opa"]
# Default enforcement
enforcement = "soft"
# Organization policy repo
policy_dir = "https://github.com/thothforge/org-iac-policies.git@main"
# Phases to skip (e.g., skip plan if no tfplan available)
skip_phases = []
# Gate thresholds
[workflow.devsecops.gates]
max_critical = 0      # Block if any critical findings
max_high = 5          # Block if more than 5 high findings
blast_radius_warn = 10  # Warn if blast radius > 10 resources
```

---

## Success Criteria

1. `thothctl workflow devsecops --phase secure` produces same results as manual `scan iac`
2. `thothctl workflow devsecops --phase all` runs full pipeline in under 60s on test project
3. `--enforcement hard` exits 1 when violations exist
4. MCP tool `thothctl_workflow_devsecops` callable from Kiro CLI
5. Skill correctly routes "prepare for production" → pre-deploy phases
6. Skill provides actionable remediation for top findings
7. CI/CD templates work in GitHub Actions and Azure Pipelines
