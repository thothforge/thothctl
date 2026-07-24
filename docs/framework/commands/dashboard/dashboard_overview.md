# Dashboard Command

The `dashboard` command launches a local web application that provides a unified view of all ThothCTL analysis results — security scans, inventory, cost analysis, blast radius, drift detection, and topology.

## Overview

The dashboard aggregates data from the `Reports/` directory and project configuration to present:

- Security scan findings with severity breakdown
- Infrastructure inventory (modules, providers, versions)
- Software Bill of Materials (SBOM) viewer
- AWS cost analysis projections
- Blast radius impact visualization
- Infrastructure drift status
- Network topology diagrams
- AI usage and decision history

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `launch` | Start the dashboard web server |

## Usage

```bash
# Launch with defaults (port 8080, opens browser)
thothctl dashboard launch

# Custom port
thothctl dashboard launch --port 3000

# Without auto-opening browser
thothctl dashboard launch --no-browser

# Debug mode
thothctl dashboard launch --debug
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-p, --port` | Integer | 8080 | Port to run the dashboard on |
| `-h, --host` | Text | 127.0.0.1 | Host to bind the dashboard to |
| `--debug` | Flag | false | Run in debug mode with auto-reload |
| `--no-browser` | Flag | false | Do not open browser automatically |

## Dashboard Sections

### 📊 Project Overview

Displays project metadata, type (Terraform/Terragrunt/CDK), and available ThothCTL commands for the detected project type.

### 🔒 Security Findings

Shows aggregated scan results from Checkov, Trivy, KICS, and OPA:
- Severity breakdown (critical, high, medium, low)
- Findings per tool
- Trend over time (from scan history)

### 📦 Inventory

Module and provider catalog:
- Current vs latest versions
- Source URLs
- Outdated dependency alerts
- CycloneDX SBOM data

### 💰 Cost Analysis

AWS cost projections from tfplan analysis:
- Monthly/annual estimates
- Per-service breakdown
- Optimization recommendations

### 💥 Blast Radius

Change impact visualization:
- Resources affected by plan
- Create/update/delete breakdown
- Risk assessment

### 🔄 Drift Detection

Infrastructure drift status:
- Resources with state mismatch
- Drift history and trends
- Coverage metrics

### 🗺️ Topology

Infrastructure topology visualization:
- Resource dependency graph
- Network architecture diagram

### 🤖 AI Usage

AI-powered analysis history:
- Decisions made by AI review
- Cost tracking per provider
- Session history

## API Endpoints

The dashboard exposes a REST API for programmatic access:

| Endpoint | Description |
|----------|-------------|
| `GET /api/project` | Project info (type, name, commands) |
| `GET /api/inventory` | Module and provider inventory |
| `GET /api/sbom` | CycloneDX SBOM data |
| `GET /api/scan-results` | Security scan results |
| `GET /api/findings` | Detailed findings list |
| `GET /api/cost-analysis` | Cost projections |
| `GET /api/blast-radius` | Blast radius data |
| `GET /api/drift` | Drift detection results |
| `GET /api/topology` | Infrastructure topology |
| `GET /api/ai-usage` | AI decision history |
| `GET /api/refresh` | Reload all data from Reports/ |

## Prerequisites

The dashboard reads data from the `Reports/` directory. Run analysis commands first:

```bash
# Generate data for the dashboard
thothctl scan iac -t checkov -t trivy -t opa       # Security findings
thothctl inventory iac --check-versions             # Inventory + SBOM
thothctl check iac -type cost-analysis              # Cost analysis
thothctl check iac -type blast-radius               # Blast radius
thothctl check iac -type drift                      # Drift detection
```

Or use the workflow command to run everything:

```bash
thothctl workflow devsecops --phase all
thothctl dashboard launch
```

## Example

```bash
# Run full pipeline then view results
$ thothctl workflow devsecops --phase all
$ thothctl dashboard launch --port 3000

🌐 Dashboard running at http://127.0.0.1:3000
📊 Loaded: 22 findings, 45 modules, 3 cost reports
🔧 Press Ctrl+C to stop
```

## Related

- [Scan Command](../scan/scan_overview.md)
- [Inventory Command](../inventory/)
- [Check Command](../check/)
- [Workflow Command](../workflow/workflow_overview.md)
