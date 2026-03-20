"""Multi-agent orchestrator for AI-powered IaC operations.

The orchestrator delegates tasks to specialized agents, each with a focused
system prompt and a specific slice of context. The main agent coordinates
the workflow and merges results.

Architecture:
    Orchestrator (this module)
    ├── SecurityAgent     — scan findings analysis
    ├── ArchitectureAgent — module structure, blast radius
    ├── FixAgent          — code improvement generation
    └── DecisionAgent     — approve/reject/request-changes

Each agent is a (system_prompt, context_formatter) pair that runs through
the same AI provider. The orchestrator runs them in parallel when possible
and merges their outputs into a unified result.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .config.ai_settings import AISettings, ProviderConfig
from .analyzers.context_builder import ContextBuilder, IaCContext
from .utils.cost_tracker import CostTracker
from .memory import AgentMemory, MemoryConfig

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    FIX = "fix"
    DECISION = "decision"


@dataclass
class AgentTask:
    """A unit of work for a specialized agent."""
    role: AgentRole
    system_prompt: str
    context: str
    # Optional post-processor to transform raw AI output
    post_process: Optional[Callable[[Dict], Dict]] = None


@dataclass
class OrchestratorResult:
    """Merged result from all agents."""
    security: Dict[str, Any] = field(default_factory=dict)
    architecture: Dict[str, Any] = field(default_factory=dict)
    fixes: Dict[str, Any] = field(default_factory=dict)
    decision: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    cost: Dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    """Coordinates multiple specialized AI agents for IaC analysis.

    Usage:
        orchestrator = AgentOrchestrator(provider="ollama", model="llama3")
        result = orchestrator.run_full_review("/path/to/terraform")
        result = orchestrator.run_agents("/path", roles=[AgentRole.SECURITY, AgentRole.FIX])
    """

    def __init__(self, provider: str = None, model: str = None,
                 config_path: str = None, max_parallel: int = 2,
                 memory_config: MemoryConfig = None):
        self.settings = AISettings.load(config_path)
        self.cost_tracker = CostTracker(
            daily_limit=self.settings.cost_controls.daily_limit,
            monthly_budget=self.settings.cost_controls.monthly_budget,
        )
        self.cost_tracker.load_records()
        self.context_builder = ContextBuilder()
        self.max_parallel = max_parallel
        self.memory = AgentMemory.create(memory_config)

        provider_name = provider or self.settings.default_provider
        self._provider = self._init_provider(provider_name, model)

    def _init_provider(self, provider_name: str, model: str = None):
        from .providers.openai_provider import OpenAIProvider
        from .providers.bedrock_provider import BedrockProvider
        from .providers.bedrock_agent_provider import BedrockAgentProvider
        from .providers.azure_provider import AzureOpenAIProvider
        from .providers.ollama_provider import OllamaProvider

        providers = {"openai": OpenAIProvider, "bedrock": BedrockProvider,
                     "bedrock_agent": BedrockAgentProvider,
                     "azure": AzureOpenAIProvider, "ollama": OllamaProvider}
        cls = providers.get(provider_name)
        if not cls:
            raise ValueError(f"Unknown provider: {provider_name}")
        config = self.settings.get_provider_config(provider_name)
        if model:
            config.model = model
        return cls(config)

    # -- Public API --

    def run_full_review(self, directory: str) -> OrchestratorResult:
        """Run all agents for a comprehensive review."""
        return self.run_agents(directory, roles=[
            AgentRole.SECURITY, AgentRole.ARCHITECTURE, AgentRole.FIX,
        ])

    def run_agents(self, directory: str,
                   roles: List[AgentRole] = None,
                   repository: str = "",
                   run_id: str = "") -> OrchestratorResult:
        """Run specific agents against a directory.

        Args:
            directory: Path to IaC code
            roles: Which agents to run (default: all except decision)
            repository: Repo identifier for memory (e.g. "owner/repo")
            run_id: Pipeline/PR identifier for isolation (e.g. "pr/42", "run/123")
        """
        if roles is None:
            roles = [AgentRole.SECURITY, AgentRole.ARCHITECTURE]

        # Build shared context once
        logger.info(f"Building context for {directory}")
        ctx = self.context_builder.build_context(directory)

        # Enrich context with previous analysis from memory
        if repository:
            previous = self.memory.load_analysis(repository, run_id=run_id)
            if previous:
                ctx.errors.append(f"Previous analysis loaded from memory ({repository})")
                self._inject_previous_context(ctx, previous)

        # Create tasks for requested roles
        tasks = self._create_tasks(ctx, roles)

        if not self.cost_tracker.check_budget():
            logger.warning("Budget exceeded — running offline agents only")
            return self._offline_result(ctx, roles)

        # Execute agents (parallel where possible)
        result = OrchestratorResult()
        self._execute_tasks(tasks, result)

        # If decision was requested, run it last with merged context
        if AgentRole.DECISION in roles:
            self._run_decision(result, ctx)

        result.cost = self.cost_tracker.get_cost_report("daily")

        # Persist results to memory
        if repository:
            self._save_to_memory(repository, result, run_id=run_id)

        return result

    def run_single_agent(self, directory: str, role: AgentRole) -> Dict[str, Any]:
        """Run a single specialized agent."""
        result = self.run_agents(directory, roles=[role])
        return getattr(result, role.value, {})

    # -- Task creation --

    def _create_tasks(self, ctx: IaCContext, roles: List[AgentRole]) -> List[AgentTask]:
        """Create agent tasks from context and requested roles."""
        from .utils.prompts import (
            SYSTEM_SECURITY_ANALYST, SYSTEM_CODE_REVIEWER, SYSTEM_FULL_ANALYSIS,
        )
        from .utils.fix_prompts import SYSTEM_FIX_GENERATOR

        tasks = []

        if AgentRole.SECURITY in roles:
            # Security agent gets scan findings + code
            security_ctx = self._format_security_context(ctx)
            if security_ctx:
                tasks.append(AgentTask(
                    role=AgentRole.SECURITY,
                    system_prompt=SYSTEM_SECURITY_ANALYST,
                    context=security_ctx,
                ))

        if AgentRole.ARCHITECTURE in roles:
            # Architecture agent gets inventory + blast radius + code structure
            arch_ctx = self._format_architecture_context(ctx)
            if arch_ctx:
                tasks.append(AgentTask(
                    role=AgentRole.ARCHITECTURE,
                    system_prompt=SYSTEM_CODE_REVIEWER,
                    context=arch_ctx,
                ))

        if AgentRole.FIX in roles:
            # Fix agent gets findings + affected code
            fix_ctx = self._format_fix_context(ctx)
            if fix_ctx:
                tasks.append(AgentTask(
                    role=AgentRole.FIX,
                    system_prompt=SYSTEM_FIX_GENERATOR,
                    context=fix_ctx,
                ))

        return tasks

    # -- Execution --

    def _execute_tasks(self, tasks: List[AgentTask], result: OrchestratorResult):
        """Execute agent tasks, parallelizing where budget allows."""
        if not tasks:
            return

        if self.max_parallel <= 1 or len(tasks) == 1:
            for task in tasks:
                self._run_task(task, result)
        else:
            with ThreadPoolExecutor(max_workers=min(self.max_parallel, len(tasks))) as pool:
                futures = {pool.submit(self._call_ai, task): task for task in tasks}
                for future in as_completed(futures):
                    task = futures[future]
                    try:
                        ai_result = future.result()
                        if task.post_process:
                            ai_result = task.post_process(ai_result)
                        setattr(result, task.role.value, ai_result)
                    except Exception as e:
                        logger.error(f"Agent {task.role.value} failed: {e}")
                        result.errors.append(f"{task.role.value}: {e}")

    def _run_task(self, task: AgentTask, result: OrchestratorResult):
        """Run a single task synchronously."""
        try:
            ai_result = self._call_ai(task)
            if task.post_process:
                ai_result = task.post_process(ai_result)
            setattr(result, task.role.value, ai_result)
        except Exception as e:
            logger.error(f"Agent {task.role.value} failed: {e}")
            result.errors.append(f"{task.role.value}: {e}")

    def _call_ai(self, task: AgentTask) -> Dict[str, Any]:
        """Send task to AI provider and track cost."""
        ai_result = self._provider.analyze(task.system_prompt, task.context)
        usage = ai_result.pop("_usage", {})
        self.cost_tracker.record_usage(
            provider=self._provider.name,
            model=self._provider.model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            operation=f"agent_{task.role.value}",
        )
        return ai_result

    def _run_decision(self, result: OrchestratorResult, ctx: IaCContext):
        """Run decision agent using merged results from other agents."""
        from .decision_engine import DecisionEngine

        # Use security analysis if available, otherwise build minimal
        analysis = result.security or {
            "summary": {"total_findings": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
            "findings": [], "risk_score": 0, "recommendations": [],
        }
        engine = DecisionEngine()
        decision_result = engine.evaluate(analysis)
        result.decision = {
            "action": decision_result.decision.value,
            "confidence": decision_result.confidence,
            "reason": decision_result.reason,
            "risk_score": decision_result.risk_score,
            "findings_summary": decision_result.findings_summary,
            "blocked_by_safety": decision_result.blocked_by_safety,
            "safety_reason": decision_result.safety_reason,
        }

    def _offline_result(self, ctx: IaCContext, roles: List[AgentRole]) -> OrchestratorResult:
        """Generate results without AI when budget is exceeded."""
        from .analyzers.risk_assessor import RiskAssessor

        result = OrchestratorResult()
        result.errors.append("AI budget exceeded — offline analysis only")

        if AgentRole.SECURITY in roles and ctx.scan_results.get("total_findings", 0) > 0:
            risk = RiskAssessor().assess_risk(ctx.scan_results)
            result.security = {
                "summary": {"total_findings": risk["total_findings"],
                            **{k.lower(): v for k, v in risk["by_severity"].items()}},
                "risk_score": risk["risk_score"],
                "findings": risk["top_findings"][:10],
                "recommendations": [f"Risk level: {risk['risk_level']}"],
                "_note": "Offline analysis",
            }

        if AgentRole.FIX in roles:
            from .ai_agent import AIReviewAgent
            result.fixes = AIReviewAgent._pattern_fixes(
                ctx.scan_results, ctx.code_files, "medium",
            )

        if AgentRole.DECISION in roles:
            self._run_decision(result, ctx)

        return result

    # -- Context formatters (each agent gets a focused slice) --

    def _format_security_context(self, ctx: IaCContext) -> str:
        """Security agent: scan findings + affected code snippets."""
        if ctx.scan_results.get("total_findings", 0) == 0 and not ctx.code_files:
            return ""

        sections = ["# Security Analysis Request\n"]

        if ctx.scan_results.get("total_findings", 0) > 0:
            sections.append("## Scan Findings")
            for tool, data in ctx.scan_results.get("tools", {}).items():
                sections.append(f"### {tool.upper()} (passed={data.get('passed', 0)}, failed={data.get('failed', 0)})")
                for f in data.get("findings", [])[:40]:
                    sections.append(
                        f"- [{f.get('severity', '?')}] {f.get('check_id', '')}: "
                        f"{f.get('check_name', '')} → {f.get('resource', '')} ({f.get('file', '')})"
                    )

        # Include affected files only
        affected_files = set()
        for tool_data in ctx.scan_results.get("tools", {}).values():
            for f in tool_data.get("findings", []):
                if f.get("file"):
                    affected_files.add(f["file"])

        if affected_files and ctx.code_files:
            sections.append("\n## Affected Code")
            budget = 20000
            used = 0
            for path in sorted(affected_files):
                content = ctx.code_files.get(path, "")
                if not content:
                    continue
                entry = f"\n--- {path} ---\n{content}\n"
                if used + len(entry) > budget:
                    break
                sections.append(entry)
                used += len(entry)

        return "\n".join(sections)

    def _format_architecture_context(self, ctx: IaCContext) -> str:
        """Architecture agent: inventory + blast radius + code structure."""
        sections = ["# Architecture Review Request\n"]
        sections.append(f"Project type: {ctx.project_type}\n")

        if ctx.modules:
            sections.append(f"## Modules ({len(ctx.modules)})")
            for m in ctx.modules[:30]:
                ver = f"v{m.get('version', '?')}"
                latest = m.get("latest_version", "")
                if latest and latest != m.get("version"):
                    ver += f" → v{latest} available"
                sections.append(f"- {m.get('name', '?')} ({ver}) [{m.get('status', '')}]")

        if ctx.providers:
            sections.append(f"\n## Providers ({len(ctx.providers)})")
            for p in ctx.providers[:20]:
                sections.append(f"- {p.get('name', '?')} v{p.get('version', '?')} ({p.get('source', '')})")

        if ctx.blast_radius:
            sections.append(f"\n## Blast Radius")
            sections.append(f"Components: {ctx.blast_radius.get('total_components', 0)}")
            sections.append(f"Risk: {ctx.blast_radius.get('risk_level', 'N/A')}")
            for c in ctx.blast_radius.get("affected_components", [])[:15]:
                sections.append(f"- {c.get('name', '?')} (risk={c.get('risk_score', 0):.1f}, deps={c.get('dependencies', [])})")

        if ctx.code_files:
            sections.append(f"\n## Code Structure ({len(ctx.code_files)} files)")
            budget = 15000
            used = 0
            for path, content in sorted(ctx.code_files.items()):
                entry = f"\n--- {path} ---\n{content}\n"
                if used + len(entry) > budget:
                    sections.append("[Truncated]")
                    break
                sections.append(entry)
                used += len(entry)

        return "\n".join(sections)

    def _format_fix_context(self, ctx: IaCContext) -> str:
        """Fix agent: findings + full code for affected files."""
        if ctx.scan_results.get("total_findings", 0) == 0:
            return ""

        from .ai_agent import AIReviewAgent
        agent = AIReviewAgent.__new__(AIReviewAgent)
        return agent._format_fix_request(ctx.scan_results, ctx.code_files, "medium")

    # -- Memory helpers --

    def _inject_previous_context(self, ctx: IaCContext, previous: Dict) -> None:
        """Add previous analysis summary to context for continuity."""
        summary = previous.get("summary", {})
        prev_score = previous.get("risk_score", "N/A")
        prev_findings = summary.get("total_findings", 0)
        if prev_findings > 0:
            ctx.errors.append(
                f"Previous review: risk={prev_score}, "
                f"findings={prev_findings} "
                f"(critical={summary.get('critical', 0)}, high={summary.get('high', 0)})"
            )

    def _save_to_memory(self, repository: str, result: OrchestratorResult,
                        run_id: str = "") -> None:
        """Persist analysis results and decision to memory.

        Analysis is scoped per run_id (pipeline-isolated).
        Decisions are always at repo level (audit trail).
        """
        try:
            if result.security:
                self.memory.save_analysis(repository, result.security, run_id=run_id)
            if result.decision:
                self.memory.append_decision(repository, result.decision)
        except Exception as e:
            logger.debug(f"Failed to save to memory: {e}")
