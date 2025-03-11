# config/defaults.py
from dataclasses import dataclass, field
from typing import Dict, List

from .default_values import (
    DEFAULT_CATALOG_SPEC,
    DEFAULT_CATALOG_TAGS,
    DEFAULT_PROPERTIES,
    DEFAULT_PROPERTIES_PARSE,
)


@dataclass(frozen=True)
class ProjectDefaults:
    """Default project configuration values."""

    properties_parse: Dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_PROPERTIES_PARSE)
    )
    properties: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_PROPERTIES))
    catalog_tags: List[str] = field(default_factory=lambda: list(DEFAULT_CATALOG_TAGS))
    catalog_spec: Dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_CATALOG_SPEC)
    )

    def __post_init__(self):
        """Validate the default values after initialization."""
        for key, value in self.properties_parse.items():
            if not isinstance(value, str):
                raise ValueError(f"Property parse value for {key} must be a string")

        for key, value in self.properties.items():
            if not isinstance(value, str):
                raise ValueError(f"Property value for {key} must be a string")

        if not all(isinstance(tag, str) for tag in self.catalog_tags):
            raise ValueError("All catalog tags must be strings")

        for key, value in self.catalog_spec.items():
            if not isinstance(value, str):
                raise ValueError(f"Catalog spec value for {key} must be a string")
