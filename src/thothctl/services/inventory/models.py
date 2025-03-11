"""Data models for inventory management."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


class RegistryType(Enum):
    """Supported registry types."""

    TERRAFORM = "terraform"
    GITHUB = "github"
    UNKNOWN = "unknown"


@dataclass
class Component:
    """Individual component information."""

    type: str
    name: str
    version: List[str]
    source: List[str]
    file: str
    latest_version: str = "Null"
    source_url: str = "Null"
    status: str = "Null"


@dataclass
class ComponentGroup:
    """Group of components with their path."""

    stack: str
    components: List[Component]


@dataclass
class Inventory:
    """Complete inventory information."""

    project_name: str
    components: List[ComponentGroup]
    version: int = 2

    def to_dict(self) -> Dict[str, Any]:
        """Convert inventory to dictionary format."""
        return {
            "version": self.version,
            "projectName": self.project_name,
            "components": [
                {
                    "path": group.stack,
                    "components": [
                        {
                            "type": comp.type,
                            "name": comp.name,
                            "version": comp.version,
                            "source": comp.source,
                            "file": comp.file,
                            "latest_version": comp.latest_version,
                            "source_url": comp.source_url,
                            "status": comp.status,
                        }
                        for comp in group.components
                    ],
                }
                for group in self.components
            ],
        }
