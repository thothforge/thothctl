"""Abstract base class for pricing providers."""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
from ..models.cost_models import ResourceCost, CostAction


class BasePricingProvider(ABC):
    """Abstract base class for pricing providers"""

    @staticmethod
    def _safe_action(actions: List[str]) -> CostAction:
        """Safely convert terraform action to CostAction enum.
        
        Handles all valid terraform actions including 'no-op' and 'read'
        which are valid in planned_values but not in the original enum.
        """
        if not actions:
            return CostAction.NO_CHANGE
        action = actions[0]
        try:
            return CostAction(action)
        except ValueError:
            # Map common terraform actions that aren't in the enum
            mapping = {
                "no-op": CostAction.NO_OP,
                "read": CostAction.READ,
                "no-change": CostAction.NO_CHANGE,
            }
            return mapping.get(action, CostAction.NO_CHANGE)
    
    @abstractmethod
    def get_service_code(self) -> str:
        """Return AWS service code"""
        pass
    
    @abstractmethod
    def get_supported_resources(self) -> List[str]:
        """Return list of supported terraform resource types"""
        pass
    
    @abstractmethod
    def calculate_cost(self, resource_change: Dict[str, Any], 
                      region: str) -> Optional[ResourceCost]:
        """Calculate cost for a resource change"""
        pass
    
    @abstractmethod
    def get_offline_estimate(self, resource_change: Dict[str, Any], 
                           region: str) -> Optional[ResourceCost]:
        """Provide offline cost estimate when API unavailable"""
        pass
