# config/validation.py
from typing import Any, Dict

from pydantic import BaseModel, Field


class ProjectProperties(BaseModel):
    """Validation schema for project properties."""

    deployment_region: str = Field(..., regex=r"^[a-z]{2}-[a-z]+-\d$")
    dynamodb_backend: str
    backend_region: str
    backend_bucket: str
    owner: str
    client: str
    environment: str = Field(..., regex=r"^(dev|staging|prod)$")
    project: str


class ConfigValidator:
    """Validates configuration values."""

    @staticmethod
    def validate_project_properties(props: Dict[str, Any]) -> Dict[str, str]:
        """Validate project properties against schema."""
        validated = ProjectProperties(**props)
        return validated.dict()
