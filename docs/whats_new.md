# What's New

## v0.33.0 — SecObserve Product Groups (October 2026)

### Highlights

!!! success "Create SecObserve products inside a product group"
    ```bash
    thothctl scan iac -t checkov -p network-stack \
      --publish-to secobserve --product-group platform-team

    thothctl inventory iac --check-versions \
      --publish-sbom secobserve --product-group platform-team
    ```

- **`--product-group`** for `scan iac` (with `--publish-to secobserve`) and `inventory iac`
  (with `--publish-sbom secobserve`). It can also be set with `SECOBSERVE_PRODUCT_GROUP` or
  `product_group` in `[integrations.secobserve]`.
- New products are created in the group, and the group is created if it doesn't exist.
  **Existing products are never moved**, because the group decides which security gate
  applies; a warning is shown instead.
- SecObserve only: using the option with another platform, or without publishing, is a
  usage error.
- **Fix:** SBOM uploads now send the configured `origin_service` as the SecObserve service.
- SecObserve has no free-form tags or labels, so ThothCTL doesn't offer them.

See [Product groups](framework/commands/scan/scan_iac.md#product-groups).

---

## v0.32.0 — SecObserve Security Gate (October 2026)

### Highlights

!!! success "Let SecObserve's security gate decide pass/fail"
    ```bash
    thothctl scan iac -t checkov -t kics -p my-infra \
      --publish-to secobserve --gate-source secobserve --enforcement hard
    ```

- **`--gate-source local|secobserve|both`**:
    - `local` (default) keeps today's behaviour;
    - `secobserve` reads the product's security gate after publishing;
    - `both` fails if either gate fails.
- **Fails closed:** under `--enforcement hard`, a gate that can't be evaluated (server
  unreachable, product or branch not found) fails the pipeline.
- **Same rules as SecObserve:** the group overrides the product, unset thresholds count as
  0, and global settings are the fallback. Feature branches are evaluated from branch
  counts, because SecObserve only gates the default branch.
- **A new "SecObserve Security Gate" panel** shows the status, open counts, thresholds and a
  link to the product.
- **Fixed findings close automatically:** each tool is uploaded in its own stable file
  (`kics-results.sarif`, `thothctl-<tool>.sarif`), and a completed tool is re-uploaded even
  with no findings. Skipped or failed tools aren't uploaded, so their history is kept.
- Usage errors now exit with code 2 across `ClickCommand`-based commands.

!!! warning "Changed service name"
    Checkov and other non-KICS findings now use the tool name as the SecObserve service
    (previously `thothctl-scan`). Findings stored under the old service aren't resolved
    automatically.

See [Security Gate Source](framework/commands/scan/scan_iac.md#security-gate-source).

---

## v0.31 — Fixes & MCP Compatibility (October 2026)

- **v0.31.3** — `scan iac --publish-to secobserve` publishes every tool, not just KICS, and
  findings are linked to a SecObserve service.
- **v0.31.2** — fixed an `ImportError` in the OPA scanner when `THOTH_ORG_POLICY` is set;
  CDK technical-debt scoring is weighted by semver gap; `generate iac` reuses its system
  prompt across self-correction rounds.
- **v0.31.1** — the MCP server reports its version, and `mcp register` writes the keys used
  by Kiro CLI v3.
- **v0.31.0** — `init` installs AI agent skills from upstream repositories.

---

## v0.30.0 — Intent-to-IaC Hardening (September 2026)

### Highlights

!!! success "Accurate dependency-graph diagrams for multi-stack generation"
    Composition-mode diagrams now render the real stack dependency graph
    (from each stack's `depends_on`) grouped by layer — no more inferred edges.

!!! success "Targeted plan validation with --plan-filter"
    ```bash
    thothctl generate iac -i "add an RDS stack" \
      --composition incremental \
      --plan-validation full-project \
      --plan-filter "stacks/platform/data/*"
    ```

- **Safer plan validation** — per-stack plan validation no longer runs against the
  terragrunt project root (`root.hcl`); single-stack + `full-project` mode is routed
  correctly
- **`--plan-filter` wired end-to-end** — also settable via `THOTH_PLAN_FILTER` or
  `[generation.plan].stack_filter`
- **HCL-aware block stripping** — `terraform {}` / `provider {}` blocks are removed
  with a string/comment-aware scanner that handles nested blocks (`backend`,
  `assume_role`, `default_tags`) reliably
- **Single-mode placeholder resolution** — `--mode project` now resolves `#{...}#`
  placeholders for single-stack generation too
- **Raw-response debugging** — when the AI returns unparseable output, the raw
  response is saved to generation history for troubleshooting
- **Unified self-correction** — single and composition paths now share the same
  validate → fix → re-validate loop with stagnation detection
- Consistent `generation_tokens` metrics across modes; clearer warning when scaffold
  examples are unavailable (missing `gh` CLI)

---

## v0.28.0 — Security Platform Integrations (August 2026)

### Highlights

!!! success "Tool-augmented IaC generation with Kiro CLI"
    ```bash
    thothctl generate iac \
      -i "EKS cluster with Karpenter, IRSA, and cluster autoscaler" \
      -p kiro --apply
    ```

!!! success "Publish SBOM to Dependency-Track in one command"
    ```bash
    thothctl inventory iac --check-versions \
      --publish-sbom dependency-track
    ```

!!! success "Publish SBOM to DefectDojo in one command"
    ```bash
    thothctl inventory iac --check-versions \
      --publish-sbom defectdojo
    ```

- **Kiro CLI provider** — use `--provider kiro` to leverage Kiro's headless mode as a generation engine with full tool access (file reading, doc search, web search, Terraform registry lookup)
- **Dependency-Track integration** — `--publish-sbom dependency-track` publishes CycloneDX SBOM directly to OWASP Dependency-Track after inventory generation (auto-creates project, supports parent hierarchy)
- **DefectDojo integration** — `--publish-sbom defectdojo` publishes CycloneDX SBOM to OWASP DefectDojo (auto-creates product/engagement, deduplicates findings, Token auth)
- **Scan results to DefectDojo** — `thothctl scan iac --publish-to defectdojo` publishes Checkov, Trivy, KICS, and OPA findings directly to DefectDojo with native parsers
- **SecObserve integration** — `--publish-sbom secobserve` for license tracking + `--publish-to secobserve` for scan findings via SARIF (supports all scanners including OPA/Conftest)
- **Custom Kiro agents** — use `--model <agent-name>` to invoke a specialized `.kiro/agents/<name>.yaml` for IaC generation tasks
- **Recursion protection** — automatic detection and prevention of infinite loops when thothctl is used as an MCP tool inside Kiro
- **Per-stack dependency graphs** — `document iac` now generates correct scoped graphs for leaf terragrunt stacks (not the full layer graph)

**Why Kiro as a provider?** Unlike raw LLM API calls where the model only sees the prompt, Kiro has tool access — it can read your project structure, look up Terraform docs, and validate its own output. This produces significantly better results for complex multi-resource generation tasks.

---

## v0.27 — Intent-to-IaC: Production Ready (August 2026)

The v0.27 series completes **Phase 1: Intent-to-IaC Generation** with plan validation, blueprint/project modes, and MCP exposure.

### Highlights

!!! success "Generate governed IaC from natural language"
    ```bash
    thothctl generate iac \
      -i "VPC with 3 private subnets, NAT gateway, and flow logs" \
      -p ollama --mode project --space prod --apply
    ```

- **Plan validation** (v0.27.0) — generated code is validated via `terragrunt plan` with self-correction loops
- **Blueprint vs Project modes** (v0.27.1) — `--mode blueprint` for IDP/Backstage templates, `--mode project` for ready-to-deploy output
- **Security hardening** (v0.27.2) — input validation and output sanitization before MCP exposure
- **MCP integration** (v0.27.3) — `generate iac` available as MCP tool for AI assistants (26 tools total)
- **Dashboard** (v0.27.3) — Generation History tab tracks all intent-to-IaC runs

---

## v0.26 — Scaffold-Driven Composition (August 2026)

Multi-stack generation grounded in organizational scaffolds.

### Highlights

!!! example "One intent → multiple stacks"
    ```bash
    thothctl generate iac \
      -i "EKS cluster with VPC, RDS PostgreSQL, and S3 for artifacts" \
      --composition multi --apply
    ```

- **Composition-aware generation** (v0.26.0) — single intent decomposed into multiple stacks with correct inter-references
- **Scaffold loader** (v0.26.1) — fetches official scaffolds from GitHub as generation context
- **Few-shot grounding** — uses scaffold examples instead of hardcoded prompts for better output quality

---

## v0.25 — Workflow Engine & Policy (July 2026)

Custom YAML pipelines and organizational policy enforcement.

### Highlights

!!! tip "Composable DevSecOps pipelines"
    ```bash
    # Custom workflow
    thothctl workflow run --file .thothcf_workflow.yaml

    # Or use built-in phases
    thothctl workflow devsecops --phase pre-deploy --enforcement hard
    ```

- **Custom workflow engine** (v0.25.0) — YAML DAG pipelines with `depends_on`, conditions, and failure handling
- **MCP v2.0 protocol** (v0.25.3) — HTTP + stdio modes, 22+ tools exposed
- **Policy enforcement at generation time** (v0.25.8) — `.thothcf.toml` rules evaluated inside the generation loop
- **OPA/Conftest** as the policy engine — org policy repos loaded via `THOTH_ORG_POLICY` env var
- **CDK v2 inventory support** — dependency tracking for AWS CDK projects

---

## v0.24 — DevSecOps SDLC Engine (July 2026)

The workflow engine that orchestrates your entire infrastructure lifecycle.

### Highlights

!!! info "7-phase DevSecOps lifecycle"
    ```bash
    thothctl workflow devsecops --phase all --enforcement hard
    ```

- **7 SDLC phases**: Plan → Develop → Build → Test → Secure → Deploy → Monitor
- **Composite phases**: `all` (full pipeline), `pre-deploy` (test + secure)
- **Enforcement modes**: `soft` (warn and continue) or `hard` (block on violations)
- **Live progress**: spinner animation during phase execution
- **Dashboard improvements**: Technical Debt Metrics, multi-stack cost aggregation

---

## Upgrading

```bash
pip install --upgrade thothctl
thothctl --version
```

ThothCTL checks for updates automatically on every invocation (cached 24h). You'll see a notice when a newer version is available.

---

## Full Changelog

See [CHANGELOG.md](https://github.com/thothforge/thothctl/blob/main/CHANGELOG.md) for the complete release history.
