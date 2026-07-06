"""Unit tests for topology_generator module."""
import json
import tempfile
from pathlib import Path

import pytest

from thothctl.services.document.topology_generator import (
    AWSCategory,
    ChangeAction,
    InfraTopology,
    MermaidTopologyRenderer,
    TopologyGenerator,
    TopologyNode,
    TopologyStack,
    get_resource_icon,
    generate_topology,
    render_topology_mermaid,
    topology_to_dict,
)


# ── get_resource_icon ────────────────────────────────────────────────────────

class TestGetResourceIcon:
    def test_known_ec2_instance(self):
        result = get_resource_icon("aws_instance")
        assert result["icon"] == "🖥️"
        assert result["label"] == "EC2"
        assert result["category"] == AWSCategory.COMPUTE

    def test_known_rds_cluster(self):
        result = get_resource_icon("aws_rds_cluster")
        assert result["icon"] == "🗄️"
        assert result["category"] == AWSCategory.DATABASE

    def test_known_vpc(self):
        result = get_resource_icon("aws_vpc")
        assert result["icon"] == "🌐"
        assert result["category"] == AWSCategory.NETWORK

    def test_known_s3_bucket(self):
        result = get_resource_icon("aws_s3_bucket")
        assert result["icon"] == "🪣"
        assert result["category"] == AWSCategory.STORAGE

    def test_known_lambda(self):
        result = get_resource_icon("aws_lambda_function")
        assert result["icon"] == "λ"
        assert result["category"] == AWSCategory.SERVERLESS

    def test_unknown_iam_resource_infers_security(self):
        result = get_resource_icon("aws_iam_something_new")
        assert result["category"] == AWSCategory.SECURITY
        assert result["icon"] == "🔑"

    def test_unknown_vpc_resource_infers_network(self):
        result = get_resource_icon("aws_vpc_something")
        assert result["category"] == AWSCategory.NETWORK

    def test_completely_unknown_resource(self):
        result = get_resource_icon("aws_new_service_thing")
        assert result["category"] == AWSCategory.OTHER
        assert result["icon"] == "☁️"
        assert "New Service Thing" in result["label"]


# ── TopologyGenerator ────────────────────────────────────────────────────────

class TestTopologyGenerator:
    @pytest.fixture
    def sample_plan(self):
        """A minimal tfplan.json structure."""
        return {
            "format_version": "1.2",
            "terraform_version": "1.9.0",
            "planned_values": {
                "root_module": {
                    "resources": [],
                    "child_modules": [
                        {
                            "address": "module.vpc",
                            "resources": [
                                {
                                    "address": "module.vpc.aws_vpc.this[0]",
                                    "type": "aws_vpc",
                                    "name": "this",
                                    "values": {"cidr_block": "10.0.0.0/16"},
                                },
                                {
                                    "address": "module.vpc.aws_subnet.private[0]",
                                    "type": "aws_subnet",
                                    "name": "private",
                                    "values": {"cidr_block": "10.0.1.0/24"},
                                },
                            ],
                        }
                    ],
                }
            },
            "resource_changes": [
                {
                    "address": "module.vpc.aws_vpc.this[0]",
                    "type": "aws_vpc",
                    "change": {"actions": ["create"], "after": {"cidr_block": "10.0.0.0/16"}},
                },
                {
                    "address": "module.vpc.aws_subnet.private[0]",
                    "type": "aws_subnet",
                    "change": {"actions": ["no-op"], "after": {"cidr_block": "10.0.1.0/24"}},
                },
            ],
            "configuration": {"root_module": {"module_calls": {}}},
        }

    @pytest.fixture
    def plan_dir(self, sample_plan, tmp_path):
        """Create a temp directory with a tfplan.json."""
        stack_dir = tmp_path / "stacks" / "network" / "vpc"
        stack_dir.mkdir(parents=True)
        plan_path = stack_dir / "tfplan.json"
        plan_path.write_text(json.dumps(sample_plan))
        return tmp_path / "stacks"

    def test_generate_from_plans_finds_stacks(self, plan_dir):
        gen = TopologyGenerator()
        topology = gen.generate_from_plans(str(plan_dir), "test-project")
        assert topology.project_name == "test-project"
        assert len(topology.stacks) == 1

    def test_stack_has_correct_nodes(self, plan_dir):
        gen = TopologyGenerator()
        topology = gen.generate_from_plans(str(plan_dir))
        stack = topology.stacks[0]
        assert len(stack.nodes) == 2
        types = {n.resource_type for n in stack.nodes}
        assert "aws_vpc" in types
        assert "aws_subnet" in types

    def test_node_action_from_resource_changes(self, plan_dir):
        gen = TopologyGenerator()
        topology = gen.generate_from_plans(str(plan_dir))
        stack = topology.stacks[0]
        vpc_node = next(n for n in stack.nodes if n.resource_type == "aws_vpc")
        subnet_node = next(n for n in stack.nodes if n.resource_type == "aws_subnet")
        assert vpc_node.action == ChangeAction.CREATE
        assert subnet_node.action == ChangeAction.NO_CHANGE

    def test_node_icon_assigned(self, plan_dir):
        gen = TopologyGenerator()
        topology = gen.generate_from_plans(str(plan_dir))
        vpc_node = next(n for n in topology.stacks[0].nodes if n.resource_type == "aws_vpc")
        assert vpc_node.icon == "🌐"
        assert vpc_node.label == "VPC"
        assert vpc_node.category == AWSCategory.NETWORK

    def test_summary_counts(self, plan_dir):
        gen = TopologyGenerator()
        topology = gen.generate_from_plans(str(plan_dir))
        assert topology.summary["total_stacks"] == 1
        assert topology.summary["total_resources"] == 2
        assert topology.summary["changed_resources"] == 1  # Only VPC is CREATE
        assert "network" in topology.summary["categories"]

    def test_empty_directory_returns_empty_topology(self, tmp_path):
        gen = TopologyGenerator()
        topology = gen.generate_from_plans(str(tmp_path), "empty")
        assert topology.project_name == "empty"
        assert topology.stacks == []
        assert topology.summary == {}

    def test_delete_action_detected(self, tmp_path):
        plan = {
            "planned_values": {"root_module": {"resources": [
                {"address": "aws_s3_bucket.old", "type": "aws_s3_bucket", "name": "old", "values": {}}
            ]}},
            "resource_changes": [
                {"address": "aws_s3_bucket.old", "type": "aws_s3_bucket",
                 "change": {"actions": ["delete"], "after": None}}
            ],
            "configuration": {"root_module": {}},
        }
        plan_path = tmp_path / "tfplan.json"
        plan_path.write_text(json.dumps(plan))
        gen = TopologyGenerator()
        topology = gen.generate_from_plans(str(tmp_path))
        node = topology.stacks[0].nodes[0]
        assert node.action == ChangeAction.DELETE

    def test_replace_action_detected(self, tmp_path):
        plan = {
            "planned_values": {"root_module": {"resources": [
                {"address": "aws_instance.web", "type": "aws_instance", "name": "web", "values": {}}
            ]}},
            "resource_changes": [
                {"address": "aws_instance.web", "type": "aws_instance",
                 "change": {"actions": ["delete", "create"], "after": {}}}
            ],
            "configuration": {"root_module": {}},
        }
        plan_path = tmp_path / "tfplan.json"
        plan_path.write_text(json.dumps(plan))
        gen = TopologyGenerator()
        topology = gen.generate_from_plans(str(tmp_path))
        node = topology.stacks[0].nodes[0]
        assert node.action == ChangeAction.REPLACE


# ── MermaidTopologyRenderer ──────────────────────────────────────────────────

class TestMermaidTopologyRenderer:
    @pytest.fixture
    def simple_topology(self):
        return InfraTopology(
            project_name="test",
            stacks=[
                TopologyStack(
                    name="network/vpc",
                    path="network/vpc",
                    nodes=[
                        TopologyNode(
                            address="module.vpc.aws_vpc.this[0]",
                            resource_type="aws_vpc",
                            name="this",
                            module="module.vpc",
                            icon="🌐",
                            label="VPC",
                            category=AWSCategory.NETWORK,
                            action=ChangeAction.CREATE,
                        ),
                        TopologyNode(
                            address="module.vpc.aws_subnet.db[0]",
                            resource_type="aws_subnet",
                            name="db",
                            module="module.vpc",
                            icon="🔲",
                            label="Subnet",
                            category=AWSCategory.NETWORK,
                            action=ChangeAction.NO_CHANGE,
                        ),
                    ],
                    edges=[],
                )
            ],
        )

    def test_render_contains_mermaid_header(self, simple_topology):
        renderer = MermaidTopologyRenderer()
        result = renderer.render(simple_topology)
        assert "%%{init:" in result
        assert "graph LR" in result

    def test_render_contains_subgraph(self, simple_topology):
        renderer = MermaidTopologyRenderer()
        result = renderer.render(simple_topology)
        assert 'subgraph' in result
        assert 'network / vpc' in result

    def test_render_contains_node_with_icon(self, simple_topology):
        renderer = MermaidTopologyRenderer()
        result = renderer.render(simple_topology)
        assert "🌐 VPC" in result
        assert "🔲 Subnet" in result

    def test_render_contains_action_badges(self, simple_topology):
        renderer = MermaidTopologyRenderer()
        result = renderer.render(simple_topology)
        assert "🆕" in result  # CREATE badge for VPC

    def test_render_contains_classdefs(self, simple_topology):
        renderer = MermaidTopologyRenderer()
        result = renderer.render(simple_topology)
        assert "classDef existingNode" in result
        assert "classDef createNode" in result
        assert "classDef deleteNode" in result

    def test_create_node_uses_create_class(self, simple_topology):
        renderer = MermaidTopologyRenderer()
        result = renderer.render(simple_topology)
        assert ":::createNode" in result

    def test_existing_node_uses_existing_class(self, simple_topology):
        renderer = MermaidTopologyRenderer()
        result = renderer.render(simple_topology)
        assert ":::existingNode" in result

    def test_show_unchanged_false_hides_no_change_nodes(self, simple_topology):
        renderer = MermaidTopologyRenderer()
        result = renderer.render(simple_topology, show_unchanged=False)
        assert "🔲 Subnet" not in result
        assert "🌐 VPC" in result

    def test_sanitize_id(self):
        renderer = MermaidTopologyRenderer()
        assert renderer._sanitize_id("module.vpc.aws_vpc.this[0]") == "module_vpc_aws_vpc_this_0"
        assert renderer._sanitize_id("a/b-c.d") == "a_b_c_d"


# ── topology_to_dict ─────────────────────────────────────────────────────────

class TestTopologyToDict:
    def test_returns_serializable_dict(self):
        topology = InfraTopology(
            project_name="proj",
            stacks=[
                TopologyStack(
                    name="stack1", path="s1",
                    nodes=[TopologyNode(
                        address="aws_vpc.x", resource_type="aws_vpc", name="x",
                        module="root", icon="🌐", label="VPC",
                        category=AWSCategory.NETWORK, action=ChangeAction.CREATE,
                    )],
                    edges=[],
                )
            ],
            summary={"total_stacks": 1, "total_resources": 1},
        )
        d = topology_to_dict(topology)
        # Should be JSON serializable
        json_str = json.dumps(d)
        assert "proj" in json_str
        assert "aws_vpc" in json_str
        assert "create" in json_str
        assert "network" in json_str

    def test_dict_has_expected_structure(self):
        topology = InfraTopology(project_name="test", stacks=[], summary={})
        d = topology_to_dict(topology)
        assert "project_name" in d
        assert "summary" in d
        assert "stacks" in d
        assert isinstance(d["stacks"], list)


# ── Integration test with real-ish plan ──────────────────────────────────────

class TestIntegration:
    def test_full_pipeline(self, tmp_path):
        """End-to-end: plan → topology → mermaid → dict."""
        plan = {
            "planned_values": {"root_module": {"child_modules": [
                {"address": "module.web", "resources": [
                    {"address": "module.web.aws_instance.app[0]", "type": "aws_instance", "name": "app", "values": {"instance_type": "t3.micro"}},
                    {"address": "module.web.aws_security_group.app", "type": "aws_security_group", "name": "app", "values": {}},
                ]},
                {"address": "module.db", "resources": [
                    {"address": "module.db.aws_rds_cluster.main[0]", "type": "aws_rds_cluster", "name": "main", "values": {}},
                ]}
            ]}},
            "resource_changes": [
                {"address": "module.web.aws_instance.app[0]", "type": "aws_instance", "change": {"actions": ["create"], "after": {}}},
                {"address": "module.web.aws_security_group.app", "type": "aws_security_group", "change": {"actions": ["create"], "after": {}}},
                {"address": "module.db.aws_rds_cluster.main[0]", "type": "aws_rds_cluster", "change": {"actions": ["update"], "after": {}}},
            ],
            "configuration": {"root_module": {"module_calls": {}}},
        }
        plan_path = tmp_path / "tfplan.json"
        plan_path.write_text(json.dumps(plan))

        # Generate
        topology = generate_topology(str(tmp_path), "integration-test")
        assert topology.summary["total_resources"] == 3
        assert topology.summary["changed_resources"] == 3

        # Render
        mermaid = render_topology_mermaid(topology)
        assert "🖥️ EC2 🆕" in mermaid
        assert "🗄️ Aurora ✏️" in mermaid  # update badge
        assert "classDef updateNode" in mermaid

        # Dict
        d = topology_to_dict(topology)
        assert d["project_name"] == "integration-test"
        assert len(d["stacks"]) == 1  # single plan file = 1 stack
        nodes = d["stacks"][0]["nodes"]
        assert any(n["action"] == "create" for n in nodes)
        assert any(n["action"] == "update" for n in nodes)
