"""Stack optimizer service for deduplicating overlapping terragrunt stacks.

Resolves the DAG of terragrunt dependencies and computes the minimal set of
filters that covers exactly the user-requested stacks without redundant
processing.

Key principle: Never remove an explicit user stack. Only remove stacks whose
resolved units are entirely contained within another stack's resolved units
(including its transitive dependencies via the '...' suffix).
"""
import fnmatch
import logging
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class StackOptimizer:
    """Optimizes a list of terragrunt stack filters by resolving the DAG
    and eliminating redundant filters."""

    def __init__(self, base_path: Path, stacks_base: str = "resources"):
        self.base_path = base_path
        self.stacks_base = stacks_base
        self._units: Dict[str, Set[str]] = {}  # unit_path -> set of dependency paths
        self._all_unit_paths: List[str] = []

    def optimize(self, target_stacks: List[str]) -> dict:
        """Compute the minimal filter set for the given target stacks.

        Args:
            target_stacks: List of glob patterns relative to stacks_base
                           (e.g. ["Network/**", "Compute/EC2/EC2_Bastion_Private/**"])

        Returns:
            dict with keys:
                optimized_filters: minimal list of filters
                removed_redundant: filters that were eliminated
                details: per-filter resolution info
        """
        self._discover_units()
        self._build_dependency_graph()

        # Resolve each stack pattern to its set of units (with transitive deps)
        resolved: Dict[str, Set[str]] = {}
        for stack in target_stacks:
            units = self._resolve_stack_with_deps(stack)
            resolved[stack] = units

        # Find redundant stacks: A is redundant if its units ⊆ another stack's units
        redundant = set()
        stacks_list = list(resolved.keys())

        for i, stack_a in enumerate(stacks_list):
            for j, stack_b in enumerate(stacks_list):
                if i == j:
                    continue
                if stack_a in redundant:
                    break
                # stack_a is redundant only if ALL its units are covered by stack_b
                if resolved[stack_a] <= resolved[stack_b] and resolved[stack_a] != resolved[stack_b]:
                    redundant.add(stack_a)
                    break

        optimized = [s for s in target_stacks if s not in redundant]

        return {
            "optimized_filters": optimized,
            "removed_redundant": list(redundant),
            "total_units_before": sum(len(v) for v in resolved.values()),
            "total_units_after": len(set().union(*(resolved[s] for s in optimized))),
            "details": {
                stack: {
                    "direct_units": len(self._resolve_stack_direct(stack)),
                    "with_deps": len(units),
                    "redundant": stack in redundant,
                }
                for stack, units in resolved.items()
            },
        }

    def _discover_units(self):
        """Find all terragrunt units (directories with terragrunt.hcl)."""
        resources_path = self.base_path / self.stacks_base
        if not resources_path.exists():
            logger.warning(f"Stacks base path not found: {resources_path}")
            return

        for hcl_file in resources_path.rglob("terragrunt.hcl"):
            unit_dir = hcl_file.parent
            rel_path = str(unit_dir.relative_to(resources_path))
            self._all_unit_paths.append(rel_path)
            self._units[rel_path] = set()

    def _build_dependency_graph(self):
        """Parse terragrunt.hcl files to extract dependency edges."""
        resources_path = self.base_path / self.stacks_base

        for unit_path in self._all_unit_paths:
            hcl_file = resources_path / unit_path / "terragrunt.hcl"
            deps = self._parse_dependencies(hcl_file, resources_path)
            self._units[unit_path] = deps

    def _parse_dependencies(self, hcl_file: Path, resources_path: Path) -> Set[str]:
        """Extract dependency config_paths from a terragrunt.hcl file."""
        deps = set()
        try:
            with open(hcl_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Primary strategy: extract /resources/<path> directly from config_path lines
            # This handles all interpolation patterns (get_parent_terragrunt_dir, etc.)
            import re
            for match in re.finditer(r'/resources/([^\s"\'}\)]+)', content):
                dep_path = match.group(1).rstrip('/"')
                if dep_path in self._all_unit_paths:
                    deps.add(dep_path)

            # Fallback: handle relative paths (../)
            if not deps:
                for match in re.finditer(r'config_path\s*=\s*"(\.\.[^"]+)"', content):
                    resolved = self._resolve_config_path(match.group(1), hcl_file.parent, resources_path)
                    if resolved:
                        deps.add(resolved)

        except Exception as e:
            logger.debug(f"Failed to parse {hcl_file}: {e}")

        return deps

    def _resolve_config_path(self, config_path: str, unit_dir: Path, resources_path: Path) -> str:
        """Resolve a config_path (may contain terragrunt functions) to a relative unit path."""
        if not config_path:
            return ""

        # Handle common patterns:
        # "${get_parent_terragrunt_dir("root")}/resources/Network/VPC"
        # Simplify by extracting the path after /resources/
        if "/resources/" in config_path:
            rel = config_path.split("/resources/", 1)[1]
            # Remove trailing quotes or interpolation artifacts
            rel = rel.strip('"').strip("'").rstrip("/")
            if rel in self._all_unit_paths:
                return rel
            return rel

        # Handle relative paths like "../../../Network/VPC"
        if config_path.startswith("..") or config_path.startswith("./"):
            try:
                resolved = (unit_dir / config_path).resolve()
                rel = str(resolved.relative_to(resources_path))
                return rel
            except (ValueError, OSError):
                pass

        return ""

    def _resolve_stack_direct(self, stack_pattern: str) -> Set[str]:
        """Resolve a glob pattern to matching unit paths (no dependency expansion)."""
        matched = set()
        for unit_path in self._all_unit_paths:
            if fnmatch.fnmatch(unit_path, stack_pattern):
                matched.add(unit_path)
        return matched

    def _resolve_stack_with_deps(self, stack_pattern: str) -> Set[str]:
        """Resolve a glob pattern to matching unit paths + all transitive dependencies."""
        direct = self._resolve_stack_direct(stack_pattern)
        all_units = set(direct)

        # BFS to collect transitive dependencies
        queue = list(direct)
        visited = set(direct)

        while queue:
            current = queue.pop(0)
            for dep in self._units.get(current, set()):
                if dep not in visited and dep in self._units:
                    visited.add(dep)
                    all_units.add(dep)
                    queue.append(dep)

        return all_units
