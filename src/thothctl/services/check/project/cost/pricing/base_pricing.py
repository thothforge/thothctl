"""Abstract base class for pricing providers."""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
from ..models.cost_models import ResourceCost


class BasePricingProvider(ABC):
    """Abstract base class for pricing providers"""
    
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
