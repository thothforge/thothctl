"""Main AI Review Agent orchestrator."""
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .config.ai_settings import AISettings
from .providers.openai_provider import OpenAIProvider
from .providers.bedrock_provider import BedrockProvider
from .providers.bedrock_agent_provider import BedrockAgentProvider
from .providers.azure_provider import AzureOpenAIProvider
from .providers.ollama_provider import OllamaProvider
from .analyzers.report_analyzer import ReportAnalyzer
from .analyzers.code_reviewer import CodeReviewer
from .analyzers.risk_assessor import RiskAssessor
from .analyzers.context_builder import ContextBuilder
from .utils.cost_tracker import CostTracker
from .utils.prompts import (
    SYSTEM_SECURITY_ANALYST,
    SYSTEM_CODE_REVIEWER,
    SYSTEM_FULL_ANALYSIS,
    SYSTEM_COMPACT,
)
from .utils.fix_prompts import SYSTEM_FIX_GENERATOR
from .tracing import span

logger = logging.getLogger(__name__)

PROVIDER_CLASSES = {
    "openai": OpenAIProvider,
    "bedrock": BedrockProvider,
    "bedrock_agent": BedrockAgentProvider,
    "azure": AzureOpenAIProvider,
    "ollama": OllamaProvider,
}


class AIReviewAgent:
    """Main orchestrator for AI-powered security analysis."""

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None,
                 config_path: Optional[str] = None):
        self.settings = AISettings.load(config_path)
        self.cost_tracker = CostTracker(
            daily_limit=self.settings.cost_controls.daily_limit,
            monthly_budget=self.settings.cost_controls.monthly_budget,
        )
        self.cost_tracker.load_records()
        self.report_analyzer = ReportAnalyzer()
        self.code_reviewer = CodeReviewer()
        self.risk_assessor = RiskAssessor()
        self.context_builder = ContextBuilder()

        provider_name = provider or self.settings.default_provider
        self._provider = self._initialize_provider(provider_name, model)

    def _initialize_provider(self, provider_name: str, model: Optional[str] = None):
        cls = PROVIDER_CLASSES.get(provider_name)
        if not cls:
            raise ValueError(f"Unknown provider: {provider_name}. Available: {list(PROVIDER_CLASSES.keys())}")
        config = self.settings.get_provider_config(provider_name)
        if model:
            config.model = model
        return cls(config)

    def analyze_scan_results(self, scan_dir: str) -> Dict[str, Any]:
        """Workflow 1: Analyze pre-existing scan results with AI."""
        scan_results = self.report_analyzer.parse_scan_results(scan_dir)
        if scan_results["total_findings"] == 0:
            return self._empty_result()

        basic_risk = self.risk_assessor.assess_risk(scan_results)

        if not self.cost_tracker.check_budget():
            logger.warning("Budget limit reached, returning basic analysis only")
            return self._basic_analysis(scan_results, basic_risk)

        formatted = self.report_analyzer.format_for_ai(scan_results)
        return self._call_ai(SYSTEM_SECURITY_ANALYST, formatted, "analyze_scan_results",
                             fallback=lambda: self._basic_analysis(scan_results, basic_risk))

    def analyze_directory(self, directory: str) -> Dict[str, Any]:
        """Workflow 2: Build full context from thothctl services, then analyze with AI.

        Calls InventoryService, ScanService, BlastRadiusService, and collects
        raw code to give the LLM a complete picture of the IaC project.
        """
        with span("ai_agent.analyze_directory", {"directory": directory}) as s:
            logger.info(f"Building rich context for {directory}")
            self._emit_status("📦 Collecting project context (inventory, scan reports, plans)...")
            ctx = self.context_builder.build_context(directory)

            basic_risk = None
            if ctx.scan_results.get("total_findings", 0) > 0:
                self._emit_status(f"⚠️  Found {ctx.scan_results['total_findings']} scan findings, assessing risk...")
                basic_risk = self.risk_assessor.assess_risk(ctx.scan_results)

            if not self.cost_tracker.check_budget():
                logger.warning("Budget limit reached")
                s.set_attribute("budget_exceeded", True)
                if basic_risk:
                    return self._basic_analysis(ctx.scan_results, basic_risk)
                return self._empty_result()

            self._emit_status("🤖 Sending context to LLM for security analysis...")
            formatted = self.context_builder.format_for_ai(ctx)
            
            # Use compact prompt for local models (Ollama) to fit VRAM constraints
            if self._provider.name == "ollama":
                # qwen models handle JSON well — use direct approach
                if "qwen" in self._provider.model.lower():
                    fallback = (lambda: self._basic_analysis(ctx.scan_results, basic_risk)) if basic_risk else self._empty_result
                    result = self._call_ai(SYSTEM_COMPACT, formatted, "analyze_directory", fallback=fallback)
                else:
                    # Other models (mistral, gemma): hybrid scan data + LLM recommendations
                    base_result = self._basic_analysis(ctx.scan_results, basic_risk) if basic_risk else self._empty_result()
                    try:
                        ai_response = self._provider.analyze(SYSTEM_COMPACT, formatted)
                        if isinstance(ai_response, dict) and ai_response.get("recommendations"):
                            base_result["recommendations"] = ai_response["recommendations"]
                            base_result["architecture_assessment"] = ai_response.get("architecture_assessment", "")
                        elif isinstance(ai_response, dict) and ai_response.get("_raw_text"):
                            base_result["recommendations"] = [ai_response["_raw_text"][:2000]]
                    except Exception as e:
                        logger.debug(f"LLM recommendations failed: {e}")
                    result = base_result
            else:
                system_prompt = SYSTEM_FULL_ANALYSIS
                fallback = (lambda: self._basic_analysis(ctx.scan_results, basic_risk)) if basic_risk else self._empty_result
                result = self._call_ai(system_prompt, formatted, "analyze_directory", fallback=fallback)

            result["_context"] = {
                "project_type": ctx.project_type,
                "modules_found": len(ctx.modules),
                "providers_found": len(ctx.providers),
                "scan_findings": ctx.scan_results.get("total_findings", 0),
                "blast_radius_components": ctx.blast_radius.get("total_components", 0),
                "code_files": len(ctx.code_files),
                "collection_notes": ctx.errors,
            }
            s.set_attribute("findings", ctx.scan_results.get("total_findings", 0))
            s.set_attribute("code_files", len(ctx.code_files))
            return result

    def review_code(self, directory: str) -> Dict[str, Any]:
        """Review raw IaC code with AI (no thothctl service context)."""
        code_files = self.code_reviewer.collect_code_for_review(directory)
        if not code_files:
            return {"summary": {"total_issues": 0}, "issues": [], "overall_assessment": "No IaC files found."}

        if not self.cost_tracker.check_budget():
            return {"summary": {"total_issues": 0}, "issues": [],
                    "overall_assessment": "Budget limit reached. Cannot perform AI review."}

        formatted = self.code_reviewer.format_for_ai(code_files)
        return self._call_ai(SYSTEM_CODE_REVIEWER, formatted, "review_code",
                             fallback=lambda: {"summary": {"total_issues": 0}, "issues": [],
                                               "overall_assessment": "AI review failed."})

    def generate_fixes(self, directory: str, scan_results: Dict = None,
                       severity_filter: str = None) -> Dict[str, Any]:
        """Generate actionable code fixes for scan findings."""
        with span("ai_agent.generate_fixes", {"directory": directory, "severity_filter": severity_filter or "all"}) as s:
            if not scan_results:
                analyzer = ReportAnalyzer()
                reports_dir = Path(directory) / "Reports"
                if reports_dir.exists():
                    scan_results = analyzer.parse_scan_results(str(reports_dir))
                else:
                    analysis = self.analyze_directory(directory)
                    return self._fixes_from_analysis(analysis, directory)

            if scan_results.get("total_findings", 0) == 0:
                return {"fixes": [], "skipped": [], "summary": {"total_findings": 0, "fixes_generated": 0, "skipped": 0}}

            code_files = self.code_reviewer.collect_code_for_review(directory)

            if not self.cost_tracker.check_budget():
                s.set_attribute("fallback", "pattern_fixes")
                return self._pattern_fixes(scan_results, code_files, severity_filter)

            content = self._format_fix_request(scan_results, code_files, severity_filter)

            # Use compact fix prompt for Ollama
            if self._provider.name == "ollama":
                fix_prompt = (
                    "IaC fix generator. Generate fixes for the STACK files (where modules are called), "
                    "NOT inside .terraform/modules/. Add missing parameters to module blocks.\n"
                    "Respond with JSON: {\"fixes\":[{\"fix_id\":\"fix_001\",\"finding_id\":\"check_id\","
                    "\"file\":\"stack main.tf path\",\"severity\":\"HIGH\",\"description\":\"what\","
                    "\"original\":\"exact module block code\",\"replacement\":\"fixed module block with new params\"}],"
                    "\"summary\":{\"total_findings\":N,\"fixes_generated\":N,\"skipped\":N}}"
                )
            else:
                fix_prompt = SYSTEM_FIX_GENERATOR

            result = self._call_ai(fix_prompt, content, "generate_fixes",
                                   fallback=lambda: self._pattern_fixes(scan_results, code_files, severity_filter))
            s.set_attribute("fixes_generated", len(result.get("fixes", [])))
            return result

    def _format_fix_request(self, scan_results: Dict, code_files: Dict,
                            severity_filter: str = None) -> str:
        """Format findings + code + org policy into a fix request for the AI."""
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        min_sev = severity_order.get((severity_filter or "LOW").upper(), 3)

        sections = []

        # Add org policy context if available
        org_rules = self._load_org_policy_context()
        if org_rules:
            sections.append("# Organization Rules (fixes MUST comply)\n")
            sections.append(org_rules)
            sections.append("")

        sections.append("# Findings to Fix\n")
        for tool, data in scan_results.get("tools", {}).items():
            for f in data.get("findings", []):
                sev = f.get("severity", "MEDIUM").upper()
                if severity_order.get(sev, 2) <= min_sev:
                    file_path = f.get("file", "")
                    # Map .terraform/modules/ findings to the stack module call
                    if ".terraform/modules/" in file_path or ".terraform\\modules\\" in file_path:
                        resource = f.get("resource", "")
                        sections.append(
                            f"- [{sev}] {f.get('check_id', '')}: {f.get('check_name', '')} "
                            f"resource={resource} (fix in the MODULE CALL, not module source)"
                        )
                    else:
                        sections.append(
                            f"- [{sev}] {f.get('check_id', '')}: {f.get('check_name', '')} "
                            f"in {file_path} resource={f.get('resource', '')}"
                        )
                    if f.get("guideline"):
                        sections.append(f"  Guideline: {f['guideline']}")

        sections.append("\n# Affected Code Files\n")
        char_budget = 25000 if self._provider.name != "ollama" else 8000
        used = 0
        for path, content in sorted(code_files.items()):
            entry = f"\n--- {path} ---\n{content}\n"
            if used + len(entry) > char_budget:
                sections.append("[Truncated: additional files omitted]")
                break
            sections.append(entry)
            used += len(entry)

        return "\n".join(sections)


    def _load_org_policy_context(self) -> str:
        """Load org policy rules as context for fix generation."""
        from ..check.org_policy_loader import get_org_policy_path
        org_path = get_org_policy_path()
        if not org_path:
            return ""

        parts = []
        rules_file = Path(org_path) / "rules" / "base.toml"
        if rules_file.exists():
            content = rules_file.read_text()
            # Extract key rules compactly
            for line in content.splitlines():
                if any(k in line for k in ["required_tags", "pattern", "public_ingress", "enforcement"]):
                    parts.append(line.strip())

        # Add naming/tagging rego summaries
        for rego in (Path(org_path) / "shared" / "policy").glob("*.rego"):
            text = rego.read_text()
            for line in text.splitlines():
                if line.startswith(("required_tags", "naming_pattern", "deny[", "warn[")):
                    parts.append(line.strip())

        return "\n".join(parts[:15])  # Cap at 15 lines to save tokens

    def _fixes_from_analysis(self, analysis: Dict, directory: str) -> Dict:
        """Extract fix suggestions from an existing AI analysis."""
        fixes = []
        for i, rec in enumerate(analysis.get("recommendations", [])):
            if isinstance(rec, str) and any(kw in rec.lower() for kw in ["add", "enable", "configure", "set", "use"]):
                fixes.append({
                    "fix_id": f"rec_{i:03d}",
                    "finding_id": "",
                    "file": "",
                    "fix_type": "manual",
                    "severity": "MEDIUM",
                    "description": rec,
                    "original": "",
                    "replacement": "",
                    "validation": "Manual review required",
                })
        return {"fixes": fixes, "skipped": [], "summary": {
            "total_findings": analysis.get("summary", {}).get("total_findings", 0),
            "fixes_generated": len(fixes), "skipped": 0,
        }}

    @staticmethod
    def _pattern_fixes(scan_results: Dict, code_files: Dict,
                       severity_filter: str = None) -> Dict:
        """Fallback: generate fixes from known patterns without AI."""
        from .utils.fix_patterns import get_pattern_fix

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        min_sev = severity_order.get((severity_filter or "LOW").upper(), 3)

        fixes, skipped = [], []
        idx = 0
        for tool, data in scan_results.get("tools", {}).items():
            for f in data.get("findings", []):
                sev = f.get("severity", "MEDIUM").upper()
                if severity_order.get(sev, 2) > min_sev:
                    continue
                check_id = f.get("check_id", "")
                fix = get_pattern_fix(check_id, f, code_files)
                if fix:
                    fix["fix_id"] = f"fix_{idx:03d}"
                    fixes.append(fix)
                    idx += 1
                else:
                    skipped.append({"finding_id": check_id, "reason": "No pattern available"})

        return {"fixes": fixes, "skipped": skipped, "summary": {
            "total_findings": scan_results.get("total_findings", 0),
            "fixes_generated": len(fixes), "skipped": len(skipped),
        }, "_note": "Pattern-based fixes (AI unavailable or budget exceeded)"}

    def get_cost_report(self, period: str = "daily") -> Dict[str, Any]:
        return self.cost_tracker.get_cost_report(period)

    # -- Private helpers --

    def _call_ai(self, system_prompt: str, user_content: str,
                 operation: str, fallback=None) -> Dict[str, Any]:
        """Send to AI provider, track cost, fall back on error."""
        try:
            ai_result = self._provider.analyze(system_prompt, user_content)
            usage = ai_result.pop("_usage", {})
            self.cost_tracker.record_usage(
                provider=self._provider.name,
                model=self._provider.model,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                operation=operation,
            )
            return ai_result
        except Exception as e:
            logger.error(f"AI call failed ({operation}): {e}")
            if fallback:
                return fallback()
            return self._empty_result()

    @staticmethod
    def _emit_status(msg: str) -> None:
        """Print a status message visible during the spinner."""
        from rich.console import Console
        Console(stderr=True).print(f"[dim]{msg}[/dim]")

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {
            "summary": {"total_findings": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
            "findings": [],
            "risk_score": 0,
            "recommendations": ["No security findings detected."],
        }

    @staticmethod
    def _basic_analysis(scan_results: Dict, risk: Dict) -> Dict[str, Any]:
        """Fallback analysis without AI."""
        findings = []
        for tool_data in scan_results.get("tools", {}).values():
            for f in tool_data.get("findings", [])[:20]:
                findings.append({
                    "id": f.get("check_id", ""),
                    "severity": f.get("severity", "MEDIUM"),
                    "title": f.get("check_name", ""),
                    "description": f.get("guideline", ""),
                    "resource": f.get("resource", ""),
                    "remediation": "",
                    "code_example": "",
                    "compliance": [],
                })

        return {
            "summary": {
                "total_findings": risk["total_findings"],
                **{k.lower(): v for k, v in risk["by_severity"].items()},
            },
            "findings": findings,
            "risk_score": risk["risk_score"],
            "recommendations": [
                "AI analysis unavailable. Review findings manually.",
                f"Risk level: {risk['risk_level']}",
            ],
            "_note": "Basic analysis (AI unavailable or budget exceeded)",
        }
