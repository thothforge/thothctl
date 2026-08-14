"""CLI command: thothctl generate iac — Generate IaC from natural language intent."""

from typing import Optional

import click

from ....core.cli_ui import CliUI
from ....core.commands import ClickCommand


class GenerateIaCCommand(ClickCommand):
    """Generate governed Infrastructure as Code from natural language intent."""

    def __init__(self):
        super().__init__()
        self.ui = CliUI()

    def validate(self, intent: str, **kwargs) -> bool:
        if not intent or not intent.strip():
            self.ui.print_error(
                "Intent is required. Describe the infrastructure you want to create."
            )
            raise ValueError("--intent is required")
        return True

    def _execute(
        self,
        intent: str,
        project_type: str = "auto",
        provider: str = "ollama",
        model: Optional[str] = None,
        output_dir: Optional[str] = None,
        dry_run: bool = True,
        apply: bool = False,
        self_correct: bool = True,
        max_iterations: int = 3,
        skip_validation: bool = False,
        include_diagram: bool = True,
        composition: str = "single",
        **kwargs,
    ) -> None:
        """Execute IaC generation from intent."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.syntax import Syntax

        console = Console()

        # Resolve apply/dry-run (--apply overrides --dry-run)
        should_apply = apply and not dry_run

        # Determine working directory
        directory = output_dir or "."

        # Show intent
        console.print(
            Panel(
                f"[bold]{intent}[/bold]",
                title="🎯 Intent",
                border_style="blue",
            )
        )

        # Initialize service
        self.ui.print_info(
            f"🤖 Provider: {provider}" + (f" (model: {model})" if model else "")
        )

        try:
            from ....services.generate.intent.intent_service import IntentToIaCService

            service = IntentToIaCService(provider=provider, model=model)
        except Exception as e:
            self.ui.print_error(f"Failed to initialize AI provider: {e}")
            return

        # Build context (show what was loaded)
        with self.ui.status_spinner("🔍 Loading project context..."):
            payload = service.context_builder.build_context(directory, project_type)

        # Display context summary
        sections_loaded = []
        if payload.project_config:
            sections_loaded.append(
                f"✅ .thothcf.toml ({len(payload.project_config)} chars)"
            )
        if payload.iac_rules:
            sections_loaded.append(f"✅ IaC rules ({len(payload.iac_rules)} chars)")
        if payload.project_overview:
            sections_loaded.append(
                f"✅ Project overview ({len(payload.project_overview)} chars)"
            )
        if payload.existing_patterns:
            sections_loaded.append(
                f"✅ Existing patterns ({len(payload.existing_patterns)} chars)"
            )
        if payload.org_policies:
            sections_loaded.append(
                f"✅ Org policies ({len(payload.org_policies)} chars)"
            )

        if sections_loaded:
            for s in sections_loaded:
                self.ui.print_info(f"  {s}")
        else:
            self.ui.print_warning("  No org context found — generating with defaults")

        self.ui.print_info(
            f"  📊 Context: ~{payload.total_tokens_estimate} tokens | Type: {payload.project_type}"
        )

        # Generate
        with self.ui.status_spinner("🤖 Generating infrastructure code..."):
            import time

            self._start_time = time.time()
            result = service.generate(
                intent=intent,
                directory=directory,
                project_type=project_type,
                output_dir=output_dir,
                apply=should_apply,
                self_correct=self_correct,
                max_iterations=max_iterations,
                skip_validation=skip_validation,
                include_diagram=include_diagram,
                composition=composition,
            )

        # Display results
        if not result.success:
            self.ui.print_error(f"Generation failed: {result.error}")
            return

        # Show validation status
        if result.validation:
            if result.validation.passed:
                if result.iterations > 1:
                    self.ui.print_success(
                        f"🔒 Validation passed (after {result.iterations} iteration(s))"
                    )
                else:
                    self.ui.print_success("🔒 Validation passed on first attempt")
            else:
                self.ui.print_warning(
                    f"⚠️ Validation: {result.validation.total_violations} violation(s) remain "
                    f"after {result.iterations} iteration(s)"
                )
                for v in result.validation.violations[:5]:
                    self.ui.print_warning(f"  [{v.severity}] {v.check_id}: {v.message}")
                if result.validation.total_violations > 5:
                    self.ui.print_warning(
                        f"  ... and {result.validation.total_violations - 5} more"
                    )

        # Show generated files
        console.print(f"\n📁 Generated {len(result.files)} file(s):")

        for f in result.files:
            if should_apply:
                console.print(f"  [green]✅ {f.path}[/green]")
            else:
                console.print(f"  [cyan]📄 {f.path}[/cyan]")

        # Show file contents in dry-run mode
        if not should_apply:
            console.print("")
            for f in result.files:
                # Detect language for syntax highlighting
                lang = "hcl"
                if f.path.endswith(".yaml") or f.path.endswith(".yml"):
                    lang = "yaml"
                elif f.path.endswith(".json"):
                    lang = "json"
                elif f.path.endswith(".ts"):
                    lang = "typescript"
                elif f.path.endswith(".py"):
                    lang = "python"

                syntax = Syntax(
                    f.content,
                    lang,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                )
                console.print(Panel(syntax, title=f"📄 {f.path}", border_style="dim"))

        # Show metadata
        if result.modules_used:
            console.print(f"\n💡 Modules: {', '.join(result.modules_used)}")
        if result.estimated_resources:
            console.print(f"📊 Resources: {', '.join(result.estimated_resources)}")
        if result.explanation:
            console.print(f"📝 {result.explanation}")

        # Show metrics
        import time

        elapsed = time.time() - self._start_time if hasattr(self, "_start_time") else 0
        metrics_parts = []
        if result.context_tokens:
            metrics_parts.append(f"context: ~{result.context_tokens} tokens")
        if result.generation_tokens:
            metrics_parts.append(f"generation: ~{result.generation_tokens} tokens")
        if elapsed > 0:
            metrics_parts.append(f"time: {elapsed:.1f}s")
        if result.iterations > 1:
            metrics_parts.append(f"iterations: {result.iterations}")
        metrics_parts.append(f"files: {len(result.files)}")
        if metrics_parts:
            console.print(f"⏱️  Metrics: {' | '.join(metrics_parts)}")

        # Final guidance
        console.print("")
        if should_apply:
            self.ui.print_success(f"✨ Files written to: {output_dir or '.'}")
            self.ui.print_info(
                "Next: run 'thothctl scan iac -t checkov' to verify, then 'terragrunt plan'"
            )
        else:
            self.ui.print_info("Run with [bold]--apply[/bold] to write files to disk:")
            apply_cmd = f'thothctl generate iac -i "{intent[:60]}..." --apply'
            if output_dir:
                apply_cmd += f" -o {output_dir}"
            console.print(f"  [dim]{apply_cmd}[/dim]")


# Create the Click command
cli = GenerateIaCCommand.as_click_command(
    help="Generate governed IaC from natural language intent. "
    "Uses organizational rules (.thothcf.toml) and validates with Checkov/OPA."
)(
    click.option(
        "-i",
        "--intent",
        required=True,
        help="Natural language description of the infrastructure to generate",
    ),
    click.option(
        "-pt",
        "--project-type",
        type=click.Choice(
            [
                "auto",
                "terraform",
                "terraform-terragrunt",
                "terragrunt",
                "cloudformation",
                "cdkv2",
            ],
            case_sensitive=False,
        ),
        default="auto",
        help="Target project type (default: auto-detect from directory)",
    ),
    click.option(
        "-p",
        "--provider",
        type=click.Choice(
            ["ollama", "bedrock", "openai", "azure"], case_sensitive=False
        ),
        default="ollama",
        help="AI provider to use for code generation",
    ),
    click.option(
        "-m",
        "--model",
        default=None,
        help="Model override (e.g., llama3, anthropic.claude-sonnet-4-6, gpt-4-turbo)",
    ),
    click.option(
        "-o",
        "--output-dir",
        type=click.Path(),
        default=None,
        help="Target directory for generated files (default: current directory)",
    ),
    click.option(
        "--dry-run/--no-dry-run",
        default=True,
        help="Preview generated code without writing to disk (default: dry-run)",
    ),
    click.option(
        "--apply",
        is_flag=True,
        default=False,
        help="Write generated files to disk",
    ),
    click.option(
        "--self-correct/--no-self-correct",
        default=True,
        help="Re-prompt AI to fix validation violations (default: enabled)",
    ),
    click.option(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum self-correction attempts (default: 3)",
    ),
    click.option(
        "--skip-validation",
        is_flag=True,
        default=False,
        help="Skip Checkov/OPA validation (trust AI output)",
    ),
    click.option(
        "--include-diagram/--no-diagram",
        default=True,
        help="Generate architecture diagram alongside code",
    ),
    click.option(
        "--composition",
        type=click.Choice(["single", "full", "incremental"], case_sensitive=False),
        default="single",
        help=(
            "Composition mode: 'single' generates one stack (default), "
            "'full' generates a complete project with root config, "
            "'incremental' adds stacks to an existing project"
        ),
    ),
)
