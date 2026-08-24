# What's New

## v0.27.13 — Kiro CLI Provider + Dependency-Track Integration (August 2026)

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
