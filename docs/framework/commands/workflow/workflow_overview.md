# Workflow Command

The `workflow` command in ThothCTL provides composite DevSecOps pipeline execution, orchestrating multiple commands into cohesive SDLC phases. Instead of running individual commands manually, the workflow command chains them in the correct order with enforcement gates and live progress feedback.

## Overview

The workflow command helps DevSecOps teams to:

- Execute complete SDLC phases with a single command
- Enforce security gates that block deployments on violations
- Get live progress feedback with animated spinners
- Skip phases gracefully when prerequisites are missing
- Produce consolidated results across all steps in a phase

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `devsecops` | Execute DevSecOps SDLC phases (plan, develop, build, test, secure, deploy, monitor) |

## Basic Usage

```bash
# Run full DevSecOps pipeline
thothctl workflow devsecops

# Run a specific phase
thothctl workflow devsecops --phase secure

# Run with hard enforcement (exit 1 on violations)
thothctl workflow devsecops --phase secure --enforcement hard

# Run pre-deployment validation (test + secure combined)
thothctl workflow devsecops --phase pre-deploy

# Use organization policies from a Git repo
thothctl workflow devsecops --phase secure \
  --policy-dir https://github.com/myorg/iac-policies.git@main
```

## How It Works

```
┌──────────────────────────────────────────────────────────────┐
│                    thothctl workflow devsecops                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  📋 Plan ──→ 💻 Develop ──→ 🔨 Build ──→ ✅ Test            │
│                                                ↓             │
│  📊 Monitor ←── 🚀 Deploy ←── 🔒 Secure ←────┘             │
│                                                              │
│  Each phase:                                                 │
│  1. Shows animated spinner while running                     │
│  2. Prints immediate pass/fail after completion              │
│  3. Stops pipeline on gate failure (hard enforcement)        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Related

- [Workflow DevSecOps Command Reference](workflow_devsecops.md)
- [DevSecOps SDLC Use Case](../../use_cases/devsecops_sdlc.md)
- [DevSecOps Quick Start](../../use_cases/devsecops_quickstart.md)
