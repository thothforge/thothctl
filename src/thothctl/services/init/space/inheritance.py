"""Space inheritance — resolve configuration by walking parent chain."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import toml

logger = logging.getLogger(__name__)

MAX_INHERITANCE_DEPTH = 5


def resolve_space_config(space_name: str) -> Dict:
    """Resolve effective space config by walking the inheritance chain.

    Child values override parent values. Lists are replaced, not merged.
    Max depth of 5 to prevent infinite loops.

    Returns merged config dict.
    """
    chain = _build_inheritance_chain(space_name)

    # Start from root ancestor, apply each child's overrides
    effective = {}
    for name in chain:
        space_config = _load_raw_space_config(name)
        if space_config:
            _deep_merge(effective, space_config)

    # Mark which fields are inherited vs local
    effective["_inheritance_chain"] = chain
    return effective


def get_parent_space(space_name: str) -> Optional[str]:
    """Get the parent space name, or None if no parent."""
    config = _load_raw_space_config(space_name)
    if config:
        return config.get("parent")
    return None


def set_parent_space(space_name: str, parent_name: str) -> None:
    """Set the parent of a space. Validates no cycles."""
    # Validate parent exists
    parent_config = _load_raw_space_config(parent_name)
    if not parent_config:
        raise ValueError(f"Parent space '{parent_name}' does not exist")

    # Check for cycles
    _detect_cycle(space_name, parent_name)

    # Write parent to spaces.toml
    spaces_path = Path.home() / ".thothcf" / "spaces.toml"
    with open(spaces_path, mode="rt", encoding="utf-8") as fp:
        config = toml.load(fp)

    config["spaces"][space_name]["parent"] = parent_name

    with open(spaces_path, mode="wt", encoding="utf-8") as fp:
        toml.dump(config, fp)

    logger.info(f"Set parent of '{space_name}' to '{parent_name}'")


def _build_inheritance_chain(space_name: str) -> List[str]:
    """Build ordered list from root ancestor to the target space."""
    chain = []
    visited = set()
    current = space_name

    while current:
        if current in visited:
            raise ValueError(
                f"Circular inheritance detected: {' -> '.join(chain)} -> {current}"
            )
        visited.add(current)
        chain.append(current)
        current = get_parent_space(current)

    if len(chain) > MAX_INHERITANCE_DEPTH:
        raise ValueError(
            f"Inheritance chain exceeds max depth ({MAX_INHERITANCE_DEPTH}): "
            f"{' -> '.join(chain)}"
        )

    # Reverse so root ancestor is first (base), target is last (overrides)
    chain.reverse()
    return chain


def _detect_cycle(child: str, proposed_parent: str) -> None:
    """Check if setting proposed_parent would create a cycle."""
    visited = {child}
    current = proposed_parent

    while current:
        if current in visited:
            raise ValueError(
                f"Cannot set parent: would create cycle "
                f"({child} -> {proposed_parent} -> ... -> {current})"
            )
        visited.add(current)
        current = get_parent_space(current)


def _load_raw_space_config(space_name: str) -> Optional[Dict]:
    """Load raw space config from spaces.toml (without inheritance resolution)."""
    spaces_path = Path.home() / ".thothcf" / "spaces.toml"
    if not spaces_path.exists():
        return None

    with open(spaces_path, mode="rt", encoding="utf-8") as fp:
        config = toml.load(fp)

    return config.get("spaces", {}).get(space_name)


def _deep_merge(base: Dict, override: Dict) -> None:
    """Deep merge override into base. Override wins on conflicts. Lists are replaced."""
    for key, value in override.items():
        if key == "parent":
            continue  # Don't propagate parent field
        if key == "projects":
            continue  # Projects are space-local, never inherited
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
