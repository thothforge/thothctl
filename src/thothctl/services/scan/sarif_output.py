"""SARIF output — export scan findings in SARIF 2.1.0 format.

SARIF (Static Analysis Results Interchange Format) is supported by:
- GitHub Code Scanning / Advanced Security
- Azure DevOps
- VS Code SARIF Viewer extension
- Many other IDE and CI/CD tools
"""
import json
import os
from datetime import datetime, timezone
from typing import Dict, List


SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json"

SEVERITY_TO_LEVEL = {
    "CRITICAL": "error",
    "HIGH": "error",
    "MEDIUM": "warning",
    "LOW": "note",
    "INFO": "note",
}


def build_sarif(results: dict, directory: str) -> dict:
    """Build a SARIF 2.1.0 document from scan results."""
    runs = []

    for tool_name, tool_data in results.items():
        if tool_name == "summary" or not isinstance(tool_data, dict):
            continue

        findings = tool_data.get("findings", [])
        if not findings:
            continue

        # Collect unique rules
        rules_map: Dict[str, dict] = {}
        sarif_results: List[dict] = []

        for f in findings:
            rule_id = f.get("id", "unknown")
            if rule_id not in rules_map:
                rules_map[rule_id] = {
                    "id": rule_id,
                    "shortDescription": {"text": f.get("title", rule_id)},
                    "defaultConfiguration": {
                        "level": SEVERITY_TO_LEVEL.get(f.get("severity", "MEDIUM"), "warning")
                    },
                    "properties": {"severity": f.get("severity", "MEDIUM")},
                }

            # Build result
            file_path = f.get("file", "")
            line = f.get("line", 1) or 1

            sarif_result = {
                "ruleId": rule_id,
                "level": SEVERITY_TO_LEVEL.get(f.get("severity", "MEDIUM"), "warning"),
                "message": {"text": f.get("title", "")},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": file_path, "uriBaseId": "%SRCROOT%"},
                            "region": {"startLine": line},
                        }
                    }
                ],
            }
            if f.get("resource"):
                sarif_result["message"]["text"] += f" (resource: {f['resource']})"

            sarif_results.append(sarif_result)

        run = {
            "tool": {
                "driver": {
                    "name": tool_name,
                    "version": "1.0.0",
                    "informationUri": _tool_uri(tool_name),
                    "rules": list(rules_map.values()),
                }
            },
            "results": sarif_results,
            "invocations": [
                {
                    "executionSuccessful": tool_data.get("status") == "COMPLETE",
                    "endTimeUtc": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }
        runs.append(run)

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": runs,
    }


def save_sarif(results: dict, directory: str, reports_dir: str) -> str:
    """Build and save SARIF file. Returns the file path."""
    sarif = build_sarif(results, directory)
    sarif_path = os.path.join(reports_dir, "scan_results.sarif")
    with open(sarif_path, "w") as f:
        json.dump(sarif, f, indent=2)
    return sarif_path


def _tool_uri(tool_name: str) -> str:
    uris = {
        "checkov": "https://www.checkov.io/",
        "trivy": "https://trivy.dev/",
        "tfsec": "https://aquasecurity.github.io/tfsec/",
        "kics": "https://docs.kics.io/",
        "opa": "https://www.openpolicyagent.org/",
    }
    return uris.get(tool_name, "https://thothctl.readthedocs.io/")
