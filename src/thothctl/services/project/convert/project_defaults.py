"""project_defaults.py.

Define default values for project properties.
These properties are using as default metadata values for templates and projects
"""
g_project_properties_parse = {
    "deployment_region": "#{deployment_region}#",
    "dynamodb_table": "#{backend_dynamodb}#",
    "backend_region": "#{backend_region}#",
    "backend_bucket": "#{backend_bucket}#",
    "owner": "#{owner}#",
    "client": "#{client}#",
    "environment": "#{environment}#",
    "project": "#{project}#",
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
