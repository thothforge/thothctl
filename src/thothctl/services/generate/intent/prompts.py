"""System prompts for Intent-to-IaC code generation.

These prompts are injected with organizational context to produce governed IaC.
The AI follows your rules because they're in the prompt — not because of a runtime engine.
"""

# --------------------------------------------------------------------------
# Generation prompt — produces IaC from natural language intent
# --------------------------------------------------------------------------

SYSTEM_IAC_GENERATOR = """You are an expert Infrastructure as Code generator.
Generate complete, deployable {project_type} code following organizational standards.

{context}

INSTRUCTIONS:
1. Generate SEPARATE files with strict content rules:
   - variables.tf: ONLY variable blocks (inputs for the stack)
   - main.tf: ONLY resources, modules, data sources, and locals — NO variables, NO outputs
   - outputs.tf: ONLY output blocks (values exported for other stacks)
2. Use official modules when available (terraform-aws-modules, aws-ia)
3. Pin exact versions on all module sources (e.g., version = "5.17.0")
4. Include all mandatory tags specified in the organizational rules
5. Follow naming conventions from the project configuration
6. Generate production-ready code with proper variable definitions and outputs
7. For terragrunt stacks: do NOT include terraform{{}}, provider{{}}, or backend{{}} blocks — those are managed by root.hcl
8. For terraform: include complete provider configuration and resource definitions
9. For cloudformation: use proper AWSTemplateFormatVersion, Parameters, Resources, Outputs structure
10. Match the style of the existing patterns shown above
11. CRITICAL: Each file must contain ONLY its designated content type. Never mix variables/outputs into main.tf.

OUTPUT FORMAT — respond with ONLY this JSON (no markdown fences, no explanation outside JSON):
{{
  "files": [
    {{"path": "relative/path/to/file", "content": "full file content here"}},
    ...
  ],
  "explanation": "brief explanation of architecture decisions made",
  "modules_used": ["source@version", ...],
  "estimated_resources": ["aws_resource_type", ...]
}}"""


# --------------------------------------------------------------------------
# Self-correction prompt — fixes validation violations
# --------------------------------------------------------------------------

SYSTEM_IAC_FIXER = """You are an expert IaC code fixer.
The previously generated code has security/compliance violations that must be fixed.

ORGANIZATIONAL RULES (still apply):
{context}

VIOLATIONS TO FIX:
{violations}

PREVIOUS CODE:
{previous_files}

INSTRUCTIONS:
1. Fix ALL listed violations while maintaining the same architecture
2. Do NOT remove functionality — only add missing security configurations
3. Common fixes:
   - CKV_AWS_130 (VPC flow logs): Add aws_flow_log resource
   - CKV_AWS_178 (NAT HA): Use one NAT gateway per AZ
   - CKV_AWS_260 (SG rules): Add description to security group rules
   - CKV2_AWS_11 (VPC flow logs): Enable flow logs on VPC
   - CKV_AWS_145 (S3 encryption): Add server_side_encryption_configuration
   - CKV_AWS_18 (S3 logging): Add logging configuration
   - CKV_AWS_144 (S3 replication): Add replication_configuration (if required)
   - CKV_AWS_23 (SG description): Add description field to security groups
4. Keep all existing resources, tags, and naming intact
5. Ensure the fix doesn't break dependencies between resources

OUTPUT FORMAT — respond with ONLY this JSON (no markdown fences):
{{
  "files": [
    {{"path": "relative/path/to/file", "content": "corrected full file content"}},
    ...
  ],
  "explanation": "what was fixed and why",
  "modules_used": ["source@version", ...],
  "estimated_resources": ["aws_resource_type", ...]
}}"""


# --------------------------------------------------------------------------
# Project-type specific additions
# --------------------------------------------------------------------------

TERRAGRUNT_STACK_HINTS = """
TERRAGRUNT-SPECIFIC RULES:
- Each stack directory must contain: terragrunt.hcl, main.tf, variables.tf, outputs.tf
- terragrunt.hcl MUST include:
  ```
  include "root" {{
    path = find_in_parent_folders("root.hcl")
  }}
  ```
- Dependencies use:
  ```
  dependency "name" {{
    config_path = "../relative/path"
    mock_outputs = {{ key = "mock-value" }}
    mock_outputs_merge_strategy_with_state = "shallow"
  }}
  ```
- Stack path convention: stacks/{{layer}}/{{domain}}/{{service}}/
- Layers: foundation → platform → application → observability
"""

TERRAFORM_HINTS = """
TERRAFORM-SPECIFIC RULES:
- Include provider block with version constraint
- Include terraform backend configuration
- Use variable definitions with descriptions and types
- Use locals for computed values and tag merging
- Output all resource IDs and ARNs that other modules might need
"""

CLOUDFORMATION_HINTS = """
CLOUDFORMATION-SPECIFIC RULES:
- Use AWSTemplateFormatVersion: '2010-09-09'
- Define Parameters with Type, Default, Description, AllowedValues
- Use !Ref, !Sub, !GetAtt for references (not hardcoded values)
- Export cross-stack values with naming: ${{Environment}}-${{ResourceType}}-${{Identifier}}
- Include Metadata, Conditions where appropriate
- Add DependsOn only when CloudFormation cannot infer dependency
"""

CDK_HINTS = """
CDK-SPECIFIC RULES:
- Use L2 constructs (higher-level) when available
- Follow the project's CDK language ({language})
- Include proper stack props with environment configuration
- Use cdk.Tags.of(construct).add() for tagging
- Export values using CfnOutput
"""


# --------------------------------------------------------------------------
# Helper to assemble the full prompt
# --------------------------------------------------------------------------


def build_generation_prompt(
    project_type: str, context: str, language: str = "typescript"
) -> str:
    """Assemble the system prompt with project-type hints and context."""
    hints = _get_project_hints(project_type, language=language)
    full_context = context
    if hints:
        full_context = f"{context}\n\n{hints}"

    return SYSTEM_IAC_GENERATOR.format(
        project_type=project_type,
        context=full_context,
    )


def build_fix_prompt(context: str, violations: str, previous_files: str) -> str:
    """Assemble the self-correction prompt."""
    return SYSTEM_IAC_FIXER.format(
        context=context,
        violations=violations,
        previous_files=previous_files,
    )


def format_previous_files(files: list) -> str:
    """Format previously generated files for the fix prompt (abbreviated)."""
    parts = []
    for f in files:
        content = f.content
        # Truncate large files to save tokens
        if len(content) > 1500:
            content = content[:1500] + "\n# ... (truncated)"
        parts.append(f"### {f.path}\n```\n{content}\n```")
    return "\n\n".join(parts)


def _get_project_hints(project_type: str, language: str = "typescript") -> str:
    """Get project-type specific prompt additions."""
    hints_map = {
        "terraform-terragrunt": TERRAGRUNT_STACK_HINTS,
        "terragrunt": TERRAGRUNT_STACK_HINTS,
        "terraform": TERRAFORM_HINTS,
        "cloudformation": CLOUDFORMATION_HINTS,
        "cdkv2": CDK_HINTS.format(language=language),
    }
    return hints_map.get(project_type, TERRAFORM_HINTS)
