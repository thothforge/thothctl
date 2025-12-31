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
            results = {"reports": [], "summary": {"total_issues": 0}}
            
            html_reports = list(self.reports_dir.rglob("*.html"))
            xml_reports = list(self.reports_dir.rglob("*.xml"))
            
            for html_file in html_reports:
                if "index.html" not in html_file.name:
                    results["reports"].append({
                        "file": str(html_file.relative_to(self.base_dir)),
                        "type": "html",
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
                "command": "thothctl check project --blast-radius"
            }
            
        except json.JSONDecodeError:
            return {
                "error": "Invalid blast radius file format", 
                "action": "Regenerate blast radius analysis",
                "command": "thothctl check project --blast-radius"
            }
        except Exception as e:
            return {
                "error": f"Error loading risk data: {str(e)}", 
                "action": "Check file permissions and try again",
                "command": "ls -la Reports/"
            }
    
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
