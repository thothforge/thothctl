"""Data models for inventory management."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class RegistryType(Enum):
    """Supported registry types."""

    TERRAFORM = "terraform"
    GITHUB = "github"
    UNKNOWN = "unknown"


class ProjectType(Enum):
    """Supported project types."""
    
    TERRAFORM = "terraform"
    TERRAGRUNT = "terragrunt"


@dataclass
class Provider:
    """Provider information."""
    
    name: str
    version: str
    source: str = "Null"
    module: str = ""  # Empty string for providers at the root level
    component: str = ""  # The specific component using this provider
    latest_version: str = "Null"  # Latest available version
    source_url: str = "Null"  # Source URL for the provider
    status: str = "Unknown"  # Version status (Current, Outdated, Unknown)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "module": self.module,
            "component": self.component,
            "latest_version": self.latest_version,
            "source_url": self.source_url,
            "status": self.status,
        }


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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "file": self.file,
            "latest_version": self.latest_version,
            "source_url": self.source_url,
            "status": self.status,
        }


@dataclass
class ComponentGroup:
    """Group of components with their path."""

    stack: str
    components: List[Component]
    providers: List[Provider] = None
    
    def __post_init__(self):
        if self.providers is None:
            self.providers = []
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stack": self.stack,
            "components": [component.to_dict() for component in self.components],
            "providers": [provider.to_dict() for provider in self.providers] if self.providers else [],
        }


@dataclass
class Inventory:
    """Complete inventory information."""

    project_name: str
    components: List[ComponentGroup]
    project_type: str = "terraform"
    version: int = 2
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert inventory to dictionary format."""
        return {
            "version": self.version,
            "projectName": self.project_name,
            "projectType": self.project_type,
            "components": [
                {
                    "stack": group.stack,
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
                    "providers": [
                        {
                            "name": provider.name,
                            "version": provider.version,
                            "source": provider.source,
                            "module": provider.module,
                            "component": provider.component,
                            "latest_version": provider.latest_version,
                            "source_url": provider.source_url,
                            "status": provider.status,                        }
                        for provider in group.providers
                    ] if group.providers else []
                }
                for group in self.components
            ],
        }
