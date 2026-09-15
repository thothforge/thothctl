# Phase 2.5.1 — Agent Autonomy Model

> **Status**: In development | **Phase**: 2.5 (Agent Governance & Autonomy Framework) | **Target**: v0.29.0
> **Roadmap task**: 2.5.1 — "Autonomy level model. Implement 4-level system aligned with Weave Intelligence framework. Define tool allow/deny lists per level in `.thothcf.toml`."

## 1. Purpose

Today ThothCTL's auto-decision capability is a **binary switch** — `DecisionRules.enabled = True/False`
(`services/ai_review/config/decision_rules.py`). Either the agent can auto-decide on PRs, or it cannot.

Phase 2.5.1 replaces that binary with a **graduated autonomy dial** aligned to the industry-standard
**4 Levels of Agentic Development** (Weave Intelligence, PlatformCon 2026). Each level is a named contract
that answers three questions:

1. **Capability** — which tools/actions may the agent invoke?
2. **Gates** — what must pass before an action executes (validation, approval, risk ceiling)?
3. **Blast radius** — how many dependent resources may a single action touch?

This is **agent RBAC**, not human RBAC. It is the keystone of Phase 2.5: the MCP Gateway (2.5.2),
self-correction loop (2.5.5), and policy generation (2.5.6) all consult "the current autonomy level."

## 2. Scope

**In scope (this task):**
- `AutonomyLevel` and `AutonomyConfig` dataclasses + loader from `.thothcf.toml [agent.autonomy]`
- Level → action mapping and `is_tool_allowed()` / `is_action_allowed()` resolution (deny-beats-allow)
- Safe-by-default resolution (Level 1 when unconfigured)
- Enforcement hook in `SafetyGuard.can_take_action()` as the **first** check
- `--autonomy` flag on `ai-review decide`
- Unit tests

**Out of scope (later 2.5 tasks):**
- MCP Gateway middleware (2.5.2) — this task only provides the model it will consume
- Budget turn/duration extensions (2.5.4)
- Self-correction loop (2.5.5), policy generation (2.5.6)
- Non-human identity audit enrichment (2.5.7)
- `max_blast_radius` **enforcement** (needs Phase 5 resource graph); the field is parsed and stored now,
  enforced later. `auto_merge_risk_max` and gate flags are stored now and consumed by the decision path.

## 3. The Four Levels

| Level | Name | Human role | Agent may... | CLI value |
|-------|------|-----------|-------------|-----------|
| 1 | Human-in-the-loop | Execution engine | Suggest, analyze, report (read-only) | `suggest` (default) |
| 2 | Human-on-the-loop | Verifier | Write files, create PRs, generate fixes; **not** apply/destroy | `draft` |
| 3 | Human-as-orchestrator | Exception review | Continuous execution, auto-merge low-risk | `validate` |
| 4 | Autonomous | System designer | Self-initiate from signals, remediate within guardrails | `execute` (break-glass) |

**Action → minimum level** (the gate `SafetyGuard` enforces):

| Action class | Min level | Rationale |
|---|---|---|
| `analyze`, `scan`, `report`, `comment` | 1 | Read-only, always safe |
| `request_changes` | 2 | Writes a PR review verdict |
| `approve`, `reject` | 2 | Auto PR decision (verified by human) |
| auto-merge | 3 | Merges without per-change human review |
| `apply`, `destroy`, self-initiated remediation | 4 | Mutates live infrastructure |

## 4. Configuration Schema (`.thothcf.toml`)

```toml
[agent.autonomy]
default_level = 1                    # 1=suggest 2=draft 3=validate 4=execute; unconfigured => 1

[agent.autonomy.levels.1]            # Human-in-the-loop
allowed_tools = ["read-file", "scan", "inventory", "describe-resource", "analyze"]

[agent.autonomy.levels.2]            # Human-on-the-loop
allowed_tools = ["read-file", "write-file", "scan", "git-commit", "git-push", "create-pr"]
denied_tools  = ["terraform-apply", "terraform-destroy"]

[agent.autonomy.levels.3]            # Human-as-orchestrator
allowed_tools = ["*"]
denied_tools  = ["terraform-apply", "terraform-destroy"]
requires_validation = true           # must pass pre-execution checks
auto_merge_risk_max = 20             # auto-merge only when risk score <= 20

[agent.autonomy.levels.4]            # Autonomous
allowed_tools = ["*"]
requires_approval = ["named-approver"]
max_blast_radius = 10                # (parsed now; enforced with Phase 5 graph)
```

If the `[agent.autonomy]` table is absent, the model falls back to **built-in safe defaults** identical to
the four levels above, with `default_level = 1`.

## 5. Data Model (`services/ai_review/config/autonomy.py`)

```python
LEVEL_NAMES = {1: "suggest", 2: "draft", 3: "validate", 4: "execute"}
NAME_TO_LEVEL = {v: k for k, v in LEVEL_NAMES.items()}

# Action class -> minimum level required
ACTION_MIN_LEVEL = {
    "analyze": 1, "scan": 1, "report": 1, "comment": 1,
    "request_changes": 2, "approve": 2, "reject": 2,
    "auto_merge": 3,
    "apply": 4, "destroy": 4, "remediate": 4,
}

@dataclass
class AutonomyLevel:
    level: int
    name: str
    allowed_tools: List[str]          # "*" = all
    denied_tools: List[str]           # deny wins over allow
    requires_validation: bool = False
    requires_approval: List[str] = []
    auto_merge_risk_max: Optional[int] = None
    max_blast_radius: Optional[int] = None

    def is_tool_allowed(self, tool: str) -> bool:
        # deny-beats-allow; "*" allows all not explicitly denied
        ...

@dataclass
class AutonomyConfig:
    default_level: int = 1
    levels: Dict[int, AutonomyLevel]  # 1..4, safe built-ins if unset

    @classmethod
    def load(cls, directory: str = ".") -> "AutonomyConfig": ...
    @classmethod
    def default(cls) -> "AutonomyConfig": ...

    def resolve_level(self, requested: Optional[str|int]) -> AutonomyLevel: ...
    def is_action_allowed(self, action: str, level: AutonomyLevel) -> Tuple[bool, str]: ...
```

### Resolution rules
- **deny-beats-allow**: a tool in both lists is denied. `"*"` in `allowed_tools` permits everything not in
  `denied_tools`.
- **safe-by-default**: unknown/absent config → Level 1. A malformed config must never *escalate* privilege;
  on parse error we log a warning and fall back to built-in defaults.
- **action gating**: `is_action_allowed(action, level)` returns `False` when
  `level.level < ACTION_MIN_LEVEL[action]`. Unknown actions default to the highest requirement (4).
- **downward override only** (future, 2.5 org-policy): CLI `--autonomy` may *request* a level, but org policy
  (`org_policy_loader.py`) may cap the maximum. Capping is a follow-up; this task honors the CLI/`default_level`.

## 6. Enforcement Choke Points

### 6.1 SafetyGuard (this task)
`SafetyGuard.__init__` gains an optional `autonomy_level: AutonomyLevel`. `can_take_action()` runs the
autonomy gate **first**, before override/confidence/rate-limit:

```
can_take_action(action, confidence, repository, pr_context):
    if autonomy_level:
        ok, reason = is_action_allowed(action, autonomy_level)   # NEW — first
        if not ok: return (False, reason)
    # ... existing override -> confidence -> rate-limit checks unchanged
```

When no autonomy level is supplied (existing callers), behavior is unchanged — backward compatible.

### 6.2 DecisionEngine (this task)
`DecisionEngine.__init__(rules, autonomy_level=None)` forwards the level to `SafetyGuard`. `decide.py`
resolves `--autonomy` → `AutonomyLevel` and passes it in.

### 6.3 MCP Gateway (Task 2.5.2, not this task)
The gateway will wrap `_run_cmd` in `services/mcp/stdio_server.py`, mapping each tool to a capability and
calling `AutonomyLevel.is_tool_allowed()` before execution. This task ships the model it needs.

## 7. CLI

```bash
# Level 1 (default) — read-only analysis, no PR action
thothctl ai-review decide -d ./terraform --autonomy suggest

# Level 2 — may post approve/reject/request-changes
thothctl ai-review decide -d ./terraform --pr-number 42 --autonomy draft
```

`--autonomy [suggest|draft|validate|execute]`, default `suggest`. Accepts the numeric level too via
`resolve_level`.

## 8. Testing Plan (`tests/test_ai_autonomy.py`)

1. **Level resolution**: name↔level, numeric input, unknown → default, absent config → Level 1.
2. **Tool allow/deny**: explicit allow; explicit deny; deny-beats-allow when in both; `"*"` wildcard;
   `"*"` with a deny entry.
3. **Action gating**: read-only allowed at L1; `approve` blocked at L1, allowed at L2; `apply` blocked below L4.
4. **Safe default**: `AutonomyConfig.default()` has 4 levels, L1 read-only.
5. **Config load**: parse a `[agent.autonomy]` TOML; malformed TOML → safe defaults (no escalation).
6. **SafetyGuard integration**: `can_take_action("approve", 0.99, ...)` returns blocked at L1 with an
   autonomy reason; passes the autonomy gate at L2 (then subject to existing checks).

Run: `python -m pytest tests/test_ai_autonomy.py tests/test_ai_safety_guard.py tests/test_ai_decision_engine.py -v`

## 9. Backward Compatibility

- New `autonomy_level` params are **optional** with `None` defaults → all existing `SafetyGuard`/
  `DecisionEngine` callers behave exactly as before.
- No change to `decision_rules.py` schema; autonomy lives in its own `[agent.autonomy]` table and its own
  module, loaded independently.
- Default CLI behavior (`--autonomy suggest`) is the most restrictive, so upgrading cannot silently grant
  an agent more power than before.

## 10. Follow-ups (unblocked by this task)

| Task | Depends on this |
|---|---|
| 2.5.2 MCP Gateway | `is_tool_allowed()` + capability map |
| 2.5.4 Budget turns/duration | level-scoped budgets |
| 2.5.5 Self-correction loop | "current level" gate |
| 2.5.7 Non-human identity audit | log level + decision per tool call |
| 2.5.9 Safe defaults surfaced in config | `AutonomyConfig.default()` writer |
| Phase 5.9 blast-radius enforcement | `max_blast_radius` field (parsed here) |
