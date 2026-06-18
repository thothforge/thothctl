# Check Dependencies Command

## Overview

The `check deps` command visualizes and analyzes infrastructure dependencies in your Terragrunt projects. It parses the DAG (Directed Acyclic Graph) from `terragrunt dag graph`, calculates component risk scores, and renders the topology in multiple formats.

## Usage

```bash
# Default: Rich tree with risk percentages
thothctl check iac -type deps

# ASCII box topology (best for terminal sharing)
thothctl check iac -type deps --format boxart

# Interactive HTML in browser (vis.js graph)
thothctl check iac -type deps --format html

# Raw DOT output (pipe to graphviz or other tools)
thothctl check iac -type deps --format dot
```

## Output Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| `tree` | Rich tree with color-coded risk | Default terminal view |
| `boxart` | ASCII box drawing topology | Copy/paste into docs, Slack, PRs |
| `html` | Interactive vis.js graph in browser | Presentations, exploration |
| `dot` | Raw GraphViz DOT | Pipe to `dot`, `neato`, custom tools |

### Tree (default)

```
Infrastructure Modules
└── stacks/observability/network/reachability-analyzer (31.0% risk)
    ├── stacks/foundation/network/security-groups (38.5% risk)
    │   └── stacks/foundation/network/vpc (46.5% risk)
    └── stacks/platform/data/rds (42.5% risk)
```

### Boxart

```
┌───────────────┐  ┌──────────────────┐
│ vpc 47%       │  │ security-groups 39% │
└───────────────┘  └──────────────────┘
         │                    │
         ▼                    ▼
┌───────────────┐  ┌──────────────────┐
│ rds 43%       │  │ vpc-lattice 34%  │
└───────────────┘  └──────────────────┘
```

For best quality boxart, install `graph-easy`:

| OS | Install Command |
|----|----------------|
| **Linux (Debian/Ubuntu)** | `sudo apt install libgraph-easy-perl` |
| **macOS** | `brew install graph-easy` |
| **Windows** | `choco install graphviz` then use `--format dot \| dot -Tpng -o graph.png` |

> **Note**: Without `graph-easy`, ThothCTL uses a built-in Python fallback renderer.

### HTML

Opens an interactive topology in your default browser with:
- Hierarchical top-down layout
- Color-coded nodes (green < 30% risk, orange 30-50%, red > 50%)
- Hover for full stack path
- Saved to `Reports/dependency_topology.html`

### DOT

Outputs raw DOT graph for piping:

```bash
# Generate PNG image
thothctl check iac -type deps --format dot | dot -Tpng -o topology.png

# Generate SVG
thothctl check iac -type deps --format dot | dot -Tsvg -o topology.svg

# Open in xdot viewer
thothctl check iac -type deps --format dot | xdot -
```

## Prerequisites

| Tool | Required | Install |
|------|----------|---------|
| `terragrunt` | ✅ Required | [terragrunt.gruntwork.io](https://terragrunt.gruntwork.io/) |
| `graphviz` | Optional (for `--format dot` piping) | See below |
| `graph-easy` | Optional (for `--format boxart` enhanced output) | See below |

### Installing Graphviz

| OS | Command |
|----|---------|
| Linux (Debian/Ubuntu) | `sudo apt install graphviz` |
| macOS | `brew install graphviz` |
| Windows | `choco install graphviz` |

### Installing graph-easy

| OS | Command |
|----|---------|
| Linux (Debian/Ubuntu) | `sudo apt install libgraph-easy-perl` |
| macOS | `brew install graph-easy` |
| Windows (WSL) | `sudo apt install libgraph-easy-perl` |

> **Windows native**: `graph-easy` is a Perl tool. On native Windows, use WSL or the `--format html` alternative.

## Features

- **Risk Assessment**: Each component gets a risk percentage based on fan-in/fan-out degree and dependency depth
- **Terragrunt Details**: Shows mock_outputs and config_path from `dependency` blocks
- **Multiple Renderers**: Terminal, ASCII art, browser, and raw DOT
- **CI/CD Friendly**: `--format dot` for pipeline image generation, `--format boxart` for PR comments

## Examples

### CI/CD Pipeline — Post topology to PR

```bash
# Generate boxart for PR comment
echo '```' > /tmp/deps.md
thothctl check iac -type deps --format boxart >> /tmp/deps.md
echo '```' >> /tmp/deps.md
gh pr comment --body-file /tmp/deps.md
```

### Generate documentation artifact

```bash
thothctl check iac -type deps --format html
# → Opens browser + saves Reports/dependency_topology.html
```

## Related Commands

- [`check blast-radius`](blast-radius.md) — Assess change impact analysis
- [`check tfplan`](plan.md) — Analyze Terraform plans
- [`inventory iac`](../inventory/iac.md) — Create dependency inventory
- [`document iac`](../document/iac.md) — Generate documentation with graphs
