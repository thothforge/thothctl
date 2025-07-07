"""Module compatibility service for checking Terraform module schema changes."""
import logging
import requests
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
import re
import time

logger = logging.getLogger(__name__)


@dataclass
class CompatibilityIssue:
    """Represents a compatibility issue found during schema comparison."""
    severity: str  # "breaking", "warning", "info"
    category: str  # "input", "output", "dependency", "version"
    message: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass
class ModuleCompatibilityReport:
    """Represents a module compatibility analysis report."""
    module_name: str
    namespace: str
    provider: str
    old_version: str
    new_version: str
    compatibility_level: str  # "compatible", "minor_issues", "breaking_changes"
    issues: List[CompatibilityIssue]
    summary: str
    upgrade_safe: bool


class ModuleCompatibilityService:
    """Service for checking Terraform module compatibility between versions."""
    
    def __init__(self, registry_base_url: str = "https://registry.terraform.io"):
        """Initialize the module compatibility service."""
        self.registry_base_url = registry_base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ThothCTL-Module-Compatibility-Checker/1.0'
        })
        self._rate_limit_delay = 0.5  # Delay between API calls to respect rate limits
    
    def parse_module_source(self, source: str) -> Optional[Tuple[str, str, str]]:
        """Parse module source to extract namespace, name, and provider."""
        try:
            # Handle different module source formats
            if source.startswith("./") or source.startswith("../") or source.startswith("/"):
                # Local module, skip
                return None
            
            if "git::" in source or source.startswith("git@"):
                # Git module, skip for now
                return None
            
            if source.startswith("http"):
                # HTTP module, skip for now
                return None
            
            # Registry module format: namespace/name/provider
            parts = source.split("/")
            if len(parts) >= 3:
                namespace = parts[0]
                name = parts[1]
                provider = parts[2]
                return namespace, name, provider
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to parse module source '{source}': {str(e)}")
            return None
    
    def get_module_schema(self, namespace: str, name: str, provider: str, version: str = "latest") -> Optional[Dict[str, Any]]:
        """Get module schema from Terraform Registry API."""
        try:
            if version == "latest":
                url = f"{self.registry_base_url}/v1/modules/{namespace}/{name}/{provider}"
            else:
                url = f"{self.registry_base_url}/v1/modules/{namespace}/{name}/{provider}/{version}"
            
            logger.debug(f"Fetching module schema from: {url}")
            
            # Add rate limiting
            time.sleep(self._rate_limit_delay)
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch module schema for {namespace}/{name}/{provider}@{version}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching module schema: {str(e)}")
            return None
    
    def get_module_versions(self, namespace: str, name: str, provider: str) -> List[str]:
        """Get available versions for a module."""
        try:
            url = f"{self.registry_base_url}/v1/modules/{namespace}/{name}/{provider}/versions"
            
            time.sleep(self._rate_limit_delay)
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            versions = [v['version'] for v in data.get('versions', [])]
            
            # Sort versions in descending order (newest first)
            return sorted(versions, key=lambda x: self._version_key(x), reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to fetch module versions for {namespace}/{name}/{provider}: {str(e)}")
            return []
    
    def _analyze_semantic_version_change(self, old_version: str, new_version: str) -> Dict[str, Any]:
        """Analyze semantic version changes to predict compatibility issues."""
        issues = []
        
        try:
            # Parse versions
            old_parts = self._parse_version(old_version)
            new_parts = self._parse_version(new_version)
            
            old_major, old_minor, old_patch = old_parts
            new_major, new_minor, new_patch = new_parts
            
            is_major_change = new_major > old_major
            is_minor_change = new_major == old_major and new_minor > old_minor
            is_patch_change = new_major == old_major and new_minor == old_minor and new_patch > old_patch
            
            if is_major_change:
                issues.append(CompatibilityIssue(
                    severity="breaking",
                    category="version",
                    message=f"Major version upgrade ({old_major}.x.x → {new_major}.x.x)",
                    old_value=f"v{old_version}",
                    new_value=f"v{new_version}",
                    recommendation="Major version changes typically include breaking changes. Review the module's CHANGELOG.md and migration guide before upgrading."
                ))
                
                # Add specific warnings for well-known modules
                module_warnings = self._get_known_module_warnings(old_version, new_version)
                issues.extend(module_warnings)
                
            elif is_minor_change:
                issues.append(CompatibilityIssue(
                    severity="warning",
                    category="version",
                    message=f"Minor version upgrade ({old_major}.{old_minor}.x → {new_major}.{new_minor}.x)",
                    old_value=f"v{old_version}",
                    new_value=f"v{new_version}",
                    recommendation="Minor version changes may include new features and deprecations. Review release notes for any deprecation warnings."
                ))
                
            elif is_patch_change:
                issues.append(CompatibilityIssue(
                    severity="info",
                    category="version",
                    message=f"Patch version upgrade ({old_version} → {new_version})",
                    old_value=f"v{old_version}",
                    new_value=f"v{new_version}",
                    recommendation="Patch versions typically contain bug fixes and should be safe to upgrade."
                ))
            
            return {
                'issues': issues,
                'is_major_change': is_major_change,
                'is_minor_change': is_minor_change,
                'is_patch_change': is_patch_change
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse version numbers {old_version} -> {new_version}: {e}")
            return {
                'issues': [CompatibilityIssue(
                    severity="warning",
                    category="version",
                    message=f"Unable to parse version format ({old_version} → {new_version})",
                    old_value=old_version,
                    new_value=new_version,
                    recommendation="Manually review module documentation for changes"
                )],
                'is_major_change': True,  # Assume breaking changes if we can't parse
                'is_minor_change': False,
                'is_patch_change': False
            }
    
    def _parse_version(self, version: str) -> Tuple[int, int, int]:
        """Parse a semantic version string into major, minor, patch components."""
        # Remove 'v' prefix if present
        version = version.lstrip('v')
        
        # Split by dots and convert to integers
        parts = version.split('.')
        
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        
        return (major, minor, patch)
    
    def _get_known_module_warnings(self, old_version: str, new_version: str) -> List[CompatibilityIssue]:
        """Get specific warnings for well-known modules with documented breaking changes."""
        issues = []
        
        # Add specific warnings for terraform-aws-modules/vpc/aws
        if "5." in old_version and "6." in new_version:
            issues.append(CompatibilityIssue(
                severity="breaking",
                category="module_specific",
                message="VPC module v6.x includes significant breaking changes",
                old_value="v5.x configuration",
                new_value="v6.x configuration",
                recommendation="Key changes in v6.x: 1) Default VPC endpoints changed, 2) NAT gateway configuration updated, 3) Some output names changed. Review the migration guide at: https://github.com/terraform-aws-modules/terraform-aws-vpc/blob/master/UPGRADE-6.0.md"
            ))
            
        # Add specific warnings for terraform-aws-modules/eks/aws  
        if "19." in old_version and "20." in new_version:
            issues.append(CompatibilityIssue(
                severity="breaking", 
                category="module_specific",
                message="EKS module v20.x includes breaking changes",
                old_value="v19.x configuration",
                new_value="v20.x configuration", 
                recommendation="Key changes in v20.x: 1) Node group configuration structure changed, 2) Some variable names updated, 3) Default security group rules modified. Review: https://github.com/terraform-aws-modules/terraform-aws-eks/blob/master/UPGRADE-20.0.md"
            ))
            
        return issues
    
    def _version_key(self, version: str) -> Tuple[int, ...]:
        """Convert version string to tuple for sorting."""
        try:
            # Remove 'v' prefix if present
            version = version.lstrip('v')
            # Split by dots and convert to integers
            return tuple(int(x) for x in version.split('.'))
        except:
            # Fallback for non-standard versions
            return (0, 0, 0)
    
    def compare_module_schemas(self, namespace: str, name: str, provider: str, 
                             old_version: str, new_version: str) -> ModuleCompatibilityReport:
        """Compare two module schema versions and identify compatibility issues."""
        
        module_name = f"{namespace}/{name}/{provider}"
        logger.info(f"Comparing module schemas: {module_name} {old_version} -> {new_version}")
        
        # First, perform semantic version analysis
        semantic_analysis = self._analyze_semantic_version_change(old_version, new_version)
        
        # Get basic module information from registry
        old_schema = self.get_module_schema(namespace, name, provider, old_version)
        new_schema = self.get_module_schema(namespace, name, provider, new_version)
        
        issues = []
        
        # Add semantic version analysis results
        issues.extend(semantic_analysis['issues'])
        
        # If we have schema data, perform detailed comparison
        if old_schema and new_schema:
            # Compare inputs
            issues.extend(self._compare_inputs(old_schema, new_schema))
            
            # Compare outputs  
            issues.extend(self._compare_outputs(old_schema, new_schema))
            
            # Compare dependencies
            issues.extend(self._compare_dependencies(old_schema, new_schema))
        else:
            # If we can't get detailed schema, rely on semantic versioning
            logger.warning(f"Unable to fetch detailed schema for {module_name}, using semantic version analysis")
            
        # Determine compatibility level
        breaking_issues = [i for i in issues if i.severity == "breaking"]
        warning_issues = [i for i in issues if i.severity == "warning"]
        
        # Override with semantic analysis if it indicates breaking changes
        if semantic_analysis['is_major_change'] and not breaking_issues:
            issues.append(CompatibilityIssue(
                severity="breaking",
                category="version",
                message=f"Major version change ({old_version} → {new_version}) likely contains breaking changes",
                old_value=old_version,
                new_value=new_version,
                recommendation="Review module changelog and documentation for breaking changes before upgrading"
            ))
            breaking_issues = [i for i in issues if i.severity == "breaking"]
        
        if breaking_issues:
            compatibility_level = "breaking_changes"
            upgrade_safe = False
            summary = f"Found {len(breaking_issues)} breaking change(s) that require code updates"
        elif warning_issues:
            compatibility_level = "minor_issues"
            upgrade_safe = True
            summary = f"Found {len(warning_issues)} minor issue(s) that may need attention"
        else:
            compatibility_level = "compatible"
            upgrade_safe = True
            summary = "No compatibility issues detected"
        
        return ModuleCompatibilityReport(
            module_name=module_name,
            namespace=namespace,
            provider=provider,
            old_version=old_version,
            new_version=new_version,
            compatibility_level=compatibility_level,
            issues=issues,
            summary=summary,
            upgrade_safe=upgrade_safe
        )
    
    def _compare_inputs(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> List[CompatibilityIssue]:
        """Compare module inputs between versions."""
        issues = []
        
        old_inputs = {inp.get('name'): inp for inp in old_schema.get('inputs', [])}
        new_inputs = {inp.get('name'): inp for inp in new_schema.get('inputs', [])}
        
        # Check for removed inputs
        for name, old_input in old_inputs.items():
            if name not in new_inputs:
                # Check if it was a required input
                has_default = old_input.get('default') is not None
                if not has_default:
                    issues.append(CompatibilityIssue(
                        severity="breaking",
                        category="input",
                        message=f"Required input variable '{name}' was removed",
                        old_value=f"required input",
                        new_value="removed",
                        recommendation=f"Remove references to '{name}' variable from your configuration"
                    ))
                else:
                    issues.append(CompatibilityIssue(
                        severity="info",
                        category="input",
                        message=f"Optional input variable '{name}' was removed",
                        old_value=f"optional input (default: {old_input.get('default')})",
                        new_value="removed",
                        recommendation=f"Remove references to '{name}' variable if any"
                    ))
        
        # Check for type changes in existing inputs
        for name, old_input in old_inputs.items():
            if name in new_inputs:
                new_input = new_inputs[name]
                old_type = old_input.get('type', 'any')
                new_type = new_input.get('type', 'any')
                
                if old_type != new_type:
                    issues.append(CompatibilityIssue(
                        severity="breaking",
                        category="input",
                        message=f"Input variable '{name}' type changed",
                        old_value=old_type,
                        new_value=new_type,
                        recommendation=f"Update '{name}' variable to match new type: {new_type}"
                    ))
                
                # Check for removed default values
                old_has_default = old_input.get('default') is not None
                new_has_default = new_input.get('default') is not None
                
                if old_has_default and not new_has_default:
                    issues.append(CompatibilityIssue(
                        severity="breaking",
                        category="input",
                        message=f"Input variable '{name}' no longer has a default value",
                        old_value=f"default: {old_input.get('default')}",
                        new_value="no default",
                        recommendation=f"Provide explicit value for '{name}' variable"
                    ))
        
        # Check for new required inputs
        for name, new_input in new_inputs.items():
            if name not in old_inputs:
                has_default = new_input.get('default') is not None
                if not has_default:
                    issues.append(CompatibilityIssue(
                        severity="breaking",
                        category="input",
                        message=f"New required input variable '{name}' was added",
                        old_value="not present",
                        new_value="required input",
                        recommendation=f"Add '{name}' variable to your configuration"
                    ))
                else:
                    issues.append(CompatibilityIssue(
                        severity="info",
                        category="input",
                        message=f"New optional input variable '{name}' was added",
                        old_value="not present",
                        new_value=f"optional input (default: {new_input.get('default')})",
                        recommendation=f"Consider using new '{name}' variable if needed"
                    ))
        
        return issues
    
    def _compare_outputs(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> List[CompatibilityIssue]:
        """Compare module outputs between versions."""
        issues = []
        
        old_outputs = {out.get('name'): out for out in old_schema.get('outputs', [])}
        new_outputs = {out.get('name'): out for out in new_schema.get('outputs', [])}
        
        # Check for removed outputs
        for name, old_output in old_outputs.items():
            if name not in new_outputs:
                issues.append(CompatibilityIssue(
                    severity="breaking",
                    category="output",
                    message=f"Output value '{name}' was removed",
                    old_value="available",
                    new_value="removed",
                    recommendation=f"Remove references to module.{name} output"
                ))
        
        # Check for type changes in outputs
        for name, old_output in old_outputs.items():
            if name in new_outputs:
                new_output = new_outputs[name]
                old_desc = old_output.get('description', '')
                new_desc = new_output.get('description', '')
                
                # If description changed significantly, it might indicate a breaking change
                if old_desc and new_desc and old_desc != new_desc:
                    issues.append(CompatibilityIssue(
                        severity="warning",
                        category="output",
                        message=f"Output '{name}' description changed",
                        old_value=old_desc[:100] + "..." if len(old_desc) > 100 else old_desc,
                        new_value=new_desc[:100] + "..." if len(new_desc) > 100 else new_desc,
                        recommendation=f"Review usage of '{name}' output for potential changes"
                    ))
        
        # Check for new outputs (informational)
        for name, new_output in new_outputs.items():
            if name not in old_outputs:
                issues.append(CompatibilityIssue(
                    severity="info",
                    category="output",
                    message=f"New output value '{name}' was added",
                    old_value="not present",
                    new_value="available",
                    recommendation=f"Consider using new '{name}' output if needed"
                ))
        
        return issues
    
    def _compare_dependencies(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> List[CompatibilityIssue]:
        """Compare module dependencies between versions."""
        issues = []
        
        old_deps = old_schema.get('dependencies', [])
        new_deps = new_schema.get('dependencies', [])
        
        # Convert to dictionaries for easier comparison
        old_providers = {}
        for dep in old_deps:
            if dep.get('name'):
                old_providers[dep['name']] = dep.get('version', '')
        
        new_providers = {}
        for dep in new_deps:
            if dep.get('name'):
                new_providers[dep['name']] = dep.get('version', '')
        
        # Check for new provider requirements
        for provider, version in new_providers.items():
            if provider not in old_providers:
                issues.append(CompatibilityIssue(
                    severity="warning",
                    category="dependency",
                    message=f"New provider dependency '{provider}' was added",
                    old_value="not required",
                    new_value=f"required: {version}",
                    recommendation=f"Ensure '{provider}' provider is available in your configuration"
                ))
        
        # Check for version requirement changes
        for provider, old_version in old_providers.items():
            if provider in new_providers:
                new_version = new_providers[provider]
                if old_version != new_version:
                    # Try to determine if this is a breaking change
                    if self._is_version_increase(old_version, new_version):
                        issues.append(CompatibilityIssue(
                            severity="warning",
                            category="dependency",
                            message=f"Provider '{provider}' minimum version increased",
                            old_value=old_version,
                            new_value=new_version,
                            recommendation=f"Ensure '{provider}' provider version {new_version} or higher is available"
                        ))
                    else:
                        issues.append(CompatibilityIssue(
                            severity="info",
                            category="dependency",
                            message=f"Provider '{provider}' version requirement changed",
                            old_value=old_version,
                            new_value=new_version,
                            recommendation=f"Review '{provider}' provider version requirements"
                        ))
        
        return issues
    
    def _is_version_increase(self, old_version: str, new_version: str) -> bool:
        """Check if new version requirement is higher than old version."""
        try:
            # Simple heuristic: if new version has higher numbers, it's likely an increase
            old_nums = re.findall(r'\d+', old_version)
            new_nums = re.findall(r'\d+', new_version)
            
            if old_nums and new_nums:
                old_major = int(old_nums[0]) if old_nums else 0
                new_major = int(new_nums[0]) if new_nums else 0
                return new_major > old_major
            
            return False
        except:
            return False
    
    def check_module_compatibility(self, module_source: str, current_version: str, 
                                 target_version: str = "latest") -> Optional[ModuleCompatibilityReport]:
        """Check compatibility for a single module upgrade."""
        
        parsed = self.parse_module_source(module_source)
        if not parsed:
            logger.debug(f"Skipping non-registry module: {module_source}")
            return None
        
        namespace, name, provider = parsed
        
        # If target version is "latest", get the actual latest version
        if target_version == "latest":
            versions = self.get_module_versions(namespace, name, provider)
            if not versions:
                logger.warning(f"No versions found for module {namespace}/{name}/{provider}")
                return None
            target_version = versions[0]  # First version is the latest
        
        # Skip if versions are the same
        if current_version == target_version:
            logger.debug(f"Module {namespace}/{name}/{provider} is already at target version {target_version}")
            return None
        
        return self.compare_module_schemas(namespace, name, provider, current_version, target_version)
    
    def check_inventory_modules_compatibility(self, inventory: Dict[str, Any]) -> Dict[str, Any]:
        """Check compatibility for all modules in an inventory."""
        
        logger.info("Starting module compatibility analysis for inventory")
        
        compatibility_reports = []
        
        for component_group in inventory.get("components", []):
            for component in component_group.get("components", []):
                component_type = component.get("type", "").lower()
                if component_type in ["module", "terraform_module", "terragrunt_module"]:
                    source = component.get("source", "")
                    current_version = component.get("version", "")
                    latest_version = component.get("latest_version", "")
                    
                    # Handle both single source and list of sources
                    if isinstance(source, list) and source:
                        source = source[0]  # Take the first source if it's a list
                    
                    # Handle both single version and list of versions
                    if isinstance(current_version, list) and current_version:
                        current_version = current_version[0]  # Take the first version if it's a list
                    
                    logger.info(f"🔍 Found {component_type}: {source}, current: {current_version}, latest: {latest_version}")
                    
                    if source and current_version and latest_version and current_version != latest_version:
                        report = self.check_module_compatibility(source, current_version, latest_version)
                        if report:
                            compatibility_reports.append({
                                "module_name": report.module_name,
                                "current_version": report.old_version,
                                "latest_version": report.new_version,
                                "compatibility_level": report.compatibility_level,
                                "upgrade_safe": report.upgrade_safe,
                                "summary": report.summary,
                                "issues_count": len(report.issues),
                                "breaking_changes": [
                                    {
                                        "category": issue.category,
                                        "message": issue.message,
                                        "old_value": issue.old_value,
                                        "new_value": issue.new_value,
                                        "recommendation": issue.recommendation
                                    }
                                    for issue in report.issues if issue.severity == "breaking"
                                ],
                                "warnings": [
                                    {
                                        "category": issue.category,
                                        "message": issue.message,
                                        "old_value": issue.old_value,
                                        "new_value": issue.new_value,
                                        "recommendation": issue.recommendation
                                    }
                                    for issue in report.issues if issue.severity == "warning"
                                ],
                                "recommendations": [issue.recommendation for issue in report.issues if issue.recommendation]
                            })
        
        # Add module compatibility section to inventory
        inventory["module_compatibility"] = {
            "total_modules_analyzed": len(compatibility_reports),
            "safe_upgrades": len([r for r in compatibility_reports if r["upgrade_safe"]]),
            "breaking_changes": len([r for r in compatibility_reports if not r["upgrade_safe"]]),
            "reports": compatibility_reports
        }
        
        logger.info(f"Module compatibility analysis completed. Analyzed {len(compatibility_reports)} modules")
        
        return inventory
