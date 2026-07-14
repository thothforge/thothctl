"""Unit tests for CloudFormation/CDK drift detection service."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from thothctl.services.check.project.drift.cfn_drift_service import (
    CfnDriftDetectionService,
    _matches_tags,
)
from thothctl.services.check.project.drift.models import (
    DriftSeverity,
    DriftType,
    DriftSummary,
)


class TestCfnDriftDetectionService:
    """Test CloudFormation drift detection."""

    @pytest.fixture
    def service(self):
        return CfnDriftDetectionService(region="us-east-1")

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.exceptions = MagicMock()
        client.exceptions.ClientError = Exception
        return client

    # -- Severity classification --

    def test_critical_severity_for_rds(self, service):
        severity = service._assess_cfn_severity("AWS::RDS::DBInstance", DriftType.DELETED)
        assert severity == DriftSeverity.CRITICAL

    def test_high_severity_for_rds_changed(self, service):
        severity = service._assess_cfn_severity("AWS::RDS::DBInstance", DriftType.CHANGED)
        assert severity == DriftSeverity.HIGH

    def test_high_severity_for_eks_deleted(self, service):
        severity = service._assess_cfn_severity("AWS::EKS::Cluster", DriftType.DELETED)
        assert severity == DriftSeverity.HIGH

    def test_medium_severity_for_lambda_changed(self, service):
        severity = service._assess_cfn_severity("AWS::Lambda::Function", DriftType.CHANGED)
        assert severity == DriftSeverity.MEDIUM

    def test_low_severity_for_unknown_type(self, service):
        severity = service._assess_cfn_severity("AWS::CloudWatch::Alarm", DriftType.CHANGED)
        assert severity == DriftSeverity.LOW

    # -- Drift type classification --

    def test_modified_maps_to_changed(self, service):
        assert service._cfn_status_to_drift_type("MODIFIED") == DriftType.CHANGED

    def test_deleted_maps_to_deleted(self, service):
        assert service._cfn_status_to_drift_type("DELETED") == DriftType.DELETED

    # -- Property diff extraction --

    def test_extract_property_diffs(self, service):
        drift_detail = {
            "PropertyDifferences": [
                {"PropertyPath": "/Properties/InstanceType"},
                {"PropertyPath": "/Properties/Tags"},
            ]
        }
        result = service._extract_cfn_property_diffs(drift_detail)
        assert len(result) == 2
        assert "/Properties/InstanceType" in result

    def test_extract_property_diffs_empty(self, service):
        result = service._extract_cfn_property_diffs({})
        assert result == []

    # -- Static comparison --

    def test_static_detects_deleted_resource(self, service):
        local_resources = {
            "MyVpc": {"Type": "AWS::EC2::VPC"},
            "MySubnet": {"Type": "AWS::EC2::Subnet"},
        }
        deployed = {
            "MyVpc": {"type": "AWS::EC2::VPC", "status": "CREATE_COMPLETE", "physical_id": "vpc-123"},
        }

        result = service._compare_template_vs_deployed(
            "template.yaml", local_resources, deployed, "my-stack"
        )

        assert result.has_drift
        assert len(result.drifted_resources) == 1
        assert result.drifted_resources[0].address == "MySubnet"
        assert result.drifted_resources[0].drift_type == DriftType.DELETED

    def test_static_detects_unmanaged_resource(self, service):
        local_resources = {
            "MyVpc": {"Type": "AWS::EC2::VPC"},
        }
        deployed = {
            "MyVpc": {"type": "AWS::EC2::VPC", "status": "CREATE_COMPLETE", "physical_id": "vpc-123"},
            "ManualSG": {"type": "AWS::EC2::SecurityGroup", "status": "CREATE_COMPLETE", "physical_id": "sg-456"},
        }

        result = service._compare_template_vs_deployed(
            "template.yaml", local_resources, deployed, "my-stack"
        )

        assert result.has_drift
        assert len(result.drifted_resources) == 1
        assert result.drifted_resources[0].address == "ManualSG"
        assert result.drifted_resources[0].drift_type == DriftType.UNMANAGED

    def test_static_no_drift_when_matching(self, service):
        local_resources = {
            "MyVpc": {"Type": "AWS::EC2::VPC"},
        }
        deployed = {
            "MyVpc": {"type": "AWS::EC2::VPC", "status": "CREATE_COMPLETE", "physical_id": "vpc-123"},
        }

        result = service._compare_template_vs_deployed(
            "template.yaml", local_resources, deployed, "my-stack"
        )

        assert not result.has_drift
        assert result.total_resources == 1
        assert result.coverage_pct == 100.0

    # -- Template parsing --

    def test_parse_yaml_template(self, service):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("AWSTemplateFormatVersion: '2010-09-09'\nResources:\n  MyBucket:\n    Type: AWS::S3::Bucket\n")
            f.flush()
            result = service._parse_template(f.name)

        assert result is not None
        assert "Resources" in result
        assert "MyBucket" in result["Resources"]
        Path(f.name).unlink()

    def test_parse_json_template(self, service):
        template = {"AWSTemplateFormatVersion": "2010-09-09", "Resources": {"MyFunc": {"Type": "AWS::Lambda::Function"}}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(template, f)
            f.flush()
            result = service._parse_template(f.name)

        assert result is not None
        assert "MyFunc" in result["Resources"]
        Path(f.name).unlink()

    def test_parse_invalid_template(self, service):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("not: valid: yaml: {{{{")
            f.flush()
            result = service._parse_template(f.name)

        # Should return None on parse failure
        assert result is None
        Path(f.name).unlink()

    # -- Live detection mock --

    def test_detect_drift_live_in_sync(self, service):
        """Test live detection when stack is in sync."""
        mock_client = MagicMock()
        mock_client.detect_stack_drift.return_value = {"StackDriftDetectionId": "test-id"}
        mock_client.describe_stack_drift_detection_status.return_value = {
            "DetectionStatus": "DETECTION_COMPLETE",
            "StackDriftStatus": "IN_SYNC",
            "DriftedStackResourceCount": 0,
        }
        mock_client.list_stack_resources.return_value = {
            "StackResourceSummaries": [{"LogicalResourceId": "R1"}, {"LogicalResourceId": "R2"}]
        }
        # Inject mock client (property returns _client if not None)
        service._client = mock_client

        result = service.detect_drift_live("my-stack")

        assert not result.has_drift
        assert result.error is None
        assert result.total_resources == 2

    def test_detect_drift_live_drifted(self, service):
        """Test live detection when stack has drifted."""
        mock_client = MagicMock()
        mock_client.detect_stack_drift.return_value = {"StackDriftDetectionId": "test-id"}
        mock_client.describe_stack_drift_detection_status.return_value = {
            "DetectionStatus": "DETECTION_COMPLETE",
            "StackDriftStatus": "DRIFTED",
            "DriftedStackResourceCount": 1,
        }

        # Mock paginator for resource drifts
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{
            "StackResourceDrifts": [{
                "StackResourceDriftStatus": "MODIFIED",
                "ResourceType": "AWS::EC2::SecurityGroup",
                "LogicalResourceId": "WebSG",
                "PhysicalResourceId": "sg-12345",
                "PropertyDifferences": [
                    {"PropertyPath": "/Properties/SecurityGroupIngress"}
                ],
            }]
        }]
        mock_client.list_stack_resources.return_value = {
            "StackResourceSummaries": [
                {"LogicalResourceId": "WebSG"},
                {"LogicalResourceId": "AppSG"},
            ]
        }
        mock_client.describe_stack_resource.return_value = {"StackResourceDetail": {}}
        service._client = mock_client

        result = service.detect_drift_live("my-stack")

        assert result.has_drift
        assert len(result.drifted_resources) == 1
        assert result.drifted_resources[0].resource_type == "AWS::EC2::SecurityGroup"
        assert result.drifted_resources[0].drift_type == DriftType.CHANGED
        assert result.drifted_resources[0].severity == DriftSeverity.MEDIUM

    # -- detect_drift_static with missing stack --

    def test_static_missing_stack(self, service):
        """When stack doesn't exist, return error."""
        mock_client = MagicMock()
        service._client = mock_client
        mock_client.describe_stack_resources.side_effect = Exception("Stack does not exist")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("AWSTemplateFormatVersion: '2010-09-09'\nResources:\n  Bucket:\n    Type: AWS::S3::Bucket\n")
            f.flush()
            result = service.detect_drift_static(f.name, "nonexistent-stack")

        assert result.error is not None
        Path(f.name).unlink()


class TestTagMatching:
    """Test tag filtering logic."""

    def test_no_filter_matches_all(self):
        assert _matches_tags({"env": "prod"}, {}) is True

    def test_exact_match(self):
        assert _matches_tags({"env": "prod", "team": "platform"}, {"env": "prod"}) is True

    def test_no_match(self):
        assert _matches_tags({"env": "dev"}, {"env": "prod"}) is False

    def test_wildcard_value(self):
        assert _matches_tags({"env": "anything"}, {"env": "*"}) is True

    def test_missing_key(self):
        assert _matches_tags({"env": "prod"}, {"team": "platform"}) is False

    def test_empty_resource_tags(self):
        assert _matches_tags({}, {"env": "prod"}) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
