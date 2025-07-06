"""
Provider Schema Compatibility Service

This service compares provider schemas between versions to detect compatibility issues,
breaking changes, and potential conflicts with existing IaC configurations.
"""

import asyncio
import logging
import requests
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import json
import re

logger = logging.getLogger(__name__)


class CompatibilityLevel(Enum):
    """Compatibility levels for schema changes"""
    COMPATIBLE = "compatible"
    MINOR_ISSUES = "minor_issues"
    BREAKING_CHANGES = "breaking_changes"
    UNKNOWN = "unknown"


@dataclass
class SchemaChange:
    """Represents a change in provider schema"""
    type: str  # 'resource_removed', 'attribute_removed', 'attribute_added', etc.
    resource: str
    attribute: Optional[str] = None
    description: str = ""
    severity: str = "info"  # 'info', 'warning', 'error'
    impact: str = ""


@dataclass
class CompatibilityReport:
    """Compatibility report for a provider version comparison"""
    provider_name: str
    current_version: str
    latest_version: str
    compatibility_level: CompatibilityLevel
    breaking_changes: List[SchemaChange]
    deprecations: List[SchemaChange]
    new_features: List[SchemaChange]
    warnings: List[SchemaChange]
    summary: str
    recommendations: List[str]


class SchemaCompatibilityService:
    """Service for checking provider schema compatibility"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ThothCTL/0.4.0 Schema Compatibility Checker'
        })
        self.cache = {}
    
    async def check_provider_compatibility(
        self,
        provider_name: str,
        current_version: str,
        latest_version: str,
        used_resources: Optional[List[str]] = None
    ) -> CompatibilityReport:
        """
        Check compatibility between two provider versions
        
        Args:
            provider_name: Name of the provider (e.g., 'aws', 'google')
            current_version: Current version being used
            latest_version: Latest available version
            used_resources: List of resources actually used in IaC (optional)
            
        Returns:
            CompatibilityReport with detailed analysis
        """
        try:
            logger.info(f"Checking compatibility for {provider_name}: {current_version} -> {latest_version}")
            
            # Skip if versions are the same
            if current_version == latest_version:
                return self._create_same_version_report(provider_name, current_version)
            
            # Get schemas for both versions
            current_schema = await self._get_provider_schema(provider_name, current_version)
            latest_schema = await self._get_provider_schema(provider_name, latest_version)
            
            if not current_schema or not latest_schema:
                return self._create_unknown_report(provider_name, current_version, latest_version)
            
            # Analyze differences
            changes = self._analyze_schema_differences(
                current_schema, latest_schema, used_resources
            )
            
            # Create compatibility report
            return self._create_compatibility_report(
                provider_name, current_version, latest_version, changes
            )
            
        except Exception as e:
            logger.error(f"Error checking compatibility for {provider_name}: {str(e)}")
            return self._create_error_report(provider_name, current_version, latest_version, str(e))
    
    async def _get_provider_schema(self, provider_name: str, version: str) -> Optional[Dict]:
        """Get provider schema from Terraform Registry"""
        cache_key = f"{provider_name}:{version}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Try different registry formats
            urls = [
                f"https://registry.terraform.io/v1/providers/hashicorp/{provider_name}/{version}/docs",
                f"https://registry.terraform.io/v1/providers/{provider_name}/{provider_name}/{version}/docs",
                f"https://registry.opentofu.org/v1/providers/hashicorp/{provider_name}/{version}/docs"
            ]
            
            for url in urls:
                try:
                    response = self.session.get(url, timeout=30)
                    if response.status_code == 200:
                        schema = response.json()
                        self.cache[cache_key] = schema
                        logger.debug(f"Retrieved schema for {provider_name} {version}")
                        return schema
                except requests.RequestException:
                    continue
            
            logger.warning(f"Could not retrieve schema for {provider_name} {version}")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving schema for {provider_name} {version}: {str(e)}")
            return None
    
    def _analyze_schema_differences(
        self,
        current_schema: Dict,
        latest_schema: Dict,
        used_resources: Optional[List[str]] = None
    ) -> List[SchemaChange]:
        """Analyze differences between two schemas"""
        changes = []
        
        # Get resources from both schemas
        current_resources = {r.get('path', r.get('name', '')): r 
                           for r in current_schema.get('resources', [])}
        latest_resources = {r.get('path', r.get('name', '')): r 
                          for r in latest_schema.get('resources', [])}
        
        # Check for removed resources
        for resource_name in current_resources:
            if resource_name not in latest_resources:
                # Only flag as breaking if the resource is actually used
                if not used_resources or resource_name in used_resources:
                    changes.append(SchemaChange(
                        type="resource_removed",
                        resource=resource_name,
                        description=f"Resource '{resource_name}' has been removed",
                        severity="error",
                        impact="Breaking change - resource no longer available"
                    ))
        
        # Check for new resources
        for resource_name in latest_resources:
            if resource_name not in current_resources:
                changes.append(SchemaChange(
                    type="resource_added",
                    resource=resource_name,
                    description=f"New resource '{resource_name}' is available",
                    severity="info",
                    impact="New capability available"
                ))
        
        # Check for changes in existing resources
        for resource_name in current_resources:
            if resource_name in latest_resources:
                resource_changes = self._compare_resource_attributes(
                    resource_name,
                    current_resources[resource_name],
                    latest_resources[resource_name],
                    used_resources
                )
                changes.extend(resource_changes)
        
        return changes
    
    def _compare_resource_attributes(
        self,
        resource_name: str,
        current_resource: Dict,
        latest_resource: Dict,
        used_resources: Optional[List[str]] = None
    ) -> List[SchemaChange]:
        """Compare attributes of a specific resource"""
        changes = []
        
        # Get attributes from both versions
        current_attrs = current_resource.get('attributes', {})
        latest_attrs = latest_resource.get('attributes', {})
        
        # Check for removed attributes
        for attr_name, attr_info in current_attrs.items():
            if attr_name not in latest_attrs:
                severity = "error" if attr_info.get('required', False) else "warning"
                impact = "Breaking change" if attr_info.get('required', False) else "Deprecated attribute"
                
                changes.append(SchemaChange(
                    type="attribute_removed",
                    resource=resource_name,
                    attribute=attr_name,
                    description=f"Attribute '{attr_name}' removed from {resource_name}",
                    severity=severity,
                    impact=impact
                ))
        
        # Check for new attributes
        for attr_name, attr_info in latest_attrs.items():
            if attr_name not in current_attrs:
                changes.append(SchemaChange(
                    type="attribute_added",
                    resource=resource_name,
                    attribute=attr_name,
                    description=f"New attribute '{attr_name}' available in {resource_name}",
                    severity="info",
                    impact="New functionality available"
                ))
        
        # Check for attribute requirement changes
        for attr_name in current_attrs:
            if attr_name in latest_attrs:
                current_required = current_attrs[attr_name].get('required', False)
                latest_required = latest_attrs[attr_name].get('required', False)
                
                if not current_required and latest_required:
                    changes.append(SchemaChange(
                        type="attribute_now_required",
                        resource=resource_name,
                        attribute=attr_name,
                        description=f"Attribute '{attr_name}' is now required in {resource_name}",
                        severity="error",
                        impact="Breaking change - attribute must be specified"
                    ))
                elif current_required and not latest_required:
                    changes.append(SchemaChange(
                        type="attribute_now_optional",
                        resource=resource_name,
                        attribute=attr_name,
                        description=f"Attribute '{attr_name}' is now optional in {resource_name}",
                        severity="info",
                        impact="Backward compatible change"
                    ))
        
        return changes
    
    def _create_compatibility_report(
        self,
        provider_name: str,
        current_version: str,
        latest_version: str,
        changes: List[SchemaChange]
    ) -> CompatibilityReport:
        """Create a comprehensive compatibility report"""
        
        # Categorize changes
        breaking_changes = [c for c in changes if c.severity == "error"]
        warnings = [c for c in changes if c.severity == "warning"]
        new_features = [c for c in changes if c.type in ["resource_added", "attribute_added"]]
        deprecations = [c for c in changes if "deprecated" in c.description.lower()]
        
        # Determine compatibility level
        if breaking_changes:
            compatibility_level = CompatibilityLevel.BREAKING_CHANGES
        elif warnings:
            compatibility_level = CompatibilityLevel.MINOR_ISSUES
        else:
            compatibility_level = CompatibilityLevel.COMPATIBLE
        
        # Generate summary
        summary = self._generate_summary(
            provider_name, current_version, latest_version, 
            breaking_changes, warnings, new_features
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            compatibility_level, breaking_changes, warnings
        )
        
        return CompatibilityReport(
            provider_name=provider_name,
            current_version=current_version,
            latest_version=latest_version,
            compatibility_level=compatibility_level,
            breaking_changes=breaking_changes,
            deprecations=deprecations,
            new_features=new_features,
            warnings=warnings,
            summary=summary,
            recommendations=recommendations
        )
    
    def _generate_summary(
        self,
        provider_name: str,
        current_version: str,
        latest_version: str,
        breaking_changes: List[SchemaChange],
        warnings: List[SchemaChange],
        new_features: List[SchemaChange]
    ) -> str:
        """Generate a summary of the compatibility analysis"""
        
        if breaking_changes:
            return (f"⚠️ Breaking changes detected when upgrading {provider_name} "
                   f"from {current_version} to {latest_version}. "
                   f"{len(breaking_changes)} breaking changes, {len(warnings)} warnings, "
                   f"{len(new_features)} new features.")
        elif warnings:
            return (f"⚡ Minor issues detected when upgrading {provider_name} "
                   f"from {current_version} to {latest_version}. "
                   f"{len(warnings)} warnings, {len(new_features)} new features.")
        else:
            return (f"✅ {provider_name} upgrade from {current_version} to {latest_version} "
                   f"appears compatible. {len(new_features)} new features available.")
    
    def _generate_recommendations(
        self,
        compatibility_level: CompatibilityLevel,
        breaking_changes: List[SchemaChange],
        warnings: List[SchemaChange]
    ) -> List[str]:
        """Generate recommendations based on compatibility analysis"""
        recommendations = []
        
        if compatibility_level == CompatibilityLevel.BREAKING_CHANGES:
            recommendations.extend([
                "🔴 Review all breaking changes before upgrading",
                "🧪 Test the upgrade in a non-production environment first",
                "📝 Update your IaC configurations to address breaking changes",
                "📋 Plan for potential resource recreation or modification"
            ])
        elif compatibility_level == CompatibilityLevel.MINOR_ISSUES:
            recommendations.extend([
                "🟡 Review warnings and deprecated features",
                "🧪 Test the upgrade in a development environment",
                "📝 Consider updating deprecated resource usage"
            ])
        else:
            recommendations.extend([
                "✅ Upgrade appears safe to proceed",
                "🧪 Still recommended to test in development first",
                "🆕 Review new features that might benefit your infrastructure"
            ])
        
        return recommendations
    
    def _create_same_version_report(self, provider_name: str, version: str) -> CompatibilityReport:
        """Create report when versions are the same"""
        return CompatibilityReport(
            provider_name=provider_name,
            current_version=version,
            latest_version=version,
            compatibility_level=CompatibilityLevel.COMPATIBLE,
            breaking_changes=[],
            deprecations=[],
            new_features=[],
            warnings=[],
            summary=f"✅ {provider_name} {version} is already the latest version",
            recommendations=["No upgrade needed - you're using the latest version"]
        )
    
    def _create_unknown_report(
        self, provider_name: str, current_version: str, latest_version: str
    ) -> CompatibilityReport:
        """Create report when schema information is unavailable"""
        return CompatibilityReport(
            provider_name=provider_name,
            current_version=current_version,
            latest_version=latest_version,
            compatibility_level=CompatibilityLevel.UNKNOWN,
            breaking_changes=[],
            deprecations=[],
            new_features=[],
            warnings=[],
            summary=f"❓ Unable to retrieve schema information for {provider_name}",
            recommendations=[
                "Check provider documentation manually",
                "Test upgrade in development environment",
                "Monitor for provider-specific upgrade guides"
            ]
        )
    
    def _create_error_report(
        self, provider_name: str, current_version: str, latest_version: str, error: str
    ) -> CompatibilityReport:
        """Create report when an error occurs"""
        return CompatibilityReport(
            provider_name=provider_name,
            current_version=current_version,
            latest_version=latest_version,
            compatibility_level=CompatibilityLevel.UNKNOWN,
            breaking_changes=[],
            deprecations=[],
            new_features=[],
            warnings=[],
            summary=f"❌ Error analyzing {provider_name} compatibility: {error}",
            recommendations=[
                "Check network connectivity",
                "Verify provider name and versions",
                "Consult provider documentation manually"
            ]
        )
    
    def generate_compatibility_html_report(self, reports: List[CompatibilityReport]) -> str:
        """Generate HTML subreport for compatibility analysis"""
        
        if not reports:
            return "<p>No compatibility analysis performed.</p>"
        
        html_parts = []
        html_parts.append("""
        <div class="compatibility-report">
            <h3>🔍 Provider Schema Compatibility Analysis</h3>
            <p class="compatibility-intro">
                This analysis compares your current provider versions with the latest available schemas
                to identify potential compatibility issues, breaking changes, and new features.
            </p>
        """)
        
        for report in reports:
            html_parts.append(self._generate_provider_compatibility_html(report))
        
        html_parts.append("</div>")
        
        return "\n".join(html_parts)
    
    def _generate_provider_compatibility_html(self, report: CompatibilityReport) -> str:
        """Generate HTML for a single provider compatibility report"""
        
        # Determine status icon and class
        status_info = {
            CompatibilityLevel.COMPATIBLE: ("✅", "compatible", "Compatible"),
            CompatibilityLevel.MINOR_ISSUES: ("⚡", "minor-issues", "Minor Issues"),
            CompatibilityLevel.BREAKING_CHANGES: ("⚠️", "breaking-changes", "Breaking Changes"),
            CompatibilityLevel.UNKNOWN: ("❓", "unknown", "Unknown")
        }
        
        icon, css_class, status_text = status_info[report.compatibility_level]
        
        html = f"""
        <div class="provider-compatibility {css_class}">
            <div class="compatibility-header">
                <h4>{icon} {report.provider_name.upper()} Provider Compatibility</h4>
                <div class="version-info">
                    <span class="current-version">Current: {report.current_version}</span>
                    <span class="arrow">→</span>
                    <span class="latest-version">Latest: {report.latest_version}</span>
                    <span class="status-badge status-{css_class}">{status_text}</span>
                </div>
            </div>
            
            <div class="compatibility-summary">
                <p>{report.summary}</p>
            </div>
        """
        
        # Add breaking changes section
        if report.breaking_changes:
            html += """
            <div class="breaking-changes-section">
                <h5>🔴 Breaking Changes</h5>
                <ul class="changes-list breaking">
            """
            for change in report.breaking_changes:
                html += f"""
                <li class="change-item">
                    <strong>{change.resource}</strong>
                    {f" - {change.attribute}" if change.attribute else ""}
                    <br><span class="change-description">{change.description}</span>
                    <br><span class="change-impact">{change.impact}</span>
                </li>
                """
            html += "</ul></div>"
        
        # Add warnings section
        if report.warnings:
            html += """
            <div class="warnings-section">
                <h5>🟡 Warnings</h5>
                <ul class="changes-list warnings">
            """
            for change in report.warnings:
                html += f"""
                <li class="change-item">
                    <strong>{change.resource}</strong>
                    {f" - {change.attribute}" if change.attribute else ""}
                    <br><span class="change-description">{change.description}</span>
                </li>
                """
            html += "</ul></div>"
        
        # Add new features section
        if report.new_features:
            html += """
            <div class="new-features-section">
                <h5>🆕 New Features</h5>
                <ul class="changes-list new-features">
            """
            for change in report.new_features[:5]:  # Limit to first 5
                html += f"""
                <li class="change-item">
                    <strong>{change.resource}</strong>
                    {f" - {change.attribute}" if change.attribute else ""}
                    <br><span class="change-description">{change.description}</span>
                </li>
                """
            if len(report.new_features) > 5:
                html += f"<li class='more-items'>... and {len(report.new_features) - 5} more new features</li>"
            html += "</ul></div>"
        
        # Add recommendations
        if report.recommendations:
            html += """
            <div class="recommendations-section">
                <h5>💡 Recommendations</h5>
                <ul class="recommendations-list">
            """
            for recommendation in report.recommendations:
                html += f"<li>{recommendation}</li>"
            html += "</ul></div>"
        
        html += "</div>"
        return html
