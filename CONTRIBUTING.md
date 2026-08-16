# Contributing to ThothCTL

Thank you for your interest in contributing to ThothCTL! This guide will help you get started.

## Quick Links

- [Issues](https://github.com/thothforge/thothctl/issues) — Bug reports, feature requests
- [Discussions](https://github.com/thothforge/thothctl/discussions) — Questions, ideas, RFC
- [Documentation](https://thothforge.github.io/thothctl/) — User docs
- [Roadmap](https://thothforge.github.io/thothctl/framework/roadmap_fdi/) — What's planned

---

## Development Setup

### Prerequisites

- Python 3.10+ (3.12 recommended)
- Git
- Optional: `graphviz` (for diagram generation)

### Install in Development Mode

```bash
git clone https://github.com/thothforge/thothctl.git
cd thothctl
pip install -e .
```

With telemetry support:

```bash
pip install -e .[telemetry]
```

### Setup Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

Pre-commit runs:
- **Ruff** (linter + formatter, Black-compatible)
- **pydocstyle** (docstring enforcement)
- **output-consistency** (custom checker)

### Verify Installation

```bash
thothctl --version
thothctl --help
```

---

## Architecture Overview

ThothCTL follows a layered architecture:

```
src/thothctl/
├── cli.py                  # Entry point (Click MultiCommand)
├── commands/               # CLI layer — command definitions
│   └── <command>/
│       ├── cli.py          # Click Group with dynamic subcommand loading
│       └── commands/       # Individual subcommands (must export `cli`)
├── services/               # Business logic — where the work happens
│   ├── ai_review/          # Multi-agent AI review system
│   ├── scan/               # Security scanner orchestration
│   ├── workflow/            # DevSecOps workflow engine
│   ├── generate/           # Intent-to-IaC generation
│   ├── inventory/          # SBOM and dependency tracking
│   ├── dashboard/          # FastAPI web dashboard
│   └── ...
├── core/                   # Cross-cutting concerns (logging, config, telemetry)
├── config/                 # Settings, models, constants
└── utils/                  # Reusable helpers
```

**Key patterns:**

- **Dynamic command loading**: Commands are discovered from filesystem. Each subcommand file must export a `cli` attribute (Click command/group).
- **Service layer separation**: Commands validate input and delegate to services. Business logic lives in `services/`.
- **ClickCommand base class** (`core/commands.py`): Provides `validate()` → `pre_execute()` → `_execute()` → `post_execute()` lifecycle with telemetry.

---

## Code Style

| Setting | Value |
|---|---|
| Formatter | Ruff (Black-compatible) |
| Line length | 88 |
| Indent | 4 spaces |
| Quotes | Double |
| Target version | Python 3.8 |
| Import sorting | Ruff isort (`I`) |
| Lint rules | `E4`, `E7`, `E9`, `F`, `I` |

### Format and Lint

```bash
# Format
ruff format src/

# Lint (with auto-fix)
ruff check src/ --fix

# Run pre-commit on all files
pre-commit run --all-files
```

### Docstrings

All public functions and classes require docstrings (enforced by pydocstyle):

```python
def scan_directory(path: str, tools: list[str]) -> ScanResult:
    """Scan a directory for security issues using the specified tools.

    Args:
        path: Path to the IaC directory.
        tools: List of scanner names (e.g., ["checkov", "trivy"]).

    Returns:
        ScanResult with findings grouped by severity.
    """
```

---

## Running Tests

```bash
# Run all tests with coverage
python -m pytest tests/ -v --cov=src/

# Run a specific test file
python -m pytest tests/test_scan.py -v

# Run tests across Python versions (requires tox)
tox
```

---

## Commit Conventions

We use [Conventional Commits](https://www.conventionalcommits.org/) enforced via [Commitizen](https://commitizen-tools.github.io/commitizen/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | When to use |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or correcting tests |
| `chore` | Build process, tooling, dependencies |
| `security` | Security hardening (no new features) |
| `ci` | CI/CD changes |

### Examples

```bash
feat(generate): add --mode blueprint|project for intent-to-IaC output
fix(scan): exclude non-IaC files from conftest scan
docs: update MCP tools list (26 tools)
security(v0.27.2): harden intent-to-IaC pipeline before MCP exposure
```

---

## Pull Request Process

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes** following the code style and architecture patterns above.

3. **Write tests** for new functionality.

4. **Run quality checks**:
   ```bash
   pre-commit run --all-files
   python -m pytest tests/ -v --cov=src/
   ```

5. **Submit a PR** with:
   - Clear title (conventional commit format)
   - Description of what changed and why
   - Link to related issue (if any)

6. **Review**: Maintainers will review within a few days. Address feedback in additional commits.

### PR Checklist

- [ ] Follows code style (ruff format passes)
- [ ] Tests pass (`pytest`)
- [ ] Pre-commit hooks pass
- [ ] New features have tests
- [ ] New commands have documentation
- [ ] Breaking changes are noted in PR description

---

## Adding a New Command

1. Create a directory under `src/thothctl/commands/`:
   ```
   commands/my_command/
   ├── __init__.py
   ├── cli.py              # Click Group
   └── commands/
       └── my_subcommand.py  # Must export `cli`
   ```

2. The main CLI auto-discovers it. Hyphens and underscores are normalized (`my_command` → `my-command`).

3. Add the command to the appropriate category in `cli.py` → `COMMAND_CATEGORIES`.

4. Create service logic in `services/my_command/` (keep CLI layer thin).

5. Add documentation in `docs/framework/commands/my-command/`.

6. Add to `mkdocs.yaml` nav.

---

## Adding a New Scanner

Scanners live in `services/scan/scanners/`. Each scanner implements the scanner interface:

```python
class MyScanner:
    """My custom scanner."""

    def scan(self, directory: str, options: dict) -> ScanResult:
        """Run the scan and return results."""
        ...
```

Register it in `services/scan/scan_service.py`.

---

## Where to Start

### Good First Issues

Look for issues labeled [`good-first-issue`](https://github.com/thothforge/thothctl/labels/good-first-issue):

- Documentation improvements
- Adding example outputs to command docs
- Test coverage for existing services
- CLI help text improvements

### Medium Complexity

- New scanner integration
- Dashboard visualization enhancements
- Workflow phase improvements
- MCP tool additions

### High Complexity

- New AI agents (requires AI provider experience)
- Workflow engine features (parallel execution, triggers)
- State graph implementation (Phase 5)

---

## Communication

- **Issues**: For bugs and specific feature requests
- **Discussions**: For design proposals, questions, and broader topics
- **PRs**: Link to the issue being addressed

---

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
