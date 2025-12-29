"""Blast radius assessment service following ITIL v4 best practices."""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChangeRisk(Enum):
    """ITIL v4 Change Risk Categories."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeType(Enum):
    """ITIL v4 Change Types."""
    STANDARD = "standard"
    NORMAL = "normal"
    EMERGENCY = "emergency"


@dataclass
class BlastRadiusComponent:
    """Component affected by changes."""
    name: str
    path: str
    change_type: str  # create, update, delete, replace
    risk_score: float
    dependencies: List[str]
    dependents: List[str]
    criticality: str


@dataclass
class BlastRadiusAssessment:
    """Complete blast radius assessment."""
    total_components: int
    affected_components: List[BlastRadiusComponent]
    risk_level: ChangeRisk
    change_type: ChangeType
    recommendations: List[str]
    mitigation_steps: List[str]
    rollback_plan: List[str]


class BlastRadiusService:
    """Service for assessing blast radius of infrastructure changes."""
    
    def __init__(self):
        """Initialize blast radius service."""
        self.risk_thresholds = {
            ChangeRisk.LOW: 0.3,
            ChangeRisk.MEDIUM: 0.6,
            ChangeRisk.HIGH: 0.8,
            ChangeRisk.CRITICAL: 1.0
        }
    
    def assess_blast_radius(self, 
                           directory: str, 
                           recursive: bool = False,
                           plan_file: str = None) -> BlastRadiusAssessment:
        """
        Assess blast radius combining dependency analysis with plan changes.
        
        Args:
            directory: Root directory to analyze
            recursive: Whether to analyze recursively
            plan_file: Path to terraform plan file (optional)
            
        Returns:
            BlastRadiusAssessment with complete analysis
        """
        logger.info("Starting blast radius assessment")
        
        # Step 1: Get dependency graph
        dependencies = self._get_dependency_graph(directory, recursive)
        
        # Step 2: Get planned changes
        planned_changes = self._get_planned_changes(directory, plan_file)
        
        # Step 3: Calculate blast radius
        affected_components = self._calculate_blast_radius(dependencies, planned_changes)
        
        # Step 4: Assess overall risk
        risk_level = self._assess_overall_risk(affected_components)
        
        # Step 5: Determine change type
        change_type = self._determine_change_type(risk_level, affected_components)
        
        # Step 6: Generate recommendations
        recommendations = self._generate_recommendations(risk_level, affected_components)
        
        # Step 7: Create mitigation steps
        mitigation_steps = self._create_mitigation_steps(risk_level, affected_components)
        
        # Step 8: Create rollback plan
        rollback_plan = self._create_rollback_plan(affected_components)
        
        return BlastRadiusAssessment(
            total_components=len(dependencies.get('nodes', [])),
            affected_components=affected_components,
            risk_level=risk_level,
            change_type=change_type,
            recommendations=recommendations,
            mitigation_steps=mitigation_steps,
            rollback_plan=rollback_plan
        )
    
    def _get_dependency_graph(self, directory: str, recursive: bool) -> Dict[str, Any]:
        """Get dependency graph from existing deps check."""
        try:
            from ...check.project.risk_assessment import RiskAssessmentService
            
            # Use existing dependency analysis
            risk_service = RiskAssessmentService()
            
            # Get nodes and edges (simplified - you'll need to adapt to your existing implementation)
            nodes, edges = self._extract_dependencies(directory, recursive)
            
            return {
                'nodes': nodes,
                'edges': edges,
                'risks': risk_service.calculate_risk_for_components(nodes, edges, directory)
            }
        except Exception as e:
            logger.error(f"Failed to get dependency graph: {e}")
            return {'nodes': [], 'edges': [], 'risks': {}}
    
    def _get_planned_changes(self, directory: str, plan_file: str = None) -> Dict[str, Any]:
        """Get planned changes from terraform plan."""
        try:
            if plan_file and os.path.exists(plan_file):
                # Use provided plan file
                with open(plan_file, 'r') as f:
                    plan_data = json.load(f)
            else:
                # Generate plan
                plan_data = self._generate_terraform_plan(directory, plan_file)
            
            return self._parse_plan_changes(plan_data)
        except Exception as e:
            logger.error(f"Failed to get planned changes: {e}")
            return {'changes': []}
    
    def _calculate_blast_radius(self, dependencies: Dict[str, Any], changes: Dict[str, Any]) -> List[BlastRadiusComponent]:
        """Calculate which components are affected by changes."""
        affected = []
        changed_components = set()
        
        # Get directly changed components
        for change in changes.get('changes', []):
            changed_components.add(change.get('address', ''))
        
        # Calculate blast radius using dependency graph
        blast_radius_components = self._propagate_changes(
            changed_components, 
            dependencies.get('edges', [])
        )
        
        # Create BlastRadiusComponent objects
        for component in blast_radius_components:
            risk_score = dependencies.get('risks', {}).get(component, 0.0)
            deps, dependents = self._get_component_relationships(component, dependencies.get('edges', []))
            
            affected.append(BlastRadiusComponent(
                name=component,
                path=self._get_component_path(component),
                change_type=self._get_change_type_for_component(component, changes),
                risk_score=risk_score,
                dependencies=deps,
                dependents=dependents,
                criticality=self._assess_component_criticality(component, risk_score)
            ))
        
        return affected
    
    def _assess_overall_risk(self, components: List[BlastRadiusComponent]) -> ChangeRisk:
        """Assess overall risk level based on affected components."""
        if not components:
            return ChangeRisk.LOW
        
        # Calculate weighted risk score
        total_risk = sum(comp.risk_score for comp in components)
        avg_risk = total_risk / len(components)
        
        # Check for critical components
        critical_count = sum(1 for comp in components if comp.criticality == "critical")
        high_risk_count = sum(1 for comp in components if comp.risk_score > 0.8)
        
        if critical_count > 0 or avg_risk > self.risk_thresholds[ChangeRisk.CRITICAL]:
            return ChangeRisk.CRITICAL
        elif high_risk_count > 2 or avg_risk > self.risk_thresholds[ChangeRisk.HIGH]:
            return ChangeRisk.HIGH
        elif avg_risk > self.risk_thresholds[ChangeRisk.MEDIUM]:
            return ChangeRisk.MEDIUM
        else:
            return ChangeRisk.LOW
    
    def _determine_change_type(self, risk_level: ChangeRisk, components: List[BlastRadiusComponent]) -> ChangeType:
        """Determine ITIL v4 change type based on risk assessment."""
        # Check for emergency indicators
        emergency_indicators = [
            any(comp.change_type == "delete" for comp in components),
            risk_level == ChangeRisk.CRITICAL,
            len(components) > 10
        ]
        
        if any(emergency_indicators):
            return ChangeType.EMERGENCY
        elif risk_level in [ChangeRisk.MEDIUM, ChangeRisk.HIGH]:
            return ChangeType.NORMAL
        else:
            return ChangeType.STANDARD
    
    def _generate_recommendations(self, risk_level: ChangeRisk, components: List[BlastRadiusComponent]) -> List[str]:
        """Generate ITIL v4 compliant recommendations."""
        recommendations = []
        
        if risk_level == ChangeRisk.CRITICAL:
            recommendations.extend([
                "🚨 CRITICAL: Require Change Advisory Board (CAB) approval",
                "🚨 Schedule maintenance window during low-traffic period",
                "🚨 Implement comprehensive rollback plan",
                "🚨 Conduct thorough testing in staging environment"
            ])
        elif risk_level == ChangeRisk.HIGH:
            recommendations.extend([
                "⚠️ HIGH: Require senior management approval",
                "⚠️ Schedule during maintenance window",
                "⚠️ Prepare detailed rollback procedures",
                "⚠️ Monitor affected systems closely"
            ])
        elif risk_level == ChangeRisk.MEDIUM:
            recommendations.extend([
                "📋 MEDIUM: Require team lead approval",
                "📋 Test in staging environment first",
                "📋 Have rollback plan ready",
                "📋 Monitor key metrics during deployment"
            ])
        else:
            recommendations.extend([
                "✅ LOW: Standard change process applies",
                "✅ Can be deployed during business hours",
                "✅ Basic monitoring sufficient"
            ])
        
        # Add component-specific recommendations
        if any(comp.change_type == "replace" for comp in components):
            recommendations.append("🔄 Resource replacement detected - ensure data backup")
        
        if len(components) > 5:
            recommendations.append("📊 Large blast radius - consider phased deployment")
        
        return recommendations
    
    def _create_mitigation_steps(self, risk_level: ChangeRisk, components: List[BlastRadiusComponent]) -> List[str]:
        """Create risk mitigation steps."""
        steps = []
        
        # Common mitigation steps
        steps.extend([
            "1. Create infrastructure backup/snapshot",
            "2. Verify all dependencies are healthy",
            "3. Ensure monitoring and alerting is active"
        ])
        
        if risk_level in [ChangeRisk.HIGH, ChangeRisk.CRITICAL]:
            steps.extend([
                "4. Set up real-time monitoring dashboard",
                "5. Have incident response team on standby",
                "6. Prepare communication plan for stakeholders"
            ])
        
        # Component-specific steps
        critical_components = [c for c in components if c.criticality == "critical"]
        if critical_components:
            steps.append(f"7. Extra validation for critical components: {', '.join(c.name for c in critical_components)}")
        
        return steps
    
    def _create_rollback_plan(self, components: List[BlastRadiusComponent]) -> List[str]:
        """Create rollback plan."""
        plan = [
            "1. Stop the deployment immediately if issues detected",
            "2. Revert to previous terraform state",
            "3. Restore from infrastructure backup if needed",
            "4. Verify all affected services are operational",
            "5. Notify stakeholders of rollback completion"
        ]
        
        # Add component-specific rollback steps
        if any(comp.change_type == "delete" for comp in components):
            plan.insert(2, "2a. Restore deleted resources from backup")
        
        return plan
    
    # Helper methods (simplified implementations)
    def _extract_dependencies(self, directory: str, recursive: bool) -> Tuple[List[str], List[Tuple[str, str]]]:
        """Extract dependencies - adapt to your existing implementation."""
        # This should integrate with your existing deps check logic
        return [], []
    
    def _generate_terraform_plan(self, directory: str, plan_file: str = None) -> Dict[str, Any]:
        """Load existing terraform plan from file."""
        if plan_file and os.path.exists(plan_file):
            try:
                with open(plan_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load plan file {plan_file}: {e}")
                return {}
        
        # If no plan file provided, return empty dict
        logger.warning("No plan file provided or file doesn't exist")
        return {}
    
    def _parse_plan_changes(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse terraform plan changes."""
        changes = []
        
        if 'resource_changes' in plan_data:
            for change in plan_data['resource_changes']:
                changes.append({
                    'address': change.get('address', ''),
                    'change': change.get('change', {}),
                    'type': change.get('type', '')
                })
        
        return {'changes': changes}
    
    def _propagate_changes(self, changed_components: Set[str], edges: List[Tuple[str, str]]) -> Set[str]:
        """Propagate changes through dependency graph."""
        affected = set(changed_components)
        
        # Simple propagation - can be enhanced with more sophisticated algorithms
        for source, target in edges:
            if source in changed_components:
                affected.add(target)
        
        return affected
    
    def _get_component_relationships(self, component: str, edges: List[Tuple[str, str]]) -> Tuple[List[str], List[str]]:
        """Get dependencies and dependents for a component."""
        dependencies = [source for source, target in edges if target == component]
        dependents = [target for source, target in edges if source == component]
        return dependencies, dependents
    
    def _get_component_path(self, component: str) -> str:
        """Get file path for component."""
        return f"./{component}"  # Simplified
    
    def _get_change_type_for_component(self, component: str, changes: Dict[str, Any]) -> str:
        """Get change type for specific component."""
        for change in changes.get('changes', []):
            if component in change.get('address', ''):
                actions = change.get('change', {}).get('actions', [])
                if 'delete' in actions:
                    return 'delete'
                elif 'create' in actions:
                    return 'create'
                elif 'update' in actions:
                    return 'update'
                elif 'replace' in actions:
                    return 'replace'
        return 'no-change'
    
    def _assess_component_criticality(self, component: str, risk_score: float) -> str:
        """Assess component criticality."""
        if risk_score > 0.8:
            return "critical"
        elif risk_score > 0.6:
            return "high"
        elif risk_score > 0.3:
            return "medium"
        else:
            return "low"
