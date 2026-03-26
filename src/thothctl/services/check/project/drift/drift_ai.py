"""AI-powered drift analysis — plugs drift results into the existing AI agent orchestrator."""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SYSTEM_DRIFT_ANALYST = """You are an expert Infrastructure as Code drift analyst.
You are analyzing infrastructure drift detected by ThothCTL's drift detection engine.

Drift occurs when live cloud resources differ from what is defined in IaC (Terraform/OpenTofu).
Each drifted resource has:
- address: the terraform resource address
- resource_type: the cloud resource type
- drift_type: changed (attributes differ), deleted (removed from cloud), unmanaged (not in IaC)
- severity: critical/high/medium/low
- changed_attributes: which attributes drifted
- actions: the terraform plan actions

Analyze the drift results and provide:
1. Security impact assessment — could any drift introduce vulnerabilities?
2. Root cause hypothesis — likely cause of each drift (manual change, external automation, provider update)
3. Prioritized remediation plan — which drifts to fix first and how
4. Risk score (0-100) for the overall drift state
5. Whether deployment should proceed or be blocked

Respond in valid JSON:
{
  "summary": {
    "risk_score": int,
    "should_block_deploy": bool,
    "total_analyzed": int,
    "security_risks": int,
    "recommendation": "string"
  },
  "findings": [
    {
      "address": "string",
      "security_impact": "none|low|medium|high|critical",
      "likely_cause": "string",
      "remediation": "string",
      "priority": int
    }
  ],
  "recommendations": ["string"]
}
"""


def format_drift_for_ai(summary_dict: Dict[str, Any],
                        trend: Optional[Dict[str, Any]] = None) -> str:
    """Format drift summary into a context string for the AI agent."""
    sections = ["# Drift Analysis Request\n"]

    sections.append(f"## Overview")
    sections.append(f"- Stacks scanned: {summary_dict.get('total_stacks', 0)}")
    sections.append(f"- Total resources: {summary_dict.get('total_resources', 0)}")
    sections.append(f"- Drifted resources: {summary_dict.get('total_drifted', 0)}")
    sections.append(f"- IaC coverage: {summary_dict.get('overall_coverage', 100)}%")

    if trend and trend.get("snapshots", 0) > 1:
        sections.append(f"\n## Coverage Trend")
        sections.append(f"- Trend: {trend['trend']} (delta: {trend['coverage_delta']}%)")
        sections.append(f"- Range: {trend['min_coverage']}% — {trend['max_coverage']}%")
        sections.append(f"- Peak drifted: {trend['peak_drifted']}")

    sections.append(f"\n## Drifted Resources")
    for result in summary_dict.get("results", []):
        if result.get("error"):
            sections.append(f"\n### {result['directory']} — ERROR: {result['error']}")
            continue
        for dr in result.get("drifted_resources", []):
            attrs = ", ".join(dr.get("changed_attributes", [])[:8])
            sections.append(
                f"- [{dr['severity'].upper()}] `{dr['address']}` "
                f"({dr['resource_type']}) — {dr['drift_type']} "
                f"| actions={dr['actions']} | changed=[{attrs}]"
            )

    return "\n".join(sections)


def analyze_drift_with_ai(
    summary_dict: Dict[str, Any],
    trend: Optional[Dict[str, Any]] = None,
    provider: str = None,
    model: str = None,
) -> Dict[str, Any]:
    """Run AI analysis on drift results using the existing orchestrator infrastructure.

    Returns the AI analysis dict, or a fallback offline analysis if AI is unavailable.
    """
    context = format_drift_for_ai(summary_dict, trend)
    if not context.strip():
        return {"error": "No drift data to analyze"}

    try:
        from ...ai_review.orchestrator import AgentOrchestrator
        from ...ai_review.memory import MemoryConfig

        orchestrator = AgentOrchestrator(
            provider=provider, model=model,
            max_parallel=1, memory_config=MemoryConfig(),
        )
        result = orchestrator._call_ai(
            type("Task", (), {
                "role": type("R", (), {"value": "drift"})(),
                "system_prompt": SYSTEM_DRIFT_ANALYST,
                "context": context,
                "post_process": None,
            })()
        )
        return result
    except Exception as e:
        logger.warning(f"AI drift analysis unavailable: {e}")
        return _offline_drift_analysis(summary_dict)


def _offline_drift_analysis(summary_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback analysis when AI provider is not configured."""
    total = summary_dict.get("total_drifted", 0)
    coverage = summary_dict.get("overall_coverage", 100)

    # Simple heuristic risk score
    risk = min(100, int((100 - coverage) * 1.5))

    security_risks = 0
    findings = []
    for result in summary_dict.get("results", []):
        for dr in result.get("drifted_resources", []):
            rtype = dr.get("resource_type", "")
            is_security = any(k in rtype for k in ("security_group", "iam", "kms", "secret", "policy", "acl"))
            if is_security:
                security_risks += 1
            findings.append({
                "address": dr["address"],
                "security_impact": "high" if is_security else "low",
                "likely_cause": "manual change or external automation",
                "remediation": f"Run terraform apply to reconcile, or update IaC to match current state",
                "priority": 1 if dr["severity"] == "critical" else 2 if dr["severity"] == "high" else 3,
            })

    return {
        "summary": {
            "risk_score": risk,
            "should_block_deploy": risk > 70 or security_risks > 0,
            "total_analyzed": total,
            "security_risks": security_risks,
            "recommendation": "Resolve critical and security-related drift before deploying"
            if security_risks > 0 else "Review drifted resources and reconcile",
        },
        "findings": sorted(findings, key=lambda f: f["priority"])[:20],
        "recommendations": _generate_recommendations(summary_dict, security_risks),
        "_note": "Offline analysis (no AI provider configured)",
    }


def _generate_recommendations(summary_dict: Dict[str, Any], security_risks: int) -> List[str]:
    recs = []
    coverage = summary_dict.get("overall_coverage", 100)
    if coverage < 80:
        recs.append("IaC coverage is critically low — prioritize importing unmanaged resources")
    elif coverage < 90:
        recs.append("IaC coverage is below target — schedule drift remediation sprint")
    if security_risks > 0:
        recs.append(f"{security_risks} security-sensitive resource(s) have drifted — investigate immediately")
    total = summary_dict.get("total_drifted", 0)
    if total > 10:
        recs.append("High drift count — consider enabling scheduled drift detection in CI/CD")
    recs.append("Run `thothctl check iac -type drift --post-to-pr` in CI to track drift per PR")
    return recs
