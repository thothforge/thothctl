"""Data models for cost analysis."""

from dataclasses import dataclass
from typing import List, Dict, Any
from enum import Enum


class CostAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    NO_CHANGE = "no-change"


@dataclass
class ResourceCost:
    resource_address: str
    resource_type: str
    service_name: str
    region: str
    action: CostAction
    hourly_cost: float
    monthly_cost: float
    annual_cost: float
    pricing_details: Dict[str, Any]
    confidence_level: str  # high, medium, low


@dataclass
class CostAnalysis:
    total_monthly_cost: float
    total_annual_cost: float
    resource_costs: List[ResourceCost]
    cost_breakdown_by_service: Dict[str, float]
    cost_breakdown_by_action: Dict[str, float]
    recommendations: List[str]
    warnings: List[str]
    analysis_metadata: Dict[str, Any]
