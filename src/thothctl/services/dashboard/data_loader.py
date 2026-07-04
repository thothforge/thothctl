import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

class DashboardDataLoader:
    """Optimized data loader for dashboard."""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.reports_dir = self.base_dir / "Reports"
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    def get_inventory_data(self) -> Dict[str, Any]:
        """Load from existing inventory JSON files."""
        cache_key = "inventory"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            inventory_files = list(self.reports_dir.glob("**/InventoryIaC_*.json"))
            if not inventory_files:
                return {
                    "error": "No inventory data found", 
                    "action": "Run 'thothctl inventory iac --check-versions' to generate inventory",
                    "command": "thothctl inventory iac --check-versions"
                }
            
            latest_file = max(inventory_files, key=lambda f: f.stat().st_mtime)
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._cache_data(cache_key, data)
            return data
            
        except json.JSONDecodeError as e:
            return {
                "error": f"Invalid inventory file format: {str(e)}", 
                "action": "Regenerate inventory data",
                "command": "thothctl inventory iac --check-versions"
            }
        except FileNotFoundError as e:
            return {
                "error": f"Inventory file not found: {str(e)}", 
                "action": "Generate inventory data",
                "command": "thothctl inventory iac --check-versions"
            }
        except Exception as e:
            return {
                "error": f"Error loading inventory: {str(e)}", 
                "action": "Check file permissions and try again",
                "command": "ls -la Reports/"
            }
    
    def get_scan_results(self) -> Dict[str, Any]:
        """Load from existing scan report files."""
        cache_key = "scan_results"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            results = {"reports": [], "summary": {"total_issues": 0}, "tools": []}
            
            html_reports = list(self.reports_dir.rglob("*.html"))
            xml_reports = list(self.reports_dir.rglob("*.xml"))
            
            # Track which tools have reports
            tools_found = set()

            for html_file in html_reports:
                rel_path = str(html_file.relative_to(self.base_dir))
                # Determine tool from path
                tool = "other"
                for t in ("checkov", "trivy", "kics", "opa", "terraform-compliance"):
                    if t in rel_path:
                        tool = t
                        tools_found.add(t)
                        break

                results["reports"].append({
                    "file": rel_path,
                    "type": "html",
                    "tool": tool,
                    "timestamp": datetime.fromtimestamp(html_file.stat().st_mtime).isoformat(),
                    "size": html_file.stat().st_size
                })
            
            for xml_file in xml_reports:
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    failures = int(root.get('failures', 0))
                    errors = int(root.get('errors', 0))
                    results["summary"]["total_issues"] += failures + errors
                except:
                    pass
            
            results["tools"] = sorted(tools_found)

            if not results["reports"]:
                return {
                    "error": "No scan results found",
                    "action": "Run security scan to generate reports",
                    "command": "thothctl scan iac --recursive"
                }
            
            self._cache_data(cache_key, results)
            return results
            
        except Exception as e:
            return {
                "error": f"Error loading scan results: {str(e)}",
                "action": "Check file permissions and try again", 
                "command": "ls -la Reports/"
            }

    def get_findings(self, tool: str = None, severity: str = None, search: str = None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Load individual findings from JSON reports with filtering."""
        cache_key = "findings_all"
        if not self._is_cache_valid(cache_key):
            all_findings = []

            # Parse Checkov JSON reports
            checkov_dir = self.reports_dir / "checkov" / "security-scan"
            if checkov_dir.exists():
                for json_file in checkov_dir.rglob("results_json.json"):
                    try:
                        with open(json_file, "r") as f:
                            data = json.load(f)
                        results = data.get("results", {})
                        # Handle both formats
                        failed_checks = results.get("failed_checks", [])
                        if not failed_checks:
                            for check_type_data in results.values():
                                if isinstance(check_type_data, dict):
                                    failed_checks.extend(check_type_data.get("failed_checks", []))
                        for check in failed_checks:
                            all_findings.append({
                                "tool": "checkov",
                                "id": check.get("check_id", ""),
                                "severity": check.get("severity", "MEDIUM") or "MEDIUM",
                                "title": check.get("check_result", {}).get("name", check.get("name", "")),
                                "name": check.get("name", ""),
                                "file": check.get("file_path", ""),
                                "line": check.get("file_line_range", [0, 0])[0],
                                "resource": check.get("resource", ""),
                                "guideline": check.get("guideline", ""),
                            })
                    except (json.JSONDecodeError, KeyError):
                        continue

            # Parse OPA/Conftest JSON reports
            opa_report = self.reports_dir / "opa" / "conftest_results.json"
            if opa_report.exists():
                try:
                    with open(opa_report, "r") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for result in data:
                            filename = result.get("filename", "")
                            for failure in result.get("failures", []):
                                all_findings.append({
                                    "tool": "opa",
                                    "id": "OPA",
                                    "severity": "HIGH",
                                    "title": failure.get("msg", ""),
                                    "name": failure.get("msg", ""),
                                    "file": filename,
                                    "line": 0,
                                    "resource": "",
                                    "guideline": "",
                                })
                            for warning in result.get("warnings", []):
                                all_findings.append({
                                    "tool": "opa",
                                    "id": "OPA",
                                    "severity": "MEDIUM",
                                    "title": warning.get("msg", ""),
                                    "name": warning.get("msg", ""),
                                    "file": filename,
                                    "line": 0,
                                    "resource": "",
                                    "guideline": "",
                                })
                except (json.JSONDecodeError, KeyError):
                    pass

            # Parse Trivy JSON reports
            trivy_dir = self.reports_dir / "trivy"
            if trivy_dir.exists():
                for json_file in trivy_dir.rglob("results.json"):
                    try:
                        with open(json_file, "r") as f:
                            data = json.load(f)
                        for result in data.get("Results", []):
                            for misconf in result.get("Misconfigurations", []):
                                all_findings.append({
                                    "tool": "trivy",
                                    "id": misconf.get("ID", ""),
                                    "severity": misconf.get("Severity", "MEDIUM"),
                                    "title": misconf.get("Title", ""),
                                    "name": misconf.get("Message", misconf.get("Title", "")),
                                    "file": result.get("Target", ""),
                                    "line": 0,
                                    "resource": misconf.get("CauseMetadata", {}).get("Resource", ""),
                                    "guideline": misconf.get("PrimaryURL", ""),
                                })
                    except (json.JSONDecodeError, KeyError):
                        continue

            # Parse KICS JSON reports
            kics_report = self.reports_dir / "kics-results.json"
            if kics_report.exists():
                try:
                    with open(kics_report, "r") as f:
                        data = json.load(f)
                    for query in data.get("queries", []):
                        sev = (query.get("severity") or "MEDIUM").upper()
                        for file_entry in query.get("files", []):
                            all_findings.append({
                                "tool": "kics",
                                "id": query.get("query_id", "")[:12],
                                "severity": sev,
                                "title": query.get("query_name", ""),
                                "name": query.get("query_name", ""),
                                "file": file_entry.get("file_name", ""),
                                "line": file_entry.get("line", 0),
                                "resource": file_entry.get("resource_type", ""),
                                "guideline": query.get("query_url", ""),
                            })
                except (json.JSONDecodeError, KeyError):
                    pass

            self._cache_data(cache_key, all_findings)
        else:
            all_findings = self.cache[cache_key]["data"]

        # Apply filters
        filtered = all_findings
        if tool:
            filtered = [f for f in filtered if f["tool"] == tool]
        if severity:
            filtered = [f for f in filtered if f["severity"].upper() == severity.upper()]
        if search:
            search_lower = search.lower()
            filtered = [f for f in filtered if (
                search_lower in f.get("title", "").lower() or
                search_lower in f.get("file", "").lower() or
                search_lower in f.get("resource", "").lower() or
                search_lower in f.get("id", "").lower()
            )]

        # Severity counts for the filtered set
        sev_counts = {}
        for f in filtered:
            s = f.get("severity", "UNKNOWN").upper()
            sev_counts[s] = sev_counts.get(s, 0) + 1

        # Tool counts
        tool_counts = {}
        for f in filtered:
            t = f.get("tool", "unknown")
            tool_counts[t] = tool_counts.get(t, 0) + 1

        total = len(filtered)
        page = filtered[offset:offset + limit]

        return {
            "findings": page,
            "total": total,
            "offset": offset,
            "limit": limit,
            "severity_counts": sev_counts,
            "tool_counts": tool_counts,
        }
    
    def get_cost_analysis(self) -> Dict[str, Any]:
        """Load from terraform plan files or cost analysis cache."""
        cache_key = "cost_analysis"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            cost_files = list(self.reports_dir.glob("**/cost_analysis_*.json"))
            if cost_files:
                latest_file = max(cost_files, key=lambda f: f.stat().st_mtime)
                with open(latest_file) as f:
                    data = json.load(f)
                self._cache_data(cache_key, data)
                return data
            
            plan_files = list(self.base_dir.rglob("tfplan.json"))
            if plan_files:
                return {
                    "message": "Terraform plan found. Generate cost analysis to see estimates.", 
                    "action": "Run cost analysis command",
                    "command": "thothctl check iac -type cost-analysis --recursive",
                    "plan_files": len(plan_files)
                }
            
            return {
                "message": "No cost data available. Create terraform plan first.",
                "action": "Generate terraform plan then run cost analysis",
                "command": "terraform plan -out=tfplan && thothctl check iac -type cost-analysis"
            }
            
        except json.JSONDecodeError:
            return {
                "error": "Invalid cost analysis file format", 
                "action": "Regenerate cost analysis",
                "command": "thothctl check iac -type cost-analysis --recursive"
            }
        except Exception as e:
            return {
                "error": f"Error loading cost data: {str(e)}", 
                "action": "Check file permissions and try again",
                "command": "ls -la Reports/"
            }
    
    def get_blast_radius(self) -> Dict[str, Any]:
        """Load from cached blast radius analysis."""
        cache_key = "blast_radius"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            blast_files = list(self.reports_dir.glob("**/blast_radius_*.json"))
            if blast_files:
                latest_file = max(blast_files, key=lambda f: f.stat().st_mtime)
                with open(latest_file) as f:
                    data = json.load(f)
                self._cache_data(cache_key, data)
                return data
            
            return {
                "message": "No risk analysis available.", 
                "action": "Run project check to generate blast radius analysis",
                "command": "thothctl check iac -type blast-radius --recursive"
            }
            
        except json.JSONDecodeError:
            return {"error": "Invalid blast radius file format", "action": "Regenerate", "command": "thothctl check iac -type blast-radius --recursive"}
        except Exception as e:
            return {"error": f"Error loading risk data: {str(e)}"}

    def get_drift_data(self) -> Dict[str, Any]:
        """Load from existing drift detection reports."""
        cache_key = "drift"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]

        try:
            drift_files = list(self.reports_dir.glob("**/drift_*.json"))
            if drift_files:
                latest_file = max(drift_files, key=lambda f: f.stat().st_mtime)
                with open(latest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache_data(cache_key, data)
                return data

            return {
                "message": "No drift data available.",
                "action": "Run drift detection",
                "command": "thothctl check iac -type drift --recursive"
            }
        except Exception as e:
            return {"error": f"Error loading drift data: {str(e)}"}

    def get_ai_usage(self) -> Dict[str, Any]:
        """Load AI usage/cost data from cost logs."""
        cache_key = "ai_usage"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]

        try:
            from datetime import date as date_mod
            cost_dir = Path(".thothctl/ai_costs")
            if not cost_dir.exists():
                return {
                    "message": "No AI usage data.",
                    "action": "Run AI review to generate usage logs",
                    "command": "thothctl ai-review analyze -d ."
                }

            records = []
            month_prefix = date_mod.today().strftime("%Y-%m")
            for log_file in sorted(cost_dir.glob(f"{month_prefix}*.jsonl")):
                with open(log_file) as f:
                    for line in f:
                        if line.strip():
                            records.append(json.loads(line.strip()))

            if not records:
                return {"message": "No AI usage this month.", "records": []}

            total_cost = sum(r.get("cost", 0) for r in records)
            total_input = sum(r.get("input_tokens", 0) for r in records)
            total_output = sum(r.get("output_tokens", 0) for r in records)

            data = {
                "total_cost": total_cost,
                "total_requests": len(records),
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "records": records[-20:],  # Last 20 records
            }
            self._cache_data(cache_key, data)
            return data
        except Exception as e:
            return {"error": f"Error loading AI usage: {str(e)}"}
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self.cache:
            return False
        return time.time() - self.cache[key]["timestamp"] < self.cache_ttl
    
    def _cache_data(self, key: str, data: Dict[str, Any]):
        """Cache data with timestamp."""
        self.cache[key] = {
            "data": data,
            "timestamp": time.time()
        }
