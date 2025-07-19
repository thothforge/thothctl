"""project_defaults.py.

Define default values for project properties.
These properties are using as default metadata values for templates and projects
"""
g_project_properties_parse = {
    "deployment_region": "us-east-2",
    "dynamodb_table": "db-terraform-lock",
    "backend_region": "us-east-2",
    "backend_bucket": "test-wrapper-tfstate",
    "owner": "thothctl",
    "client": "thothctl",
    "environment": "dev",
    "project": "test-wrapper",
}
g_project_properties = {
    "deployment_region": "us-east-1",
    "dynamodb_backend": "db-lock",
    "backend_region": "us-east-1",
    "backend_bucket": "bucket-us-east-1",
    "owner": "me",
    "client": "client_name",
    "environment": "dev",
    "project": "lab",
}

g_catalog_tags = [
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

g_catalog_spec = {
    "lifecycle": "production",
    "owner": "IaCPlatform",
    "system": "IaCPlatform",
    "type": "template",
}
