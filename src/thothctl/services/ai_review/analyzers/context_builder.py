"""Context builder - gathers rich IaC context from thothctl internal services."""
import asyncio
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class IaCContext:
    """Aggregated IaC context from all thothctl services."""
    directory: str = ""
    project_type: str = "unknown"
    # Inventory
    inventory: Dict[str, Any] = field(default_factory=dict)
    modules: List[Dict] = field(default_factory=list)
    providers: List[Dict] = field(default_factory=list)
    # Scan findings
    scan_results: Dict[str, Any] = field(default_factory=dict)
    # Blast radius
    blast_radius: Dict[str, Any] = field(default_factory=dict)
    # Raw code (supplementary)
    code_files: Dict[str, str] = field(default_factory=dict)
    # Metadata
    errors: List[str] = field(default_factory=list)


class ContextBuilder:
    """Builds rich IaC context by calling thothctl's internal services."""

    def build_context(self, directory: str) -> IaCContext:
        """Gather all available context from a directory."""
        ctx = IaCContext(directory=directory)

        # Run each collector independently — failures don't block others
        self._collect_inventory(ctx)
        self._collect_scan_results(ctx)
        self._collect_plan_files(ctx)
        self._collect_blast_radius(ctx)
        self._collect_code(ctx)

        return ctx

    def format_for_ai(self, ctx: IaCContext) -> str:
        """Format the full context into a single string for the LLM."""
        sections = [f"# IaC Analysis Context for: {ctx.directory}\n"]
        sections.append(f"Project type: {ctx.project_type}\n")

        # Inventory section
        if ctx.modules or ctx.providers:
            sections.append("## Infrastructure Inventory")
            if ctx.modules:
                sections.append(f"Modules ({len(ctx.modules)}):")
                for m in ctx.modules[:30]:
                    status = f" [{m.get('status', '')}]" if m.get("status") else ""
                    version = m.get("version", "N/A")
                    latest = m.get("latest_version", "")
                    ver_info = f"v{version}"
                    if latest and latest != version:
                        ver_info += f" → v{latest} available"
                    sections.append(f"  - {m.get('name', 'unknown')} ({ver_info}){status}")
            if ctx.providers:
                sections.append(f"\nProviders ({len(ctx.providers)}):")
                for p in ctx.providers[:20]:
                    sections.append(
                        f"  - {p.get('name', 'unknown')} v{p.get('version', 'N/A')} "
                        f"({p.get('source', '')})"
                    )
            sections.append("")

        # Scan results section
        if ctx.scan_results.get("total_findings", 0) > 0:
            sections.append("## Security Scan Findings")
            for tool, data in ctx.scan_results.get("tools", {}).items():
                sections.append(f"### {tool.upper()}")
                sections.append(f"Passed: {data.get('passed', 0)}, Failed: {data.get('failed', 0)}")
                for f in data.get("findings", [])[:30]:
                    sections.append(
                        f"  - [{f.get('severity', '?')}] {f.get('check_id', '')}: "
                        f"{f.get('check_name', '')} → {f.get('resource', '')} "
                        f"({f.get('file', '')})"
                    )
            sections.append("")

        # Blast radius section
        if ctx.blast_radius:
            sections.append("## Blast Radius / Dependency Analysis")
            sections.append(f"Total components: {ctx.blast_radius.get('total_components', 0)}")
            sections.append(f"Risk level: {ctx.blast_radius.get('risk_level', 'N/A')}")
            for comp in ctx.blast_radius.get("affected_components", [])[:15]:
                sections.append(
                    f"  - {comp.get('name', '?')} ({comp.get('change_type', '?')}) "
                    f"risk={comp.get('risk_score', 0):.1f} "
                    f"deps={comp.get('dependencies', [])}"
                )
            sections.append("")

        # Code section — only include files referenced in findings + plan summaries
        if ctx.code_files:
            sections.append("## Key IaC Files")
            char_budget = 12000  # ~3K tokens for code context

            # Prioritize: plans first, then files mentioned in scan findings
            referenced_files = set()
            for tool_data in ctx.scan_results.get("tools", {}).values():
                for f in tool_data.get("findings", []):
                    ref = f.get("file", "")
                    if ref:
                        referenced_files.add(ref)

            # Sort: plans first, then referenced files, then others
            def priority(item):
                path, _ = item
                if "[PLAN]" in path:
                    return 0
                if any(ref in path for ref in referenced_files):
                    return 1
                return 2

            used = 0
            for path, content in sorted(ctx.code_files.items(), key=priority):
                header = f"\n--- {path} ---\n"
                if used + len(header) + len(content) > char_budget:
                    remaining = len(ctx.code_files) - len([s for s in sections if s.startswith("--- ")])
                    sections.append(f"\n[Truncated: additional files omitted]")
                    break
                sections.append(header)
                sections.append(content)
                used += len(header) + len(content)

        if ctx.errors:
            sections.append(f"\n## Context Collection Notes")
            for e in ctx.errors:
                sections.append(f"  - {e}")

        return "\n".join(sections)

    # -- Private collectors --

    def _collect_inventory(self, ctx: IaCContext) -> None:
        """Run InventoryService to get modules, providers, versions."""
        try:
            from ...inventory.inventory_service import InventoryService

            svc = InventoryService()
            inventory = asyncio.get_event_loop().run_until_complete(
                svc.create_inventory(
                    source_directory=ctx.directory,
                    check_versions=True,
                    report_type="json",
                    print_console=False,
                )
            )

            ctx.inventory = inventory
            ctx.project_type = inventory.get("project_type", "unknown")

            # Extract modules
            for group in inventory.get("component_groups", []):
                for comp in group.get("components", []):
                    ctx.modules.append({
                        "name": comp.get("name", ""),
                        "source": comp.get("source", ""),
                        "version": comp.get("version", ""),
                        "latest_version": comp.get("latest_version", ""),
                        "status": comp.get("status", ""),
                        "registry": comp.get("registry", ""),
                    })
                for prov in group.get("providers", []):
                    ctx.providers.append({
                        "name": prov.get("name", ""),
                        "version": prov.get("version", ""),
                        "source": prov.get("source", ""),
                        "latest_version": prov.get("latest_version", ""),
                        "status": prov.get("status", ""),
                    })

            logger.info(f"Inventory: {len(ctx.modules)} modules, {len(ctx.providers)} providers")
        except Exception as e:
            logger.debug(f"Inventory collection failed: {e}")
            ctx.errors.append(f"Inventory unavailable: {e}")

    def _collect_scan_results(self, ctx: IaCContext) -> None:
        """Check for existing scan reports at project root."""
        try:
            from .report_analyzer import ReportAnalyzer

            analyzer = ReportAnalyzer()

            # Look for Reports/ at target dir and up to project root
            target = Path(ctx.directory)
            reports_dir = None
            for parent in [target] + list(target.parents):
                candidate = parent / "Reports"
                if candidate.exists():
                    reports_dir = candidate
                    break
                if (parent / ".thothcf.toml").exists() or (parent / ".git").exists():
                    break

            if reports_dir and reports_dir.exists():
                ctx.scan_results = analyzer.parse_scan_results(str(reports_dir))
                if ctx.scan_results.get("total_findings", 0) > 0:
                    logger.info(f"Found existing scan results: {ctx.scan_results['total_findings']} findings")
                    return

            ctx.errors.append("No scan reports found. Run 'thothctl scan iac' first for richer AI analysis.")

        except Exception as e:
            logger.debug(f"Scan results collection failed: {e}")
            ctx.errors.append(f"Scan results unavailable: {e}")

    def _collect_plan_files(self, ctx: IaCContext) -> None:
        """Collect tfplan.json summaries for change analysis."""
        try:
            import json as _json
            target = Path(ctx.directory)

            # Find tfplan.json in target and project-level stacks/tfplan/
            plan_files = list(target.rglob("tfplan.json"))
            for parent in [target] + list(target.parents):
                if (parent / ".thothcf.toml").exists() or (parent / ".git").exists():
                    tfplan_dir = parent / "stacks" / "tfplan"
                    if tfplan_dir.exists():
                        plan_files.extend(tfplan_dir.rglob("tfplan.json"))
                    break

            for pf in plan_files[:5]:
                try:
                    with open(pf) as f:
                        plan = _json.load(f)
                    changes = plan.get("resource_changes", [])
                    creates = sum(1 for c in changes if "create" in c.get("change", {}).get("actions", []))
                    updates = sum(1 for c in changes if "update" in c.get("change", {}).get("actions", []))
                    deletes = sum(1 for c in changes if "delete" in c.get("change", {}).get("actions", []))
                    ctx.code_files[f"[PLAN] {pf.name} ({pf.parent.name})"] = (
                        f"# Terraform Plan: {pf.parent.name}\n"
                        f"# Creates: {creates}, Updates: {updates}, Deletes: {deletes}\n"
                        f"# Total resource changes: {len(changes)}\n"
                        + "\n".join(
                            f"# {c['type']}.{c['name']} → {c['change']['actions']}"
                            for c in changes[:20]
                        )
                    )
                except Exception:
                    pass
            if plan_files:
                logger.info(f"Found {len(plan_files)} tfplan.json files")
        except Exception as e:
            logger.debug(f"Plan file collection failed: {e}")

    def _collect_blast_radius(self, ctx: IaCContext) -> None:
        """Run BlastRadiusService for dependency analysis."""
        try:
            from ...check.project.blast_radius_service import BlastRadiusService

            svc = BlastRadiusService()
            assessment = svc.assess_blast_radius(directory=ctx.directory, recursive=True)

            ctx.blast_radius = {
                "total_components": assessment.total_components,
                "risk_level": assessment.risk_level.value if hasattr(assessment.risk_level, 'value') else str(assessment.risk_level),
                "affected_components": [
                    {
                        "name": c.name,
                        "path": c.path,
                        "change_type": c.change_type,
                        "risk_score": c.risk_score,
                        "dependencies": c.dependencies,
                        "dependents": c.dependents,
                        "criticality": c.criticality,
                    }
                    for c in assessment.affected_components
                ],
                "recommendations": assessment.recommendations,
            }
            logger.info(f"Blast radius: {assessment.total_components} components")
        except Exception as e:
            logger.debug(f"Blast radius collection failed: {e}")
            ctx.errors.append(f"Blast radius unavailable: {e}")

    def _collect_code(self, ctx: IaCContext) -> None:
        """Collect raw IaC files as supplementary context."""
        try:
            from .code_reviewer import CodeReviewer

            reviewer = CodeReviewer()
            ctx.code_files = reviewer.collect_code_for_review(ctx.directory)
            logger.info(f"Collected {len(ctx.code_files)} IaC files")
        except Exception as e:
            logger.debug(f"Code collection failed: {e}")
            ctx.errors.append(f"Code collection failed: {e}")
