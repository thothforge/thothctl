"""Known fix patterns for common Checkov/KICS/Trivy findings.

Used as fallback when AI is unavailable or budget is exceeded.
"""
from typing import Dict, Optional

# Map check_id → fix generator function
_PATTERNS: Dict[str, Dict] = {
    # S3
    "CKV_AWS_18": {
        "description": "Enable S3 bucket access logging",
        "fix_type": "add_attribute",
        "attribute": "logging",
        "template": '  logging {{\n    target_bucket = "{bucket}_logs"\n  }}',
    },
    "CKV_AWS_19": {
        "description": "Enable S3 bucket encryption (AES256)",
        "fix_type": "add_resource",
        "template": (
            'resource "aws_s3_bucket_server_side_encryption_configuration" "{name}" {{\n'
            '  bucket = aws_s3_bucket.{name}.id\n'
            '  rule {{\n'
            '    apply_server_side_encryption_by_default {{\n'
            '      sse_algorithm = "AES256"\n'
            '    }}\n'
            '  }}\n'
            '}}'
        ),
    },
    "CKV_AWS_21": {
        "description": "Enable S3 bucket versioning",
        "fix_type": "add_resource",
        "template": (
            'resource "aws_s3_bucket_versioning" "{name}" {{\n'
            '  bucket = aws_s3_bucket.{name}.id\n'
            '  versioning_configuration {{\n'
            '    status = "Enabled"\n'
            '  }}\n'
            '}}'
        ),
    },
    "CKV_AWS_145": {
        "description": "Enable S3 bucket encryption with KMS",
        "fix_type": "add_resource",
        "template": (
            'resource "aws_s3_bucket_server_side_encryption_configuration" "{name}" {{\n'
            '  bucket = aws_s3_bucket.{name}.id\n'
            '  rule {{\n'
            '    apply_server_side_encryption_by_default {{\n'
            '      sse_algorithm = "aws:kms"\n'
            '    }}\n'
            '  }}\n'
            '}}'
        ),
    },
    # Security Groups
    "CKV_AWS_23": {
        "description": "Add description to security group",
        "fix_type": "modify_attribute",
        "attribute": "description",
        "value": '"Managed by Terraform"',
    },
    "CKV_AWS_24": {
        "description": "Restrict SSH ingress to specific CIDR",
        "fix_type": "modify_attribute",
        "attribute": "cidr_blocks",
        "find": '"0.0.0.0/0"',
        "value": 'var.allowed_ssh_cidrs',
    },
    "CKV_AWS_25": {
        "description": "Restrict RDP ingress to specific CIDR",
        "fix_type": "modify_attribute",
        "attribute": "cidr_blocks",
        "find": '"0.0.0.0/0"',
        "value": 'var.allowed_rdp_cidrs',
    },
    # RDS
    "CKV_AWS_16": {
        "description": "Enable RDS encryption at rest",
        "fix_type": "add_attribute",
        "attribute": "storage_encrypted",
        "value": "true",
    },
    "CKV_AWS_17": {
        "description": "Ensure RDS is not publicly accessible",
        "fix_type": "modify_attribute",
        "attribute": "publicly_accessible",
        "value": "false",
    },
    # CloudWatch / Logging
    "CKV_AWS_158": {
        "description": "Enable CloudWatch Log Group encryption",
        "fix_type": "add_attribute",
        "attribute": "kms_key_id",
        "value": "var.cloudwatch_kms_key_id",
    },
    # EBS
    "CKV_AWS_3": {
        "description": "Enable EBS volume encryption",
        "fix_type": "add_attribute",
        "attribute": "encrypted",
        "value": "true",
    },
    # Lambda
    "CKV_AWS_116": {
        "description": "Add Lambda dead letter config",
        "fix_type": "add_attribute",
        "attribute": "dead_letter_config",
        "template": '  dead_letter_config {{\n    target_arn = var.dlq_arn\n  }}',
    },
    "CKV_AWS_272": {
        "description": "Enable Lambda code signing",
        "fix_type": "add_attribute",
        "attribute": "code_signing_config_arn",
        "value": "var.code_signing_config_arn",
    },
}


def get_pattern_fix(check_id: str, finding: Dict, code_files: Dict) -> Optional[Dict]:
    """Look up a known fix pattern for a check ID.

    Returns a fix dict or None if no pattern exists.
    """
    pattern = _PATTERNS.get(check_id)
    if not pattern:
        return None

    resource = finding.get("resource", "")
    file_path = finding.get("file", "")

    # Extract resource name from "aws_s3_bucket.my_bucket" format
    name = resource.split(".")[-1] if "." in resource else resource

    fix = {
        "finding_id": check_id,
        "file": file_path,
        "fix_type": pattern["fix_type"],
        "severity": finding.get("severity", "MEDIUM"),
        "description": pattern["description"],
        "original": "",
        "replacement": "",
        "validation": f"Run: checkov -f {file_path} --check {check_id}",
    }

    if pattern["fix_type"] == "add_resource":
        fix["replacement"] = pattern["template"].format(name=name)
        fix["original"] = f"# Add after resource definition for {resource}"
    elif pattern["fix_type"] == "add_attribute":
        attr = pattern["attribute"]
        value = pattern.get("value", "")
        tmpl = pattern.get("template")
        if tmpl:
            fix["replacement"] = tmpl.format(name=name)
        else:
            fix["replacement"] = f"  {attr} = {value}"
        fix["original"] = f"# Add to {resource}"
    elif pattern["fix_type"] == "modify_attribute":
        attr = pattern["attribute"]
        find = pattern.get("find", "")
        value = pattern.get("value", "")
        if find:
            fix["original"] = f"  {attr} = [{find}]"
            fix["replacement"] = f"  {attr} = [{value}]"
        else:
            fix["replacement"] = f'  {attr} = {value}'
            fix["original"] = f"# Modify {attr} in {resource}"

    return fix


def list_supported_checks() -> list:
    """Return list of check IDs with known fix patterns."""
    return [{"check_id": k, "description": v["description"]} for k, v in _PATTERNS.items()]
