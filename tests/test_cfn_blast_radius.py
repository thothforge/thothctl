"""Unit tests for CFN blast radius service."""
import json
from pathlib import Path

import pytest

from thothctl.services.check.project.cfn_blast_radius_service import (
    CfnBlastRadiusService,
    CfnBlastRadiusResult,
    CfnResource,
    result_to_dict,
)


@pytest.fixture
def service():
    return CfnBlastRadiusService()


@pytest.fixture
def simple_cfn_template(tmp_path):
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Resources": {
            "VPC": {
                "Type": "AWS::EC2::VPC",
                "Properties": {"CidrBlock": "10.0.0.0/16"},
            },
            "Subnet": {
                "Type": "AWS::EC2::Subnet",
                "DependsOn": "VPC",
                "Properties": {
                    "VpcId": {"Ref": "VPC"},
                    "CidrBlock": "10.0.1.0/24",
                },
            },
            "SecurityGroup": {
                "Type": "AWS::EC2::SecurityGroup",
                "Properties": {
                    "GroupDescription": "Test SG",
                    "VpcId": {"Ref": "VPC"},
                },
            },
            "RDS": {
                "Type": "AWS::RDS::DBInstance",
                "Properties": {
                    "DBSubnetGroupName": {"Ref": "Subnet"},
                    "VPCSecurityGroups": [{"Fn::GetAtt": ["SecurityGroup", "GroupId"]}],
                },
            },
        },
    }
    path = tmp_path / "template.yaml"
    import yaml
    path.write_text(yaml.dump(template))
    return str(path)


@pytest.fixture
def json_cfn_template(tmp_path):
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Resources": {
            "Bucket": {"Type": "AWS::S3::Bucket", "Properties": {}},
            "BucketPolicy": {
                "Type": "AWS::S3::BucketPolicy",
                "Properties": {"Bucket": {"Ref": "Bucket"}},
            },
        },
    }
    path = tmp_path / "stack.json"
    path.write_text(json.dumps(template))
    return str(path)


class TestBuildDependencyGraph:
    def test_explicit_depends_on(self, service, simple_cfn_template):
        template = service._parse_template(simple_cfn_template)
        graph = service._build_dependency_graph(template["Resources"])
        assert "VPC" in graph["Subnet"]

    def test_ref_dependency(self, service, simple_cfn_template):
        template = service._parse_template(simple_cfn_template)
        graph = service._build_dependency_graph(template["Resources"])
        # SecurityGroup depends on VPC via Ref
        assert "VPC" in graph["SecurityGroup"]

    def test_getatt_dependency(self, service, simple_cfn_template):
        template = service._parse_template(simple_cfn_template)
        graph = service._build_dependency_graph(template["Resources"])
        # RDS depends on SecurityGroup via Fn::GetAtt
        assert "SecurityGroup" in graph["RDS"]

    def test_ref_in_json_template(self, service, json_cfn_template):
        template = service._parse_template(json_cfn_template)
        graph = service._build_dependency_graph(template["Resources"])
        assert "Bucket" in graph["BucketPolicy"]

    def test_no_self_dependency(self, service, simple_cfn_template):
        template = service._parse_template(simple_cfn_template)
        graph = service._build_dependency_graph(template["Resources"])
        for lid, deps in graph.items():
            assert lid not in deps

    def test_sub_reference(self, service, tmp_path):
        template = {
            "Resources": {
                "Lambda": {"Type": "AWS::Lambda::Function", "Properties": {}},
                "Permission": {
                    "Type": "AWS::Lambda::Permission",
                    "Properties": {
                        "FunctionName": {"Fn::Sub": "${Lambda.Arn}"}
                    },
                },
            }
        }
        import yaml
        path = tmp_path / "sub.yaml"
        path.write_text(yaml.dump(template))
        parsed = service._parse_template(str(path))
        graph = service._build_dependency_graph(parsed["Resources"])
        assert "Lambda" in graph["Permission"]


class TestPropagateChanges:
    def test_propagates_to_dependents(self, service, simple_cfn_template):
        template = service._parse_template(simple_cfn_template)
        graph = service._build_dependency_graph(template["Resources"])
        # If VPC changes, Subnet and SecurityGroup should be affected
        affected = service._propagate_changes({"VPC"}, graph)
        assert "Subnet" in affected
        assert "SecurityGroup" in affected

    def test_cascading_propagation(self, service, simple_cfn_template):
        template = service._parse_template(simple_cfn_template)
        graph = service._build_dependency_graph(template["Resources"])
        # VPC → Subnet → RDS (transitive)
        # VPC → SecurityGroup → RDS (transitive)
        affected = service._propagate_changes({"VPC"}, graph)
        assert "RDS" in affected

    def test_leaf_change_doesnt_propagate(self, service, simple_cfn_template):
        template = service._parse_template(simple_cfn_template)
        graph = service._build_dependency_graph(template["Resources"])
        # RDS has no dependents, so only RDS is affected
        affected = service._propagate_changes({"RDS"}, graph)
        assert affected == {"RDS"}

    def test_empty_changes(self, service):
        graph = {"A": ["B"], "B": [], "C": ["A"]}
        affected = service._propagate_changes(set(), graph)
        assert affected == set()


class TestCalculateRisk:
    def test_low_risk(self, service):
        changed = [CfnResource(logical_id="X", resource_type="AWS::S3::Bucket", action="modify")]
        assert service._calculate_risk(10.0, changed) == "LOW"

    def test_medium_risk_critical_type(self, service):
        changed = [CfnResource(logical_id="X", resource_type="AWS::RDS::DBInstance", action="modify")]
        assert service._calculate_risk(15.0, changed) == "MEDIUM"

    def test_high_risk_removes(self, service):
        changed = [CfnResource(logical_id="X", resource_type="AWS::S3::Bucket", action="remove")]
        assert service._calculate_risk(25.0, changed) == "HIGH"

    def test_critical_risk_high_blast(self, service):
        changed = [CfnResource(logical_id="X", resource_type="AWS::EC2::VPC", action="remove")]
        assert service._calculate_risk(65.0, changed) == "CRITICAL"


class TestAssessStatic:
    def test_returns_result(self, service, simple_cfn_template):
        result = service.assess_static(simple_cfn_template)
        assert isinstance(result, CfnBlastRadiusResult)
        assert result.mode == "static"
        assert result.total_resources == 4

    def test_has_dependency_graph(self, service, simple_cfn_template):
        result = service.assess_static(simple_cfn_template)
        assert "VPC" in result.dependency_graph
        assert "Subnet" in result.dependency_graph

    def test_invalid_template_returns_empty(self, service, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("not: a: valid: cfn template")
        result = service.assess_static(str(path))
        assert result.total_resources == 0

    def test_json_template_works(self, service, json_cfn_template):
        result = service.assess_static(json_cfn_template)
        assert result.total_resources == 2


class TestResultToDict:
    def test_serializable(self, service, simple_cfn_template):
        result = service.assess_static(simple_cfn_template)
        d = result_to_dict(result)
        # Should be JSON serializable
        json_str = json.dumps(d)
        assert "static" in json_str
        assert "VPC" in json_str

    def test_has_expected_keys(self, service, simple_cfn_template):
        result = service.assess_static(simple_cfn_template)
        d = result_to_dict(result)
        assert "mode" in d
        assert "risk_level" in d
        assert "blast_radius_percentage" in d
        assert "changed_resources" in d
        assert "dependency_graph" in d
        assert "recommendations" in d
