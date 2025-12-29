"""Unit tests for cost analyzer service."""

import pytest
import json
import tempfile
from unittest.mock import Mock, patch
from thothctl.services.check.project.cost.cost_analyzer import CostAnalyzer
from thothctl.services.check.project.cost.models.cost_models import CostAction


class TestCostAnalyzer:
    """Test cost analyzer service"""
    
    @pytest.fixture
    def sample_terraform_plan(self):
        """Sample terraform plan data"""
        return {
            "resource_changes": [
                {
                    "address": "aws_instance.web",
                    "type": "aws_instance",
                    "change": {
                        "actions": ["create"],
                        "after": {
                            "instance_type": "t3.micro",
                            "availability_zone": "us-east-1a"
                        }
                    }
                },
                {
                    "address": "aws_db_instance.main",
                    "type": "aws_db_instance",
                    "change": {
                        "actions": ["create"],
                        "after": {
                            "instance_class": "db.t3.micro"
                        }
                    }
                },
                {
                    "address": "aws_s3_bucket.assets",
                    "type": "aws_s3_bucket",
                    "change": {
                        "actions": ["no-op"],
                        "after": {}
                    }
                }
            ]
        }
    
    @pytest.fixture
    def cost_analyzer(self):
        """Cost analyzer instance"""
        with patch('thothctl.services.check.project.cost.cost_analyzer.AWSPricingClient'):
            return CostAnalyzer(region='us-east-1')
    
    def test_initialization(self, cost_analyzer):
        """Test cost analyzer initialization"""
        assert cost_analyzer.region == 'us-east-1'
        assert 'aws_instance' in cost_analyzer._providers
        assert 'aws_db_instance' in cost_analyzer._providers
    
    def test_analyze_terraform_plan(self, cost_analyzer, sample_terraform_plan):
        """Test terraform plan analysis"""
        # Create temporary plan file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_terraform_plan, f)
            plan_file = f.name
        
        try:
            analysis = cost_analyzer.analyze_terraform_plan(plan_file)
            
            assert analysis is not None
            assert analysis.total_monthly_cost > 0
            assert len(analysis.resource_costs) == 2  # Only create actions
            assert 'EC2' in analysis.cost_breakdown_by_service
            assert 'RDS' in analysis.cost_breakdown_by_service
            assert 'create' in analysis.cost_breakdown_by_action
            assert len(analysis.recommendations) > 0
        finally:
            import os
            os.unlink(plan_file)
    
    def test_extract_region(self, cost_analyzer):
        """Test region extraction from resource"""
        resource_change = {
            'change': {
                'after': {
                    'availability_zone': 'us-west-2a'
                }
            }
        }
        
        region = cost_analyzer._extract_region(resource_change)
        assert region == 'us-west-2'
    
    def test_breakdown_by_service(self, cost_analyzer):
        """Test cost breakdown by service"""
        from thothctl.services.check.project.cost.models.cost_models import ResourceCost
        
        costs = [
            ResourceCost(
                resource_address="aws_instance.test",
                resource_type="aws_instance",
                service_name="EC2",
                region="us-east-1",
                action=CostAction.CREATE,
                hourly_cost=0.10,
                monthly_cost=72.0,
                annual_cost=864.0,
                pricing_details={},
                confidence_level="high"
            ),
            ResourceCost(
                resource_address="aws_db_instance.test",
                resource_type="aws_db_instance",
                service_name="RDS",
                region="us-east-1",
                action=CostAction.CREATE,
                hourly_cost=0.05,
                monthly_cost=36.0,
                annual_cost=432.0,
                pricing_details={},
                confidence_level="medium"
            )
        ]
        
        breakdown = cost_analyzer._breakdown_by_service(costs)
        
        assert breakdown['EC2'] == 72.0
        assert breakdown['RDS'] == 36.0
    
    def test_generate_recommendations(self, cost_analyzer):
        """Test recommendation generation"""
        recommendations = cost_analyzer._generate_recommendations(1500.0, [])
        
        assert len(recommendations) > 0
        assert any("Reserved Instances" in rec for rec in recommendations)
        assert any("Cost Explorer" in rec for rec in recommendations)
