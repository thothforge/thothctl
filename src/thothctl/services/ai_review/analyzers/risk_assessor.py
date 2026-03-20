"""Risk assessor - scores and prioritizes security findings."""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

SEVERITY_WEIGHTS = {"CRITICAL": 10, "HIGH": 7, "MEDIUM": 4, "LOW": 1}


class RiskAssessor:
    """Calculates risk scores from scan findings without AI."""

    def assess_risk(self, scan_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate a basic risk assessment from parsed scan results."""
        all_findings: List[Dict] = []
        for tool_data in scan_results.get("tools", {}).values():
            all_findings.extend(tool_data.get("findings", []))

        if not all_findings:
            return {
                "risk_score": 0,
                "risk_level": "LOW",
                "total_findings": 0,
                "by_severity": {},
                "top_findings": [],
            }

        by_severity: Dict[str, int] = {}
        weighted_sum = 0
        for f in all_findings:
            sev = f.get("severity", "MEDIUM").upper()
            by_severity[sev] = by_severity.get(sev, 0) + 1
            weighted_sum += SEVERITY_WEIGHTS.get(sev, 4)

        # Normalize to 0-100 scale (cap at 100)
        risk_score = min(100, weighted_sum * 2)

        if risk_score >= 80:
            risk_level = "CRITICAL"
        elif risk_score >= 50:
            risk_level = "HIGH"
        elif risk_score >= 25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Top findings sorted by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        sorted_findings = sorted(all_findings, key=lambda x: severity_order.get(x.get("severity", "MEDIUM").upper(), 2))

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "total_findings": len(all_findings),
            "by_severity": by_severity,
            "top_findings": sorted_findings[:10],
        }
