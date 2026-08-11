"""Project assembler for multi-stack Intent-to-IaC composition.

Assembles a full project structure from a CompositionPlan, generating
root configuration, common files, and per-stack terragrunt.hcl with
dependency blocks. This is deterministic template generation — no AI calls.
"""

import logging
from typing import Dict, List

from .composition_models import CompositionPlan, StackPlan
from .models import GeneratedFile

logger = logging.getLogger(__name__)

# Realistic mock outputs by domain/stack name for dependency blocks
MOCK_OUTPUTS: Dict[str, Dict[str, str]] = {
    "vpc": {
        "vpc_id": "vpc-mock-12345",
        "vpc_cidr_block": "10.0.0.0/16",
        "private_subnet_ids": '["subnet-mock-priv-1", "subnet-mock-priv-2"]',
        "public_subnet_ids": '["subnet-mock-pub-1", "subnet-mock-pub-2"]',
        "database_subnet_ids": '["subnet-mock-db-1", "subnet-mock-db-2"]',
        "availability_zones": '["us-east-1a", "us-east-1b"]',
    },
    "security-groups": {
        "app_security_group_id": "sg-mock-app-12345",
        "db_security_group_id": "sg-mock-db-12345",
        "alb_security_group_id": "sg-mock-alb-12345",
    },
    "eks": {
        "cluster_name": "eks-mock-cluster",
        "cluster_endpoint": "https://mock-eks-endpoint.eks.amazonaws.com",
        "cluster_certificate_authority_data": "LS0tLS1CRUdJTi...",
        "cluster_security_group_id": "sg-mock-eks-12345",
        "oidc_provider_arn": "arn:aws:iam::123456789012:oidc-provider/mock",
    },
    "rds": {
        "db_instance_endpoint": "mock-db.123456789012.us-east-1.rds.amazonaws.com:5432",
        "db_instance_identifier": "mock-db-instance",
        "db_instance_arn": "arn:aws:rds:us-east-1:123456789012:db:mock-db",
        "db_security_group_id": "sg-mock-rds-12345",
    },
    "s3": {
        "bucket_id": "mock-bucket-12345",
        "bucket_arn": "arn:aws:s3:::mock-bucket-12345",
        "bucket_domain_name": "mock-bucket-12345.s3.amazonaws.com",
    },
    "kms": {
        "key_id": "mrk-mock-12345678",
        "key_arn": "arn:aws:kms:us-east-1:123456789012:key/mrk-mock-12345678",
        "alias_arn": "arn:aws:kms:us-east-1:123456789012:alias/mock-key",
    },
    "iam": {
        "role_arn": "arn:aws:iam::123456789012:role/mock-role",
        "role_name": "mock-role",
        "instance_profile_arn": "arn:aws:iam::123456789012:instance-profile/mock",
    },
    "alb": {
        "alb_arn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/mock/12345",
        "alb_dns_name": "mock-alb-123456.us-east-1.elb.amazonaws.com",
        "alb_zone_id": "Z35SXDOTRQ7X7K",
        "target_group_arn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/mock/12345",
    },
    "ecr": {
        "repository_url": "123456789012.dkr.ecr.us-east-1.amazonaws.com/mock-repo",
        "repository_arn": "arn:aws:ecr:us-east-1:123456789012:repository/mock-repo",
    },
    "cloudfront": {
        "distribution_id": "E1MOCK12345",
        "distribution_domain_name": "d1mock12345.cloudfront.net",
        "distribution_arn": "arn:aws:cloudfront::123456789012:distribution/E1MOCK12345",
    },
    "route53": {
        "zone_id": "Z1MOCK12345",
        "name_servers": '["ns-mock-1.awsdns-01.com", "ns-mock-2.awsdns-02.net"]',
    },
}

# Default mock output for stacks without specific mappings
DEFAULT_MOCK_OUTPUTS: Dict[str, str] = {
    "id": "mock-resource-id-12345",
    "arn": "arn:aws:service:us-east-1:123456789012:resource/mock-12345",
}


class ProjectAssembler:
    """Assemble a full project structure from a composition plan.

    Generates root configuration (root.hcl), common files, and per-stack
    terragrunt.hcl files with dependency blocks and input mappings.
    This is purely deterministic template generation.
    """

    def __init__(self, project_type: str = "terraform-terragrunt"):
        """Initialize the project assembler.

        Args:
            project_type: Target project type (default: terraform-terragrunt).
        """
        self.project_type = project_type
        self.logger = logging.getLogger(self.__class__.__name__)

    def assemble(
        self,
        plan: CompositionPlan,
        output_dir: str,
        existing_project: bool = False,
    ) -> List[GeneratedFile]:
        """Assemble full project structure from composition plan.

        Args:
            plan: The decomposed composition plan with stacks.
            output_dir: Target output directory path.
            existing_project: If True, skip root/common generation.

        Returns:
            List of GeneratedFile objects ready to be written.
        """
        files: List[GeneratedFile] = []

        # Generate root config if needed
        if plan.needs_root_config and not existing_project:
            files.extend(self._generate_root_config(plan))

        # Generate common/ if needed
        if plan.needs_common and not existing_project:
            files.extend(self._generate_common(plan))

        # Generate per-stack terragrunt.hcl files
        ordered_stacks = plan.topological_order()
        for stack in ordered_stacks:
            terragrunt_content = self.generate_terragrunt_hcl(stack, ordered_stacks)
            files.append(
                GeneratedFile(
                    path=f"{stack.path}/terragrunt.hcl",
                    content=terragrunt_content,
                )
            )

        self.logger.info(
            "Assembled %d files for %d stacks (project_type=%s)",
            len(files),
            plan.stack_count,
            self.project_type,
        )
        return files

    def generate_terragrunt_hcl(
        self, stack: StackPlan, all_stacks: List[StackPlan]
    ) -> str:
        """Generate terragrunt.hcl for a stack with dependency blocks.

        Produces a complete terragrunt.hcl with:
        - include "root" block pointing to root.hcl
        - dependency blocks for each depends_on reference
        - inputs mapping dependency outputs to variables

        Args:
            stack: The stack to generate configuration for.
            all_stacks: All stacks in the plan (for resolving dependencies).

        Returns:
            Complete terragrunt.hcl content as string.
        """
        lines: List[str] = []

        # include "root" block
        lines.append('include "root" {')
        lines.append('  path = find_in_parent_folders("root.hcl")')
        lines.append("}")
        lines.append("")

        # Resolve dependency stacks
        dep_stacks = self._resolve_dependencies(stack, all_stacks)

        # dependency blocks
        for dep in dep_stacks:
            lines.append(f'dependency "{dep.name}" {{')
            lines.append(f'  config_path = "../../../{dep.path}"')
            lines.append("")

            # Mock outputs
            mock_outputs = self._get_mock_outputs(dep.name)
            lines.append("  mock_outputs = {")
            for key, value in mock_outputs.items():
                # Determine if value needs quoting
                if value.startswith("[") or value.startswith("{"):
                    lines.append(f"    {key} = {value}")
                else:
                    lines.append(f'    {key} = "{value}"')
            lines.append("  }")
            lines.append("")
            lines.append('  mock_outputs_merge_strategy_with_state = "shallow"')
            lines.append("}")
            lines.append("")

        # terraform source block
        if stack.module_source:
            lines.append("terraform {")
            lines.append(f'  source = "{stack.module_source}"')
            lines.append("}")
            lines.append("")

        # inputs block
        lines.append("inputs = {")
        input_lines = self._generate_inputs(stack, dep_stacks)
        for input_line in input_lines:
            lines.append(f"  {input_line}")
        lines.append("}")
        lines.append("")

        return "\n".join(lines)

    def _generate_root_config(self, plan: CompositionPlan) -> List[GeneratedFile]:
        """Generate root.hcl with remote_state and provider generate blocks.

        Args:
            plan: The composition plan for project metadata.

        Returns:
            List with a single GeneratedFile for root.hcl.
        """
        content = """\
# Root configuration for Terragrunt
# Generated by ThothCTL Intent-to-IaC

locals {
  project_name = "my-project"
  aws_region   = "us-east-1"
  environment  = "dev"
}

remote_state {
  backend = "s3"

  config = {
    bucket         = "${local.project_name}-${local.environment}-tfstate"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.aws_region
    encrypt        = true
    dynamodb_table = "${local.project_name}-${local.environment}-tflock"

    s3_bucket_tags = {
      Project     = local.project_name
      Environment = local.environment
      ManagedBy   = "terragrunt"
    }
  }

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"

  contents = <<EOF
provider "aws" {
  region = "${local.aws_region}"

  default_tags {
    tags = {
      Project     = "${local.project_name}"
      Environment = "${local.environment}"
      ManagedBy   = "terragrunt"
    }
  }
}
EOF
}
"""
        self.logger.debug("Generated root.hcl")
        return [GeneratedFile(path="root.hcl", content=content)]

    def _generate_common(self, plan: CompositionPlan) -> List[GeneratedFile]:
        """Generate common/common.hcl and common/common.tfvars.

        Args:
            plan: The composition plan for project metadata.

        Returns:
            List of GeneratedFile objects for common directory.
        """
        common_hcl = """\
# Common configuration shared across all stacks
# Generated by ThothCTL Intent-to-IaC

locals {
  common_vars = read_terragrunt_config(
    find_in_parent_folders("common/common.tfvars")
  )

  project_name = local.common_vars.locals.project_name
  environment  = local.common_vars.locals.environment
  aws_region   = local.common_vars.locals.aws_region
  owner        = local.common_vars.locals.owner
}
"""

        common_tfvars = """\
# Common variables for all stacks
# Generated by ThothCTL Intent-to-IaC

locals {
  project_name = "my-project"
  environment  = "dev"
  aws_region   = "us-east-1"
  owner        = "platform-team"
}
"""

        self.logger.debug("Generated common/ files")
        return [
            GeneratedFile(path="common/common.hcl", content=common_hcl),
            GeneratedFile(path="common/common.tfvars", content=common_tfvars),
        ]

    def _resolve_dependencies(
        self, stack: StackPlan, all_stacks: List[StackPlan]
    ) -> List[StackPlan]:
        """Resolve dependency names to StackPlan objects.

        Args:
            stack: The stack whose dependencies to resolve.
            all_stacks: All available stacks.

        Returns:
            List of StackPlan objects that this stack depends on.
        """
        name_to_stack = {s.name: s for s in all_stacks}
        resolved = []
        for dep_name in stack.depends_on:
            if dep_name in name_to_stack:
                resolved.append(name_to_stack[dep_name])
            else:
                self.logger.warning(
                    "Stack '%s' depends on unknown stack '%s'",
                    stack.name,
                    dep_name,
                )
        return resolved

    def _get_mock_outputs(self, stack_name: str) -> Dict[str, str]:
        """Get realistic mock outputs for a dependency stack.

        Args:
            stack_name: Name of the dependency stack.

        Returns:
            Dict of output_name -> mock_value.
        """
        # Try exact match first
        if stack_name in MOCK_OUTPUTS:
            return MOCK_OUTPUTS[stack_name]

        # Try partial match (e.g., "my-vpc" matches "vpc")
        for key, outputs in MOCK_OUTPUTS.items():
            if key in stack_name or stack_name.endswith(f"-{key}"):
                return outputs

        # Fallback to generic defaults
        return DEFAULT_MOCK_OUTPUTS

    def _generate_inputs(
        self, stack: StackPlan, dep_stacks: List[StackPlan]
    ) -> List[str]:
        """Generate input mappings from dependency outputs.

        Creates input lines that map dependency outputs to the current
        stack's input variables using dependency.<name>.outputs.<key> syntax.

        Args:
            stack: The current stack.
            dep_stacks: Resolved dependency stacks.

        Returns:
            List of HCL input assignment strings.
        """
        input_lines: List[str] = []

        for dep in dep_stacks:
            mock_outputs = self._get_mock_outputs(dep.name)
            for output_key in mock_outputs:
                input_lines.append(
                    f"{output_key} = dependency.{dep.name}.outputs.{output_key}"
                )

        # If no dependencies, add a comment placeholder
        if not input_lines:
            input_lines.append("# Add stack-specific inputs here")

        return input_lines
