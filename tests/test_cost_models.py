"""Unit tests for cost analysis models."""

import pytest
from thothctl.services.check.project.cost.models.cost_models import (
    CostAction, ResourceCost, CostAnalysis
)


class TestCostModels:
    """Test cost analysis data models"""
    
    def test_cost_action_enum(self):
        """Test CostAction enum values"""
        assert CostAction.CREATE.value == "create"
        assert CostAction.UPDATE.value == "update"
        assert CostAction.DELETE.value == "delete"
        assert CostAction.NO_CHANGE.value == "no-change"
    
    def test_resource_cost_creation(self):
        """Test ResourceCost object creation"""
        cost = ResourceCost(
            resource_address="aws_instance.test",
            resource_type="aws_instance",
            service_name="EC2",
            region="us-east-1",
            action=CostAction.CREATE,
            hourly_cost=0.10,
            monthly_cost=72.0,
            annual_cost=864.0,
            pricing_details={"instance_type": "t3.micro"},
            confidence_level="high"
        )
        
        assert cost.resource_address == "aws_instance.test"
        assert cost.service_name == "EC2"
        assert cost.action == CostAction.CREATE
        assert cost.monthly_cost == 72.0
        assert cost.confidence_level == "high"
    
    def test_cost_analysis_creation(self):
        """Test CostAnalysis object creation"""
        resource_costs = [
            ResourceCost(
                resource_address="aws_instance.test",
                resource_type="aws_instance",
                service_name="EC2",
                region="us-east-1",
                action=CostAction.CREATE,
                hourly_cost=0.10,
                monthly_cost=72.0,
                annual_cost=864.0,
                pricing_details={"instance_type": "t3.micro"},
                confidence_level="high"
            )
        ]
        
        analysis = CostAnalysis(
            total_monthly_cost=72.0,
            total_annual_cost=864.0,
            resource_costs=resource_costs,
            cost_breakdown_by_service={"EC2": 72.0},
            cost_breakdown_by_action={"create": 72.0},
            recommendations=["Consider Reserved Instances"],
            warnings=[],
            analysis_metadata={"region": "us-east-1"}
        )
        
        assert analysis.total_monthly_cost == 72.0
        assert len(analysis.resource_costs) == 1
        assert analysis.cost_breakdown_by_service["EC2"] == 72.0
