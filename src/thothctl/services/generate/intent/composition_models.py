"""Composition models for multi-stack Intent-to-IaC decomposition.

Defines the data structures used to represent a decomposed infrastructure
intent as a collection of ordered stacks organized by architectural layers.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Canonical layer ordering (lower index = deployed first)
LAYER_ORDER: Dict[str, int] = {
    "foundation": 0,
    "platform": 1,
    "application": 2,
    "observability": 3,
}


@dataclass
class StackPlan:
    """A single infrastructure stack within a composition plan.

    Represents one logical unit of IaC (e.g., VPC, EKS cluster, RDS)
    that maps to a directory of Terraform/Terragrunt files.
    """

    name: str  # e.g., 'vpc'
    layer: str  # foundation | platform | application | observability
    domain: str  # e.g., 'networking', 'data', 'compute'
    intent: str  # Specific intent for this stack
    depends_on: List[str] = field(default_factory=list)  # Stack names
    module_source: Optional[str] = None  # Official module if applicable

    @property
    def path(self) -> str:
        """Return the relative directory path for this stack."""
        return f"stacks/{self.layer}/{self.domain}/{self.name}"

    def __repr__(self) -> str:
        """Return a concise string representation."""
        deps = ", ".join(self.depends_on) if self.depends_on else "none"
        return (
            f"StackPlan(name={self.name!r}, layer={self.layer!r}, "
            f"domain={self.domain!r}, depends_on=[{deps}])"
        )


@dataclass
class CompositionPlan:
    """A full decomposition of an intent into ordered stacks.

    Contains all stacks needed to fulfil the user's infrastructure intent,
    organized by layer with dependency information for correct ordering.
    """

    stacks: List[StackPlan] = field(default_factory=list)
    project_type: str = "terraform"
    needs_root_config: bool = True
    needs_common: bool = True

    @property
    def stack_count(self) -> int:
        """Return the total number of stacks in the plan."""
        return len(self.stacks)

    def get_stacks_by_layer(self, layer: str) -> List[StackPlan]:
        """Return all stacks belonging to the specified layer.

        Args:
            layer: One of foundation, platform, application, observability.

        Returns:
            List of StackPlan objects in the given layer.
        """
        return [s for s in self.stacks if s.layer == layer]

    def topological_order(self) -> List[StackPlan]:
        """Return stacks in dependency-resolved order (Kahn's algorithm).

        Stacks with no dependencies come first (foundation layer),
        followed by stacks whose dependencies have already been resolved.
        Ties within the same depth are broken by layer order, then name.

        Returns:
            List of StackPlan in topological (deployment) order.

        Raises:
            ValueError: If a circular dependency is detected.
        """
        if not self.stacks:
            return []

        # Build adjacency and in-degree maps by stack name
        name_to_stack: Dict[str, StackPlan] = {s.name: s for s in self.stacks}
        in_degree: Dict[str, int] = {s.name: 0 for s in self.stacks}
        dependents: Dict[str, List[str]] = {s.name: [] for s in self.stacks}

        for stack in self.stacks:
            for dep in stack.depends_on:
                if dep in name_to_stack:
                    in_degree[stack.name] += 1
                    dependents[dep].append(stack.name)

        # Initialize queue with zero in-degree nodes
        queue: deque = deque(
            sorted(
                [name for name, deg in in_degree.items() if deg == 0],
                key=lambda n: (
                    LAYER_ORDER.get(name_to_stack[n].layer, 99),
                    n,
                ),
            )
        )

        result: List[StackPlan] = []
        while queue:
            current = queue.popleft()
            result.append(name_to_stack[current])

            # Collect and sort newly available nodes for determinism
            newly_available: List[str] = []
            for dependent in dependents[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    newly_available.append(dependent)

            # Sort by layer order then name for stable output
            newly_available.sort(
                key=lambda n: (
                    LAYER_ORDER.get(name_to_stack[n].layer, 99),
                    n,
                )
            )
            queue.extend(newly_available)

        if len(result) != len(self.stacks):
            resolved = {s.name for s in result}
            unresolved = [s.name for s in self.stacks if s.name not in resolved]
            raise ValueError(f"Circular dependency detected among stacks: {unresolved}")

        return result

    def validate(self) -> List[str]:
        """Validate the composition plan for common issues.

        Returns:
            List of warning/error messages (empty if valid).
        """
        issues: List[str] = []
        valid_layers = set(LAYER_ORDER.keys())
        known_names = {s.name for s in self.stacks}

        for stack in self.stacks:
            if stack.layer not in valid_layers:
                issues.append(
                    f"Stack '{stack.name}' has invalid layer "
                    f"'{stack.layer}'. Must be one of: "
                    f"{', '.join(valid_layers)}"
                )

            for dep in stack.depends_on:
                if dep not in known_names:
                    issues.append(
                        f"Stack '{stack.name}' depends on unknown stack '{dep}'"
                    )

            # Check layer ordering consistency
            for dep in stack.depends_on:
                if dep in known_names:
                    dep_stack = next(s for s in self.stacks if s.name == dep)
                    dep_order = LAYER_ORDER.get(dep_stack.layer, 99)
                    self_order = LAYER_ORDER.get(stack.layer, 99)
                    if dep_order > self_order:
                        issues.append(
                            f"Stack '{stack.name}' ({stack.layer}) "
                            f"depends on '{dep}' ({dep_stack.layer}) "
                            f"which is in a higher layer"
                        )

        return issues
