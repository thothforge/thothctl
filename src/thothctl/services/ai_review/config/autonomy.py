"""Agent autonomy model — graduated governance for AI agents.

Implements the 4-level autonomy framework (Weave Intelligence "4 Levels of
Agentic Development", adopted at PlatformCon 2026) that replaces ThothCTL's
binary auto-decision switch with a graduated trust dial.

Each level is a named contract defining:
1. Capability — which tools/actions the agent may invoke (allow/deny lists).
2. Gates — validation/approval/risk ceilings before an action executes.
3. Blast radius — how many dependent resources one action may touch.

Configuration lives in ``.thothcf.toml`` under ``[agent.autonomy]``. When
absent or malformed, the model falls back to built-in **safe defaults**
(Level 1, read-only) — a misconfiguration must never escalate privilege.

See ``docs/framework/specs/phase2.5.1_autonomy_model.md``.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Level number -> CLI name and back
LEVEL_NAMES: Dict[int, str] = {1: "suggest", 2: "draft", 3: "validate", 4: "execute"}
NAME_TO_LEVEL: Dict[str, int] = {v: k for k, v in LEVEL_NAMES.items()}

# Action class -> minimum autonomy level required to perform it.
# Unknown actions default to the highest requirement (see is_action_allowed).
ACTION_MIN_LEVEL: Dict[str, int] = {
    # Level 1 — read-only
    "analyze": 1,
    "scan": 1,
    "report": 1,
    "comment": 1,
    "inventory": 1,
    # Level 2 — writes verdicts / PRs, verified by a human
    "request_changes": 2,
    "approve": 2,
    "reject": 2,
    "create_pr": 2,
    # Level 3 — auto-merge low-risk without per-change review
    "auto_merge": 3,
    # Level 4 — mutates live infrastructure / self-initiates
    "apply": 4,
    "destroy": 4,
    "remediate": 4,
}

# Action requirement used when an action is not in ACTION_MIN_LEVEL.
_UNKNOWN_ACTION_MIN_LEVEL = 4

WILDCARD = "*"


@dataclass
class AutonomyLevel:
    """A single autonomy tier's capability contract."""

    level: int
    name: str
    allowed_tools: List[str] = field(default_factory=list)
    denied_tools: List[str] = field(default_factory=list)
    requires_validation: bool = False
    requires_approval: List[str] = field(default_factory=list)
    auto_merge_risk_max: Optional[int] = None
    max_blast_radius: Optional[int] = None

    def is_tool_allowed(self, tool: str) -> bool:
        """Return True if ``tool`` may be invoked at this level.

        Resolution is **deny-beats-allow**: a tool present in ``denied_tools``
        is rejected even if also allowed (or covered by the ``"*"`` wildcard).
        """
        if tool in self.denied_tools:
            return False
        if WILDCARD in self.allowed_tools:
            return True
        return tool in self.allowed_tools


def _default_levels() -> Dict[int, AutonomyLevel]:
    """Built-in safe defaults, identical to the documented schema."""
    return {
        1: AutonomyLevel(
            level=1,
            name="suggest",
            allowed_tools=[
                "read-file",
                "scan",
                "inventory",
                "describe-resource",
                "analyze",
            ],
        ),
        2: AutonomyLevel(
            level=2,
            name="draft",
            allowed_tools=[
                "read-file",
                "write-file",
                "scan",
                "git-commit",
                "git-push",
                "create-pr",
            ],
            denied_tools=["terraform-apply", "terraform-destroy"],
        ),
        3: AutonomyLevel(
            level=3,
            name="validate",
            allowed_tools=[WILDCARD],
            denied_tools=["terraform-apply", "terraform-destroy"],
            requires_validation=True,
            auto_merge_risk_max=20,
        ),
        4: AutonomyLevel(
            level=4,
            name="execute",
            allowed_tools=[WILDCARD],
            requires_approval=["named-approver"],
            max_blast_radius=10,
        ),
    }


@dataclass
class AutonomyConfig:
    """The full autonomy configuration: default level + the four tiers."""

    default_level: int = 1
    levels: Dict[int, AutonomyLevel] = field(default_factory=_default_levels)

    @classmethod
    def default(cls) -> "AutonomyConfig":
        """Return the built-in safe configuration (Level 1 default)."""
        return cls(default_level=1, levels=_default_levels())

    @classmethod
    def load(cls, directory: str = ".") -> "AutonomyConfig":
        """Load ``[agent.autonomy]`` from ``.thothcf.toml`` in ``directory``.

        Falls back to safe defaults when the file or table is missing, or if
        parsing fails. A malformed config never escalates privilege.
        """
        config = cls.default()
        toml_path = os.path.join(directory, ".thothcf.toml")
        if not os.path.exists(toml_path):
            return config

        try:
            import toml

            with open(toml_path, "r") as f:
                data = toml.load(f)
        except Exception as e:  # noqa: BLE001 — never fail closed with escalation
            logger.warning(
                "Could not parse .thothcf.toml for autonomy config (%s); "
                "using safe defaults (Level 1).",
                e,
            )
            return cls.default()

        autonomy = data.get("agent", {}).get("autonomy", {})
        if not autonomy:
            return config

        try:
            config.default_level = int(
                autonomy.get("default_level", config.default_level)
            )
            if config.default_level not in LEVEL_NAMES:
                logger.warning(
                    "Invalid default_level %s; falling back to 1.",
                    config.default_level,
                )
                config.default_level = 1

            level_tables = autonomy.get("levels", {})
            for key, tbl in level_tables.items():
                try:
                    lvl = int(key)
                except (TypeError, ValueError):
                    logger.warning("Ignoring non-integer autonomy level key %r", key)
                    continue
                if lvl not in LEVEL_NAMES:
                    logger.warning("Ignoring unknown autonomy level %s", lvl)
                    continue
                config.levels[lvl] = AutonomyLevel(
                    level=lvl,
                    name=LEVEL_NAMES[lvl],
                    allowed_tools=list(tbl.get("allowed_tools", [])),
                    denied_tools=list(tbl.get("denied_tools", [])),
                    requires_validation=bool(tbl.get("requires_validation", False)),
                    requires_approval=list(tbl.get("requires_approval", [])),
                    auto_merge_risk_max=tbl.get("auto_merge_risk_max"),
                    max_blast_radius=tbl.get("max_blast_radius"),
                )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Error reading [agent.autonomy] (%s); using safe defaults.", e
            )
            return cls.default()

        return config

    def resolve_level(
        self, requested: Optional[Union[str, int]] = None
    ) -> AutonomyLevel:
        """Resolve a requested level (name or number) to an AutonomyLevel.

        Falls back to ``default_level`` on unknown/absent input. Never raises.
        """
        lvl_num: Optional[int] = None

        if requested is None:
            lvl_num = self.default_level
        elif isinstance(requested, int):
            lvl_num = requested
        else:
            # string: try name first, then numeric string
            name = str(requested).strip().lower()
            if name in NAME_TO_LEVEL:
                lvl_num = NAME_TO_LEVEL[name]
            else:
                try:
                    lvl_num = int(name)
                except ValueError:
                    lvl_num = None

        if lvl_num not in LEVEL_NAMES:
            logger.warning(
                "Unknown autonomy level %r; using default level %s.",
                requested,
                self.default_level,
            )
            lvl_num = self.default_level

        return self.levels.get(lvl_num, _default_levels()[lvl_num])

    def is_action_allowed(
        self, action: str, level: AutonomyLevel
    ) -> Tuple[bool, str]:
        """Return (allowed, reason) for performing ``action`` at ``level``.

        An action is allowed only if the level meets its minimum requirement.
        Unknown actions require the highest level (fail safe).
        """
        min_level = ACTION_MIN_LEVEL.get(action, _UNKNOWN_ACTION_MIN_LEVEL)
        if level.level >= min_level:
            return True, (
                f"Action '{action}' permitted at autonomy level "
                f"{level.level} ({level.name})"
            )
        return False, (
            f"Action '{action}' requires autonomy level {min_level} "
            f"({LEVEL_NAMES.get(min_level, min_level)}); current level is "
            f"{level.level} ({level.name})"
        )
