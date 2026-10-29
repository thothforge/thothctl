"""System prompts for Intent-to-IaC code generation.

These prompts are injected with organizational context to produce governed IaC.
The AI follows your rules because they're in the prompt — not because of a runtime engine.

Token strategy: the SYSTEM prompt is a *stable* block (role + org context +
project hints + output format) that is byte-identical across the initial
generation and every self-correction ("fix") iteration of a run. All dynamic,
per-call content (the intent, validation violations, the code being fixed) goes
into the USER message. Keeping the system prefix stable means the org context is
built once per run instead of 2-3x, and lets providers reuse a cached prefix.
"""

# --------------------------------------------------------------------------
# Stable system prompt — shared by generation AND self-correction
# --------------------------------------------------------------------------

SYSTEM_IAC_GENERATOR = """You are an expert Infrastructure as Code generator and fixer.
Generate complete, deployable {project_type} code following organizational standards.
When given existing code plus validation violations, correct the violations while
preserving the architecture.

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

WHEN FIXING VIOLATIONS (a "VIOLATIONS TO FIX" section is present in the user message):
- Fix ALL listed violations while maintaining the same architecture
- Do NOT remove functionality — only add missing security configurations
- Keep all existing resources, tags, and naming intact
- Ensure the fix doesn't break dependencies between resources
- Common fixes: CKV_AWS_130/CKV2_AWS_11 (add aws_flow_log for VPC flow logs);
  CKV_AWS_178 (one NAT gateway per AZ); CKV_AWS_260/CKV_AWS_23 (add description to
  security group rules); CKV_AWS_145 (S3 server_side_encryption_configuration);
  CKV_AWS_18 (S3 logging); CKV_AWS_144 (S3 replication if required)

OUTPUT FORMAT — respond with ONLY this JSON (no markdown fences, no explanation outside JSON):
{{
  "files": [
    {{"path": "relative/path/to/file", "content": "full file content here"}},
    ...
  ],
  "explanation": "brief explanation of architecture decisions (or what was fixed)",
  "modules_used": ["source@version", ...],
  "estimated_resources": ["aws_resource_type", ...]
}}"""


# Kept for backward compatibility (older callers / tests may import it).
# The fixer instructions now live in the shared SYSTEM_IAC_GENERATOR so the
# system prefix is identical across generation and fix.
SYSTEM_IAC_FIXER = SYSTEM_IAC_GENERATOR


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
    """Assemble the stable system prompt with project-type hints and context.

    This is the same static block used for both generation and self-correction,
    so the system prefix stays byte-identical across a run's iterations.
    """
    hints = _get_project_hints(project_type, language=language)
    full_context = context
    if hints:
        full_context = f"{context}\n\n{hints}"

    return SYSTEM_IAC_GENERATOR.format(
        project_type=project_type,
        context=full_context,
    )


def build_fix_system_prompt(
    project_type: str, context: str, language: str = "typescript"
) -> str:
    """Return the system prompt for a fix call.

    Identical to build_generation_prompt — the fixer instructions live in the
    shared static block, so generation and fix send the exact same system
    prompt (org context is not re-templated per iteration).
    """
    return build_generation_prompt(project_type, context, language=language)


def build_fix_user_message(violations: str, previous_files: str) -> str:
    """Build the DYNAMIC user message for a self-correction call.

    Only this changes between iterations — the system prompt stays stable.

    Args:
        violations: Formatted violation list (ValidationResult.format_for_ai()).
        previous_files: The code to fix (ideally only the violating files).
    """
    return (
        "The generated code has validation violations that must be fixed.\n\n"
        "VIOLATIONS TO FIX:\n"
        f"{violations}\n\n"
        "CODE TO FIX:\n"
        f"{previous_files}\n\n"
        "Return the corrected files in the JSON format specified in the system prompt."
    )


def build_fix_prompt(context: str, violations: str, previous_files: str) -> str:
    """Deprecated: assemble a combined fix prompt (context + violations + files).

    Retained for backward compatibility. New callers should use
    build_fix_system_prompt() for the (stable) system prompt and
    build_fix_user_message() for the (dynamic) user content, so the org context
    is not re-sent on every correction iteration.
    """
    return (
        f"{SYSTEM_IAC_GENERATOR.format(project_type='terraform', context=context)}\n\n"
        f"{build_fix_user_message(violations, previous_files)}"
    )


def format_previous_files(files: list, only_paths: set = None) -> str:
    """Format previously generated files for the fix prompt (abbreviated).

    Args:
        files: Generated files.
        only_paths: If provided, include only files whose path is in this set
            (the files that actually have violations). Falls back to all files
            when the filter would exclude everything (e.g. violations without
            file paths), so the fixer always has something to work with.
    """
    selected = files
    if only_paths:
        filtered = [f for f in files if f.path in only_paths]
        if filtered:
            selected = filtered

    parts = []
    for f in selected:
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
