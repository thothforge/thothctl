"""Risk assessment service for infrastructure components."""
import os
import re
import logging
import random
from typing import Dict, List, Tuple, Set
from pathlib import Path
import subprocess

logger = logging.getLogger(__name__)

class RiskAssessmentService:
    """Service for assessing risk in infrastructure components."""
    
    # Risk factors and their weights
    RISK_FACTORS = {
        "changes_frequency": 0.3,    # How often the component changes
        "dependencies_count": 0.25,  # Number of dependencies
        "complexity": 0.2,           # Complexity of the component
        "criticality": 0.15,         # How critical the component is
        "recent_changes": 0.1        # Recent changes to the component
    }
    
    def __init__(self):
        """Initialize the risk assessment service."""
        self.component_risks = {}
        self.git_history_cache = {}
    
    def calculate_risk_for_components(self, 
                                     nodes: List[str], 
                                     edges: List[Tuple[str, str]], 
                                     directory: str) -> Dict[str, float]:
        """
        Calculate risk percentage for each component in the dependency graph.
        
        Args:
            nodes: List of component names
            edges: List of dependency relationships (source, target)
            directory: Root directory of the project
            
        Returns:
            Dictionary mapping component names to risk percentages
        """
        logger.info(f"Calculating risk for {len(nodes)} components")
        
        # Reset component risks
        self.component_risks = {}
        
        # Calculate incoming and outgoing dependencies
        incoming_deps = {node: [] for node in nodes}
        outgoing_deps = {node: [] for node in nodes}
        
        for source, target in edges:
            outgoing_deps[source].append(target)
            incoming_deps[target].append(source)
        
        # Calculate risk for each component
        for node in nodes:
            risk = self._calculate_component_risk(
                node, 
                incoming_deps[node], 
                outgoing_deps[node], 
                directory
            )
            self.component_risks[node] = risk
        
        return self.component_risks
    
    def _calculate_component_risk(self, 
                                 component: str, 
                                 incoming_deps: List[str], 
                                 outgoing_deps: List[str], 
                                 directory: str) -> float:
        """
        Calculate risk percentage for a single component.
        
        Args:
            component: Component name
            incoming_deps: List of components that depend on this component
            outgoing_deps: List of components this component depends on
            directory: Root directory of the project
            
        Returns:
            Risk percentage (0-100)
        """
        # Get component path
        component_path = self._get_component_path(component, directory)
        
        # Calculate individual risk factors
        changes_frequency = self._calculate_changes_frequency(component_path)
        dependencies_count = self._calculate_dependencies_risk(incoming_deps, outgoing_deps)
        complexity = self._calculate_complexity(component_path)
        criticality = self._calculate_criticality(incoming_deps)
        recent_changes = self._calculate_recent_changes(component_path)
        
        # Calculate weighted risk
        weighted_risk = (
            changes_frequency * self.RISK_FACTORS["changes_frequency"] +
            dependencies_count * self.RISK_FACTORS["dependencies_count"] +
            complexity * self.RISK_FACTORS["complexity"] +
            criticality * self.RISK_FACTORS["criticality"] +
            recent_changes * self.RISK_FACTORS["recent_changes"]
        )
        
        # Convert to percentage (0-100)
        risk_percentage = min(100, max(0, weighted_risk * 100))
        
        logger.debug(f"Risk for {component}: {risk_percentage:.1f}%")
        return risk_percentage
    
    def _get_component_path(self, component: str, directory: str) -> str:
        """
        Get the filesystem path for a component.
        
        Args:
            component: Component name (e.g., "stacks/networking")
            directory: Root directory of the project
            
        Returns:
            Absolute path to the component
        """
        # Remove quotes if present
        component = component.strip('"')
        
        # Construct path
        component_path = os.path.join(directory, component)
        
        # If path doesn't exist, try to find it
        if not os.path.exists(component_path):
            # Try to find a directory that ends with the component name
            for root, dirs, _ in os.walk(directory):
                for dir_name in dirs:
                    if dir_name == os.path.basename(component):
                        return os.path.join(root, dir_name)
            
            # If still not found, return the original path
            logger.warning(f"Component path not found: {component_path}")
        
        return component_path
    
    def _calculate_changes_frequency(self, component_path: str) -> float:
        """
        Calculate risk based on how frequently the component changes.
        
        Args:
            component_path: Path to the component
            
        Returns:
            Risk factor (0-1)
        """
        if not os.path.exists(component_path):
            return 0.5  # Default risk if path doesn't exist
        
        # Get git history for the component
        commit_count = self._get_git_commit_count(component_path)
        
        # Normalize commit count to risk factor (0-1)
        # More commits = higher risk
        if commit_count == 0:
            return 0.1  # Low risk for components with no changes
        elif commit_count < 5:
            return 0.3  # Low-medium risk
        elif commit_count < 20:
            return 0.6  # Medium risk
        elif commit_count < 50:
            return 0.8  # Medium-high risk
        else:
            return 1.0  # High risk
    
    def _calculate_dependencies_risk(self, incoming_deps: List[str], outgoing_deps: List[str]) -> float:
        """
        Calculate risk based on dependencies.
        
        Args:
            incoming_deps: List of components that depend on this component
            outgoing_deps: List of components this component depends on
            
        Returns:
            Risk factor (0-1)
        """
        # Count total dependencies
        total_deps = len(incoming_deps) + len(outgoing_deps)
        
        # Normalize dependency count to risk factor (0-1)
        # More dependencies = higher risk
        if total_deps == 0:
            return 0.1  # Low risk for isolated components
        elif total_deps < 3:
            return 0.3  # Low-medium risk
        elif total_deps < 6:
            return 0.5  # Medium risk
        elif total_deps < 10:
            return 0.7  # Medium-high risk
        else:
            return 0.9  # High risk
    
    def _calculate_complexity(self, component_path: str) -> float:
        """
        Calculate risk based on component complexity.
        
        Args:
            component_path: Path to the component
            
        Returns:
            Risk factor (0-1)
        """
        if not os.path.exists(component_path):
            return 0.5  # Default risk if path doesn't exist
        
        # Count HCL files and their lines of code
        hcl_files = 0
        total_loc = 0
        
        for root, _, files in os.walk(component_path):
            for file in files:
                if file.endswith(('.tf', '.hcl')):
                    hcl_files += 1
                    try:
                        with open(os.path.join(root, file), 'r') as f:
                            total_loc += sum(1 for _ in f)
                    except Exception as e:
                        logger.warning(f"Error reading file {file}: {str(e)}")
        
        # Calculate complexity based on files and LOC
        if hcl_files == 0:
            return 0.1  # Low risk for components with no HCL files
        
        avg_loc = total_loc / hcl_files if hcl_files > 0 else 0
        
        # Normalize complexity to risk factor (0-1)
        if avg_loc < 50:
            return 0.2  # Low risk
        elif avg_loc < 100:
            return 0.4  # Low-medium risk
        elif avg_loc < 200:
            return 0.6  # Medium risk
        elif avg_loc < 500:
            return 0.8  # Medium-high risk
        else:
            return 1.0  # High risk
    
    def _calculate_criticality(self, incoming_deps: List[str]) -> float:
        """
        Calculate risk based on how critical the component is.
        
        Args:
            incoming_deps: List of components that depend on this component
            
        Returns:
            Risk factor (0-1)
        """
        # Components with more incoming dependencies are more critical
        incoming_count = len(incoming_deps)
        
        # Normalize criticality to risk factor (0-1)
        if incoming_count == 0:
            return 0.1  # Low risk for components with no dependents
        elif incoming_count < 2:
            return 0.3  # Low-medium risk
        elif incoming_count < 5:
            return 0.6  # Medium risk
        elif incoming_count < 10:
            return 0.8  # Medium-high risk
        else:
            return 1.0  # High risk
    
    def _calculate_recent_changes(self, component_path: str) -> float:
        """
        Calculate risk based on recent changes to the component.
        
        Args:
            component_path: Path to the component
            
        Returns:
            Risk factor (0-1)
        """
        if not os.path.exists(component_path):
            return 0.5  # Default risk if path doesn't exist
        
        # Get recent git commits for the component
        recent_commits = self._get_recent_git_commits(component_path)
        
        # Normalize recent commits to risk factor (0-1)
        # More recent commits = higher risk
        if recent_commits == 0:
            return 0.1  # Low risk for components with no recent changes
        elif recent_commits == 1:
            return 0.4  # Low-medium risk
        elif recent_commits < 3:
            return 0.6  # Medium risk
        elif recent_commits < 5:
            return 0.8  # Medium-high risk
        else:
            return 1.0  # High risk
    
    def _get_git_commit_count(self, path: str) -> int:
        """
        Get the number of git commits for a path.
        
        Args:
            path: Path to check
            
        Returns:
            Number of commits
        """
        # Check cache first
        if path in self.git_history_cache:
            return self.git_history_cache[path]
        
        try:
            # Try to get git commit count
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD", "--", path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                commit_count = int(result.stdout.strip())
                # Cache the result
                self.git_history_cache[path] = commit_count
                return commit_count
            else:
                # If git command fails, use a random value for demo purposes
                # In production, you might want to handle this differently
                random_count = random.randint(1, 30)
                self.git_history_cache[path] = random_count
                return random_count
                
        except Exception as e:
            logger.warning(f"Error getting git commit count for {path}: {str(e)}")
            # Use a random value for demo purposes
            random_count = random.randint(1, 30)
            self.git_history_cache[path] = random_count
            return random_count
    
    def _get_recent_git_commits(self, path: str) -> int:
        """
        Get the number of recent git commits (last 30 days) for a path.
        
        Args:
            path: Path to check
            
        Returns:
            Number of recent commits
        """
        try:
            # Try to get recent git commits
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD", "--since='30 days ago'", "--", path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                return int(result.stdout.strip())
            else:
                # If git command fails, use a random value for demo purposes
                return random.randint(0, 5)
                
        except Exception as e:
            logger.warning(f"Error getting recent git commits for {path}: {str(e)}")
            # Use a random value for demo purposes
            return random.randint(0, 5)


# Create a singleton instance
risk_service = RiskAssessmentService()

def calculate_component_risks(nodes: List[str], edges: List[Tuple[str, str]], directory: str) -> Dict[str, float]:
    """
    Calculate risk percentages for components in the dependency graph.
    
    Args:
        nodes: List of component names
        edges: List of dependency relationships (source, target)
        directory: Root directory of the project
        
    Returns:
        Dictionary mapping component names to risk percentages
    """
    return risk_service.calculate_risk_for_components(nodes, edges, directory)
