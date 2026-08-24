# Changelog

All notable changes to ThothCTL are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.27.13] - 2026-08-22

### Added

- **Dependency-Track SBOM publishing** (`--publish-sbom dependency-track`)
  - Publishes CycloneDX SBOM to OWASP Dependency-Track via PUT /api/v1/bom
  - Auto-creates project if it doesn't exist (autoCreate=true)
  - Config via env vars (`DTRACK_URL`, `DTRACK_API_KEY`) or `.thothcf.toml`
  - Supports project UUID (`DTRACK_PROJECT_UUID`) for existing projects
  - Supports parent project hierarchy for multi-project orgs
  - BOM sanitization for DTRACK v5.x compatibility (strips unsupported CycloneDX 1.6 fields)
  - Resolves project name from SBOM metadata when not configured
  - 31 unit tests covering all paths
- **DefectDojo SBOM publishing** (`--publish-sbom defectdojo`)
  - Publishes CycloneDX SBOM to OWASP DefectDojo via /api/v2/reimport-scan/
  - Token-based authentication
  - Auto-creates product, product type, and engagement
  - Deduplication and close-old-findings support
  - Config via env vars (`DEFECTDOJO_URL`, `DEFECTDOJO_TOKEN`) or `.thothcf.toml`
  - 21 unit tests covering all paths
- **Kiro CLI as AI provider** for Intent-to-IaC generation (`--provider kiro`)
  - Uses Kiro headless mode (`kiro-cli chat --no-interactive --trust-all-tools`)
  - Tool-augmented generation: reads project files, searches docs, validates output
  - Custom agent support: `--model <agent-name>` maps to `.kiro/agents/<name>.yaml`
  - 5-strategy JSON extraction for robust parsing of mixed agent output
  - Recursion guard via `THOTHCTL_KIRO_PROVIDER_ACTIVE` env var prevents infinite loops
- New provider registered in `code_generator.py` factory alongside ollama/bedrock/openai/azure
- Updated `generate iac` CLI to accept `kiro` as a valid provider choice

### Docs

- Updated `generate_iac.md` with Kiro provider section, setup guide, and tradeoffs
- Updated `inventory_iac.md` with Dependency-Track integration section
- Added v0.27.13 entry to What's New

### Fixed

- **CycloneDX SBOM: populate `group` field** for module components
  - Registry modules: group = namespace (e.g., `terraform-aws-modules`)
  - Local modules: group = `local`
  - Providers: group = publisher (e.g., `hashicorp`)
- **CycloneDX SBOM: recursive file search** — find SBOM in `Reports/inventory/` subdirectory
- **Dependency-Track compatibility** — sanitize BOM to remove CycloneDX 1.6 fields unsupported by DTRACK v5.0.x (`attestations`, `definitions`, `formulation`, lifecycle phase `deploy`)

## [0.27.7] - 2026-08-14

### Fixed

- Document command: fix `graph.svg` generation for Terragrunt projects

## [0.27.5] - 2026-08-14

### Fixed

- Document command: correct Terragrunt DAG graph command order for v0.99+

### Docs

- Update MCP tools list (26 tools) and generate iac documentation

## [0.27.3] - 2026-08-14

### Added

- **MCP: expose `generate iac` via MCP** with full capabilities (intent, mode, composition, self-correction)
- Dashboard: Generation History tab for intent-to-IaC runs

## [0.27.2] - 2026-08-14

### Security

- Harden intent-to-IaC pipeline before MCP exposure (input validation, output sanitization)

## [0.27.1] - 2026-08-14

### Added

- **`--mode blueprint|project` flag** for `generate iac` output
  - `blueprint`: produces `#{...}#` placeholders for IDP/Backstage consumption
  - `project`: resolves values from space config + intent, ready to deploy

## [0.27.0] - 2026-08-14

### Added

- **Secure plan validation** for Intent-to-IaC (Phase 1.10)
  - Per-stack + full-project plan via Terragrunt v0.99+ native commands
  - `--iam-assume-role`, `--provider-cache`, `--graph` support
  - Convergence detection and JSON repair
  - Self-correction loop: plan failure → regenerate → re-plan (max iterations)

## [0.26.1] - 2026-08-13

### Added

- **Scaffold-driven composition** — multi-stack generation grounded in official scaffolds
  - `ScaffoldLoader`: fetch and parse scaffold structure from GitHub
  - `IntentDecomposer`: break complex intents into per-stack responsibilities
  - `ProjectAssembler`: assemble multi-stack projects with correct inter-stack references
  - Scaffold completeness validation

### Fixed

- Composition mode generates pure TF per stack (not nested terragrunt projects)
- Remove `terraform{source}` from `terragrunt.hcl` (module source belongs in `main.tf`)
- Update tests for OPA v1 syntax

## [0.26.0] - 2026-08-11

### Added

- **Composition-aware Intent-to-IaC generation** (Phase 1.9)
  - Multi-stack decomposition from single intent
  - Auto-fetch official scaffold from GitHub for composition context
  - Few-shot context from scaffold examples (replaces hardcoded prompts)

## [0.25.8] - 2026-08-06

### Added

- Enforce `.thothcf.toml` org policy rules at Intent-to-IaC generation time (Phase 2.4)

## [0.25.3] - 2026-07-30

### Added

- **Phase 2 Policy Engine**: OPA/Conftest integration with org policy repos
- Intent-to-IaC improvements (context builder, validation loop)
- **MCP v2.0 protocol upgrade** (Starlette HTTP + stdio modes)
- CDK and CloudFormation scaffolds added to Official Scaffolds

## [0.25.0] - 2026-07-29

### Added

- **Custom workflow engine**: YAML DAG pipelines with `depends_on`, conditions, failure handling
- `thothctl workflow run --file .thothcf_workflow.yaml` command
- **Auto-update check**: non-blocking cached version check against PyPI (24h TTL)
- **MCP server**: 22+ tools exposed via Model Context Protocol
- **CDK v2 inventory support**: dependency tracking for CDK projects
- Categorized CLI help output (DevSecOps, Project Lifecycle, Governance, Utilities)
- `--changed-only` flag for workflow phases (git-aware scoping)

### Improved

- Major developer experience improvements across CLI output and error messages

## [0.24.0] - 2026-07-23

### Added

- **DevSecOps SDLC workflow engine** with 7 phases (Plan → Monitor)
- `thothctl workflow devsecops --phase <phase>` command
- Phases: plan, develop, build, test, secure, deploy, monitor
- Composite phases: `all`, `pre-deploy`
- `--enforcement soft|hard` mode
- Spinner animation and live progress during phase execution
- Dashboard enhancements: Technical Debt Metrics, cost aggregation

### Improved

- OPA scanner: show policy repo URL, exclude non-IaC files
- Dashboard: project name overflow fix, scan tools detection

---

## Earlier Releases

For releases prior to v0.24.0, see the [git history](https://github.com/thothforge/thothctl/commits/main).
