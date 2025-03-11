# config/default_values.py
"""Default values used across the application."""

from typing import Dict, Final, List


DEFAULT_PROPERTIES_PARSE: Final[Dict[str, str]] = {
    "deployment_region": "#{deployment_region}#",
    "dynamodb_table": "#{backend_dynamodb}#",
    "backend_region": "#{backend_region}#",
    "backend_bucket": "#{backend_bucket}#",
    "owner": "#{owner}#",
    "client": "#{client}#",
    "environment": "#{environment}#",
    "project": "#{project}#",
}

DEFAULT_PROPERTIES: Final[Dict[str, str]] = {
    "deployment_region": "us-east-1",
    "dynamodb_backend": "db-lock",
    "backend_region": "us-east-1",
    "backend_bucket": "XXXXXXXXXXXXXXXX",
    "owner": "me",
    "client": "client_name",
    "environment": "dev",
    "project": "lab",
}

DEFAULT_CATALOG_TAGS: Final[List[str]] = [
    "devops",
    "devsecops",
    "iac",
    "terraform",
    "terragrunt",
    "module",
    "aws",
    "cloud",
    "automation",
    "template",
]

DEFAULT_CATALOG_SPEC: Final[Dict[str, str]] = {
    "lifecycle": "production",
    "owner": "IaCPlatform",
    "system": "IaCPlatform",
    "type": "template",
}
