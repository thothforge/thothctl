"""Project-type-aware tool packs for init env.

Each pack defines which tools are needed for a project type.
SAST/compliance tools are always in base (mandatory for all project types).
Runtime dependencies (node, python) are checked but never installed.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ProjectType(Enum):
    """Supported project types for tool packs."""

    TERRAFORM = "terraform"
    TERRAGRUNT = "terraform-terragrunt"
    TOFU = "tofu"
    CDKV2 = "cdkv2"
    TERRAFORM_MODULE = "terraform_module"
    CUSTOM = "custom"


@dataclass
class Prerequisite:
    """A runtime dependency that must be present (check-only, never install)."""

    name: str
    min_version: Optional[str] = None
    check_command: str = ""
    install_hint: str = ""
    version_managers: List[str] = field(default_factory=list)


@dataclass
class ToolPack:
    """A collection of tools for a project type."""

    name: str
    description: str
    tools: List[str]
    prerequisites: List[Prerequisite] = field(default_factory=list)
    inherits_from: Optional[str] = None


# ── Prerequisites (check-only, never install) ────────────────────────────────

PREREQ_NODE = Prerequisite(
    name="node",
    min_version="18.0.0",
    check_command="node --version",
    install_hint=(
        "Node.js 18+ required for CDK. Install via your version manager:\n"
        "  nvm:   nvm install 22\n"
        "  fnm:   fnm install 22\n"
        "  volta:  volta install node@22\n"
        "  Or:    https://nodejs.org/en/download/"
    ),
    version_managers=["nvm", "fnm", "volta", "asdf"],
)

PREREQ_NPM = Prerequisite(
    name="npm",
    min_version="9.0.0",
    check_command="npm --version",
    install_hint="npm comes with Node.js. Install Node.js first.",
)

PREREQ_PYTHON = Prerequisite(
    name="python3",
    min_version="3.10.0",
    check_command="python3 --version",
    install_hint=(
        "Python 3.10+ required for checkov/compliance tools.\n"
        "  pyenv:  pyenv install 3.12\n"
        "  apt:    sudo apt install python3\n"
        "  Or:     https://www.python.org/downloads/"
    ),
    version_managers=["pyenv", "asdf"],
)

PREREQ_PIP = Prerequisite(
    name="pip",
    check_command="pip3 --version",
    install_hint="pip comes with Python. Install Python first.",
)


# ── Tool Packs ────────────────────────────────────────────────────────────────

PACKS: Dict[str, ToolPack] = {
    "base": ToolPack(
        name="base",
        description="Core DevSecOps tools (SAST, compliance, governance)",
        tools=[
            "pre-commit",
            "commitizen",
            "thothctl",
            "kiro-cli",
            "checkov",
            "trivy",
            "opa",
            "conftest",
        ],
        prerequisites=[PREREQ_PYTHON, PREREQ_PIP],
    ),
    "terraform": ToolPack(
        name="terraform",
        description="Terraform development (HCL, providers, state management)",
        tools=[
            "terraform",
            "tfswitch",
            "tflint",
            "terraform-docs",
        ],
        inherits_from="base",
    ),
    "terraform-terragrunt": ToolPack(
        name="terraform-terragrunt",
        description="Terragrunt orchestration with Terraform",
        tools=[
            "terragrunt",
        ],
        inherits_from="terraform",
    ),
    "tofu": ToolPack(
        name="tofu",
        description="OpenTofu development",
        tools=[
            "tofu",
            "tflint",
            "terraform-docs",
        ],
        inherits_from="base",
    ),
    "cdkv2": ToolPack(
        name="cdkv2",
        description="AWS CDK v2 (TypeScript/Python)",
        tools=[
            "aws-cdk",
        ],
        prerequisites=[PREREQ_NODE, PREREQ_NPM],
        inherits_from="base",
    ),
    "terraform_module": ToolPack(
        name="terraform_module",
        description="Terraform module development",
        tools=[
            "terraform-docs",
        ],
        inherits_from="terraform",
    ),
    "custom": ToolPack(
        name="custom",
        description="Base tools only — select additional tools manually",
        tools=[],
        inherits_from="base",
    ),
}


def resolve_pack(project_type: str) -> ToolPack:
    """Resolve a pack including inherited tools and prerequisites.

    Returns a flattened ToolPack with all tools and prerequisites
    from the inheritance chain (root-first).
    """
    pack = PACKS.get(project_type)
    if not pack:
        pack = PACKS["custom"]

    # Walk inheritance chain
    chain = []
    current = pack
    while current:
        chain.append(current)
        if current.inherits_from:
            current = PACKS.get(current.inherits_from)
        else:
            current = None

    # Reverse to get root-first order
    chain.reverse()

    # Merge tools and prerequisites (deduplicate, preserve order)
    all_tools = []
    all_prereqs = []
    seen_tools = set()
    seen_prereqs = set()

    for p in chain:
        for tool in p.tools:
            if tool not in seen_tools:
                all_tools.append(tool)
                seen_tools.add(tool)
        for prereq in p.prerequisites:
            if prereq.name not in seen_prereqs:
                all_prereqs.append(prereq)
                seen_prereqs.add(prereq.name)

    return ToolPack(
        name=pack.name,
        description=pack.description,
        tools=all_tools,
        prerequisites=all_prereqs,
    )


def get_pack_names() -> List[str]:
    """Get list of available pack names."""
    return list(PACKS.keys())


def get_pack_summary() -> Dict[str, str]:
    """Get pack name → description mapping."""
    return {name: pack.description for name, pack in PACKS.items()}
