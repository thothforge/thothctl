"""Data models for Intent-to-IaC generation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ProjectType(Enum):
    """Supported IaC project types for generation."""

    TERRAFORM = "terraform"
    TERRAFORM_TERRAGRUNT = "terraform-terragrunt"
    TERRAGRUNT = "terragrunt"
    CLOUDFORMATION = "cloudformation"
    CDKV2 = "cdkv2"
    AUTO = "auto"


@dataclass
class GeneratedFile:
    """A single file produced by the generation pipeline."""

    path: str  # Relative path (e.g., "stacks/foundation/network/vpc/main.tf")
    content: str  # Full file content


@dataclass
class GenerationOutput:
    """Raw output from the AI code generator."""

    files: List[GeneratedFile] = field(default_factory=list)
    explanation: str = ""
    modules_used: List[str] = field(default_factory=list)
    estimated_resources: List[str] = field(default_factory=list)
    raw_response: Optional[str] = None

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_lines(self) -> int:
        return sum(
            content.count("\n") + 1 for f in self.files for content in [f.content]
        )


@dataclass
class Violation:
    """A single validation violation from Checkov or OPA."""

    check_id: str  # e.g., "CKV_AWS_130"
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    resource: str  # e.g., "aws_vpc.main"
    message: str  # Human-readable description
    file_path: str = ""  # File where violation was found
    tool: str = "checkov"  # "checkov" or "opa"


@dataclass
class ValidationResult:
    """Result of validating generated code against Checkov + OPA."""

    passed: bool
    violations: List[Violation] = field(default_factory=list)
    checkov_passed: int = 0
    checkov_failed: int = 0
    opa_passed: int = 0
    opa_failed: int = 0

    @property
    def total_violations(self) -> int:
        return len(self.violations)

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "CRITICAL")

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "HIGH")

    def format_for_ai(self) -> str:
        """Format violations as structured text for AI self-correction.

        Groups by severity and provides actionable fix hints so the AI
        can make surgical edits instead of rewriting entire files.
        """
        if not self.violations:
            return "No violations found."

        lines = []
        lines.append(
            f"VALIDATION FAILED: {self.total_violations} violation(s) "
            f"({self.critical_count} critical, {self.high_count} high)\n"
        )

        # Group by tool for clarity
        framework_violations = [v for v in self.violations if v.tool == "framework"]
        plan_violations = [v for v in self.violations if v.tool == "plan"]
        security_violations = [v for v in self.violations if v.tool == "checkov"]
        policy_violations = [v for v in self.violations if v.tool == "opa"]

        if framework_violations:
            lines.append("## SCHEMA/SYNTAX ERRORS (fix these first!):")
            for v in framework_violations:
                lines.append(
                    f"  - [{v.severity}] {v.check_id}"
                    f"{' in ' + v.file_path if v.file_path else ''}"
                    f"{' (resource: ' + v.resource + ')' if v.resource else ''}"
                    f"\n    Error: {v.message}"
                    f"\n    Fix: Correct the syntax/schema error. Check resource "
                    f"types, required attributes, and references."
                )

        if plan_violations:
            lines.append("\n## PLAN/DEPLOYABILITY ERRORS (fix after schema errors):")
            for v in plan_violations:
                fix_hint = self._get_plan_fix_hint(v.message)
                lines.append(
                    f"  - [{v.severity}] {v.check_id}"
                    f"{' in ' + v.file_path if v.file_path else ''}"
                    f"{' (resource: ' + v.resource + ')' if v.resource else ''}"
                    f"\n    Error: {v.message}"
                    f"\n    Fix: {fix_hint}"
                )

        if security_violations:
            lines.append("\n## SECURITY VIOLATIONS:")
            for v in security_violations:
                fix_hint = self._get_fix_hint(v.check_id)
                lines.append(
                    f"  - [{v.severity}] {v.check_id}: {v.message}"
                    f"{' (resource: ' + v.resource + ')' if v.resource else ''}"
                    f"\n    Fix: {fix_hint}"
                )

        if policy_violations:
            lines.append("\n## POLICY VIOLATIONS:")
            for v in policy_violations:
                lines.append(
                    f"  - [{v.severity}] {v.check_id}: {v.message}"
                    f"{' (resource: ' + v.resource + ')' if v.resource else ''}"
                    f"\n    Fix: Add/modify the resource to comply with "
                    f"organizational policy."
                )

        lines.append(
            "\n## INSTRUCTIONS:"
            "\n1. Fix ALL schema/syntax errors first (code won't deploy otherwise)"
            "\n2. Then fix CRITICAL and HIGH security violations"
            "\n3. Do NOT remove resources — only add missing configurations"
            "\n4. Keep existing naming, tags, and structure intact"
        )

        return "\n".join(lines)

    @staticmethod
    def _get_fix_hint(check_id: str) -> str:
        """Return a concise fix hint for common Checkov check IDs."""
        hints = {
            "CKV_AWS_130": "Add aws_flow_log resource for VPC flow logs",
            "CKV_AWS_178": "Use one NAT gateway per AZ for high availability",
            "CKV_AWS_260": "Add 'description' field to security group rules",
            "CKV2_AWS_11": "Enable VPC flow logs (aws_flow_log resource)",
            "CKV_AWS_145": "Add server_side_encryption_configuration block",
            "CKV_AWS_18": "Add logging block to S3 bucket",
            "CKV_AWS_144": "Add replication_configuration to S3 bucket",
            "CKV_AWS_23": "Add 'description' field to security group",
            "CKV_AWS_19": "Add server_side_encryption_configuration with AES256 or aws:kms",
            "CKV_AWS_21": "Add versioning { enabled = true } to S3 bucket",
            "CKV_AWS_57": "Set acl to 'private' (not 'public-read')",
            "CKV_AWS_79": "Enable IMDSv2: metadata_options { http_tokens = 'required' }",
            "CKV_AWS_88": "Set associate_public_ip_address = false on EC2 instances",
            "CKV_AWS_8": "Set storage_encrypted = true on RDS instance",
            "CKV_AWS_16": "Set multi_az = true on RDS instance",
            "CKV_AWS_17": "Set enabled_cloudwatch_logs_exports on RDS",
            "CKV_AWS_157": "Set deletion_protection = true on RDS",
        }
        return hints.get(check_id, "Add missing security configuration")

    @staticmethod
    def _get_plan_fix_hint(error_message: str) -> str:
        """Return a fix hint based on plan error message patterns.

        Plan errors are provider-specific and not mapped to IDs like Checkov.
        We pattern-match the error message to provide actionable guidance.
        """
        msg_lower = error_message.lower()

        # Instance type errors
        if "instance type" in msg_lower or "instance_type" in msg_lower:
            return (
                "Use a valid instance type for the region. "
                "Common types: t3.micro, t3.small, m5.large, r5.large"
            )

        # AZ availability
        if "availability zone" in msg_lower or "not available" in msg_lower:
            return (
                "The specified resource configuration is not available in this AZ. "
                "Try a different AZ or instance type."
            )

        # Missing required attribute
        if "required" in msg_lower and ("attribute" in msg_lower or "argument" in msg_lower):
            return "Add the missing required attribute to the resource block."

        # Reference errors
        if "reference" in msg_lower or "not found" in msg_lower:
            return (
                "Fix the resource reference. Ensure the target resource exists "
                "and the attribute name is correct (e.g., .id, .arn, .name)."
            )

        # Security group
        if "security_group" in msg_lower:
            return (
                "Check security group configuration. Ensure security_group_id "
                "references an existing group or use self/source_security_group_id."
            )

        # CIDR / networking
        if "cidr" in msg_lower or "invalid cidr" in msg_lower:
            return "Use valid CIDR notation (e.g., 10.0.0.0/16, 10.0.1.0/24)."

        # Duplicate resource
        if "already exists" in msg_lower or "duplicate" in msg_lower:
            return "Resource name conflicts with existing infrastructure. Use a unique name."

        # Dependency / cycle
        if "cycle" in msg_lower or "circular" in msg_lower:
            return "Break the circular dependency between resources. Use depends_on explicitly."

        # IAM
        if "iam" in msg_lower and ("policy" in msg_lower or "role" in msg_lower):
            return "Check IAM policy/role configuration. Ensure valid JSON policy document."

        # Generic
        return (
            "Review the resource configuration against the provider documentation. "
            "Fix the specific attribute or reference mentioned in the error."
        )


@dataclass
class IntentResult:
    """Final result of the Intent-to-IaC pipeline."""

    success: bool
    files: List[GeneratedFile] = field(default_factory=list)
    validation: Optional[ValidationResult] = None
    iterations: int = 1
    explanation: str = ""
    modules_used: List[str] = field(default_factory=list)
    estimated_resources: List[str] = field(default_factory=list)
    context_tokens: int = 0
    generation_tokens: int = 0
    error: Optional[str] = None
    diagram: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "files": [{"path": f.path, "content": f.content} for f in self.files],
            "validation": {
                "passed": self.validation.passed,
                "violations": len(self.validation.violations),
            }
            if self.validation
            else None,
            "iterations": self.iterations,
            "explanation": self.explanation,
            "modules_used": self.modules_used,
            "estimated_resources": self.estimated_resources,
            "context_tokens": self.context_tokens,
            "generation_tokens": self.generation_tokens,
            "diagram": self.diagram,
            "error": self.error,
        }


@dataclass
class ContextPayload:
    """Compiled organizational context for AI injection."""

    project_type: str = "terraform"
    project_config: str = ""  # From .thothcf.toml
    iac_rules: str = ""  # From steering/rules docs
    project_overview: str = ""  # From product.md / CLAUDE.md
    existing_patterns: str = ""  # Sample files from project
    org_policies: str = ""  # OPA/Rego policy summaries
    total_tokens_estimate: int = 0

    def compile(self) -> str:
        """Compile all sections into a single context string for prompt injection."""
        sections = []

        if self.project_config:
            sections.append(f"## Project Configuration\n{self.project_config}")

        if self.iac_rules:
            sections.append(f"## IaC Rules & Conventions\n{self.iac_rules}")

        if self.project_overview:
            sections.append(f"## Project Overview\n{self.project_overview}")

        if self.existing_patterns:
            sections.append(
                f"## Existing Patterns (from this project)\n{self.existing_patterns}"
            )

        if self.org_policies:
            sections.append(f"## Organization Policies (OPA)\n{self.org_policies}")

        compiled = "# Organizational Context\n\n" + "\n\n".join(sections)
        self.total_tokens_estimate = len(compiled) // 4  # ~4 chars per token estimate
        return compiled


# ============================================================
# Plan Validation Models (Phase 1.10)
# ============================================================


class PlanMode(Enum):
    """Plan validation execution modes."""

    DISABLED = "disabled"
    PER_STACK = "per-stack"
    FULL_PROJECT = "full-project"
    TERRAFORM = "terraform"


@dataclass
class PlanContext:
    """Execution context for plan validation.

    Determines HOW and WHERE plan runs:
    - For terragrunt: in-place in the project directory (terragrunt handles backend/provider)
    - For terraform: in a temp workspace with backend configured
    """

    mode: PlanMode
    work_dir: str  # Directory where plan will execute
    project_type: str  # "terraform-terragrunt", "terragrunt", "terraform"
    stack_path: str = ""  # Relative stack path (for terragrunt per-stack)
    is_in_place: bool = False  # True if files are written to real project dir
    written_files: List[str] = field(default_factory=list)  # For rollback tracking


@dataclass
class StateConfig:
    """Resolved state backend configuration."""

    backend_type: str = "none"  # "s3", "local", "gcs", "azurerm", "none"
    config: Dict[str, str] = field(default_factory=dict)
    existing: bool = False  # Whether there's existing state to read


@dataclass
class PlanResult:
    """Result of a plan validation execution."""

    violations: List["Violation"] = field(default_factory=list)
    plan_succeeded: bool = False
    resources_to_create: int = 0
    resources_to_update: int = 0
    resources_to_destroy: int = 0
    execution_time_seconds: float = 0.0
    skipped: bool = False
    skip_reason: str = ""

    @property
    def has_errors(self) -> bool:
        """True if plan found blocking errors."""
        return any(v.severity in ("CRITICAL", "HIGH") for v in self.violations)

    def to_violations(self) -> List["Violation"]:
        """Return violations list (for integration with GenerationValidator)."""
        return self.violations
