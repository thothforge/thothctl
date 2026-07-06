"""Infrastructure topology generator from terraform/terragrunt plans.

Parses tfplan.json to produce a topology data structure that can be
rendered as Mermaid diagrams (with AWS icons) or interactive HTML.
Supports blast radius overlay to highlight changed resources.
"""
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── AWS Resource Type → Icon Mapping ────────────────────────────────────────

class AWSCategory(Enum):
    COMPUTE = "compute"
    DATABASE = "database"
    NETWORK = "network"
    STORAGE = "storage"
    SECURITY = "security"
    SERVERLESS = "serverless"
    CONTAINERS = "containers"
    MONITORING = "monitoring"
    INTEGRATION = "integration"
    OTHER = "other"


# Map terraform resource types to display metadata
AWS_RESOURCE_MAP: Dict[str, Dict] = {
    # Compute
    "aws_instance": {"icon": "🖥️", "label": "EC2", "category": AWSCategory.COMPUTE},
    "aws_launch_template": {"icon": "🖥️", "label": "Launch Template", "category": AWSCategory.COMPUTE},
    "aws_autoscaling_group": {"icon": "📐", "label": "ASG", "category": AWSCategory.COMPUTE},
    # Database
    "aws_db_instance": {"icon": "🗄️", "label": "RDS", "category": AWSCategory.DATABASE},
    "aws_rds_cluster": {"icon": "🗄️", "label": "Aurora", "category": AWSCategory.DATABASE},
    "aws_rds_cluster_instance": {"icon": "🗄️", "label": "Aurora Instance", "category": AWSCategory.DATABASE},
    "aws_dynamodb_table": {"icon": "⚡", "label": "DynamoDB", "category": AWSCategory.DATABASE},
    "aws_elasticache_cluster": {"icon": "🧊", "label": "ElastiCache", "category": AWSCategory.DATABASE},
    # Network
    "aws_vpc": {"icon": "🌐", "label": "VPC", "category": AWSCategory.NETWORK},
    "aws_subnet": {"icon": "🔲", "label": "Subnet", "category": AWSCategory.NETWORK},
    "aws_internet_gateway": {"icon": "🌍", "label": "IGW", "category": AWSCategory.NETWORK},
    "aws_nat_gateway": {"icon": "🔀", "label": "NAT GW", "category": AWSCategory.NETWORK},
    "aws_route_table": {"icon": "🗺️", "label": "Route Table", "category": AWSCategory.NETWORK},
    "aws_route_table_association": {"icon": "🔗", "label": "RT Assoc", "category": AWSCategory.NETWORK},
    "aws_security_group": {"icon": "🛡️", "label": "Security Group", "category": AWSCategory.NETWORK},
    "aws_security_group_rule": {"icon": "🛡️", "label": "SG Rule", "category": AWSCategory.NETWORK},
    "aws_vpc_security_group_ingress_rule": {"icon": "🛡️", "label": "SG Ingress", "category": AWSCategory.NETWORK},
    "aws_vpc_security_group_egress_rule": {"icon": "🛡️", "label": "SG Egress", "category": AWSCategory.NETWORK},
    "aws_lb": {"icon": "⚖️", "label": "ALB/NLB", "category": AWSCategory.NETWORK},
    "aws_lb_target_group": {"icon": "🎯", "label": "Target Group", "category": AWSCategory.NETWORK},
    "aws_lb_listener": {"icon": "👂", "label": "Listener", "category": AWSCategory.NETWORK},
    "aws_vpclattice_service": {"icon": "🔗", "label": "VPC Lattice", "category": AWSCategory.NETWORK},
    "aws_vpclattice_service_network": {"icon": "🕸️", "label": "Lattice Network", "category": AWSCategory.NETWORK},
    "aws_vpclattice_service_network_vpc_association": {"icon": "🔗", "label": "Lattice VPC Assoc", "category": AWSCategory.NETWORK},
    "aws_ec2_network_insights_path": {"icon": "🔍", "label": "Reachability Path", "category": AWSCategory.NETWORK},
    "aws_ec2_network_insights_analysis": {"icon": "🔍", "label": "Reachability Analysis", "category": AWSCategory.NETWORK},
    # Storage
    "aws_s3_bucket": {"icon": "🪣", "label": "S3", "category": AWSCategory.STORAGE},
    "aws_ebs_volume": {"icon": "💾", "label": "EBS", "category": AWSCategory.STORAGE},
    "aws_efs_file_system": {"icon": "📁", "label": "EFS", "category": AWSCategory.STORAGE},
    # Security/IAM
    "aws_iam_role": {"icon": "🔑", "label": "IAM Role", "category": AWSCategory.SECURITY},
    "aws_iam_policy": {"icon": "📜", "label": "IAM Policy", "category": AWSCategory.SECURITY},
    "aws_iam_role_policy_attachment": {"icon": "📎", "label": "Policy Attach", "category": AWSCategory.SECURITY},
    "aws_kms_key": {"icon": "🔐", "label": "KMS Key", "category": AWSCategory.SECURITY},
    # Serverless
    "aws_lambda_function": {"icon": "λ", "label": "Lambda", "category": AWSCategory.SERVERLESS},
    "aws_api_gateway_rest_api": {"icon": "🚪", "label": "API Gateway", "category": AWSCategory.SERVERLESS},
    "aws_apigatewayv2_api": {"icon": "🚪", "label": "API GW v2", "category": AWSCategory.SERVERLESS},
    "aws_sqs_queue": {"icon": "📬", "label": "SQS", "category": AWSCategory.INTEGRATION},
    "aws_sns_topic": {"icon": "📢", "label": "SNS", "category": AWSCategory.INTEGRATION},
    # Containers
    "aws_ecs_cluster": {"icon": "🐳", "label": "ECS Cluster", "category": AWSCategory.CONTAINERS},
    "aws_ecs_service": {"icon": "🐳", "label": "ECS Service", "category": AWSCategory.CONTAINERS},
    "aws_ecs_task_definition": {"icon": "📋", "label": "Task Def", "category": AWSCategory.CONTAINERS},
    "aws_eks_cluster": {"icon": "☸️", "label": "EKS", "category": AWSCategory.CONTAINERS},
    # Monitoring
    "aws_cloudwatch_log_group": {"icon": "📊", "label": "CloudWatch Logs", "category": AWSCategory.MONITORING},
    "aws_cloudwatch_metric_alarm": {"icon": "🚨", "label": "CW Alarm", "category": AWSCategory.MONITORING},
    "aws_cloudtrail": {"icon": "📝", "label": "CloudTrail", "category": AWSCategory.MONITORING},
    "aws_flow_log": {"icon": "📈", "label": "Flow Log", "category": AWSCategory.MONITORING},
    # Free/structural (hidden from main view but counted)
    "aws_default_network_acl": {"icon": "🔲", "label": "Default NACL", "category": AWSCategory.NETWORK},
    "aws_default_route_table": {"icon": "🗺️", "label": "Default RT", "category": AWSCategory.NETWORK},
    "aws_default_security_group": {"icon": "🛡️", "label": "Default SG", "category": AWSCategory.NETWORK},
    "aws_db_subnet_group": {"icon": "🔲", "label": "DB Subnet Group", "category": AWSCategory.DATABASE},
}


def get_resource_icon(resource_type: str) -> Dict:
    """Get icon and metadata for a terraform resource type."""
    if resource_type in AWS_RESOURCE_MAP:
        return AWS_RESOURCE_MAP[resource_type]
    # Fallback: infer from prefix
    if resource_type.startswith("aws_iam"):
        return {"icon": "🔑", "label": resource_type.replace("aws_", "").replace("_", " ").title(), "category": AWSCategory.SECURITY}
    if resource_type.startswith("aws_vpc") or resource_type.startswith("aws_subnet"):
        return {"icon": "🌐", "label": resource_type.replace("aws_", "").replace("_", " ").title(), "category": AWSCategory.NETWORK}
    return {"icon": "☁️", "label": resource_type.replace("aws_", "").replace("_", " ").title(), "category": AWSCategory.OTHER}


# ── Data Models ─────────────────────────────────────────────────────────────

class ChangeAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"
    NO_CHANGE = "no-change"


@dataclass
class TopologyNode:
    """A resource node in the topology."""
    address: str
    resource_type: str
    name: str
    module: str
    icon: str
    label: str
    category: AWSCategory
    action: ChangeAction = ChangeAction.NO_CHANGE
    attributes: Dict = field(default_factory=dict)


@dataclass
class TopologyEdge:
    """A dependency edge between nodes."""
    source: str  # address
    target: str  # address
    label: str = ""


@dataclass
class TopologyStack:
    """A stack (terragrunt module) in the topology."""
    name: str
    path: str
    nodes: List[TopologyNode] = field(default_factory=list)
    edges: List[TopologyEdge] = field(default_factory=list)


@dataclass
class InfraTopology:
    """Complete infrastructure topology."""
    project_name: str
    stacks: List[TopologyStack] = field(default_factory=list)
    inter_stack_edges: List[TopologyEdge] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)


# ── Topology Generator ──────────────────────────────────────────────────────

class TopologyGenerator:
    """Generate infrastructure topology from terraform plan files."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def generate_from_plans(self, plan_dir: str, project_name: str = "") -> InfraTopology:
        """Generate topology from all tfplan.json files in a directory.
        
        Args:
            plan_dir: Directory containing tfplan.json files (recursive)
            project_name: Project name for the topology
            
        Returns:
            InfraTopology with all stacks, nodes, and edges
        """
        plan_dir_path = Path(plan_dir)
        if not project_name:
            project_name = plan_dir_path.name

        topology = InfraTopology(project_name=project_name)

        # Find all tfplan.json files
        plan_files = list(plan_dir_path.rglob("tfplan.json"))
        plan_files = [p for p in plan_files if ".terraform" not in str(p)]

        if not plan_files:
            self.logger.warning(f"No tfplan.json files found in {plan_dir}")
            return topology

        for plan_file in plan_files:
            stack = self._parse_plan_to_stack(plan_file, plan_dir_path)
            if stack and stack.nodes:
                topology.stacks.append(stack)

        # Build summary
        total_nodes = sum(len(s.nodes) for s in topology.stacks)
        changed_nodes = sum(
            1 for s in topology.stacks for n in s.nodes
            if n.action != ChangeAction.NO_CHANGE
        )
        topology.summary = {
            "total_stacks": len(topology.stacks),
            "total_resources": total_nodes,
            "changed_resources": changed_nodes,
            "categories": self._count_categories(topology),
        }

        return topology

    def _parse_plan_to_stack(self, plan_file: Path, base_dir: Path) -> Optional[TopologyStack]:
        """Parse a single tfplan.json into a TopologyStack."""
        try:
            with open(plan_file, "r") as f:
                plan = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Failed to parse {plan_file}: {e}")
            return None

        # Determine stack name from path
        rel_path = plan_file.parent.relative_to(base_dir)
        stack_name = str(rel_path).replace("tfplan/", "").replace("\\", "/")

        stack = TopologyStack(name=stack_name, path=str(rel_path))

        # Parse resource_changes for action info
        change_actions: Dict[str, ChangeAction] = {}
        for change in plan.get("resource_changes", []):
            actions = change.get("change", {}).get("actions", [])
            address = change.get("address", "")
            if actions == ["no-op"]:
                change_actions[address] = ChangeAction.NO_CHANGE
            elif actions == ["create"]:
                change_actions[address] = ChangeAction.CREATE
            elif actions == ["delete"]:
                change_actions[address] = ChangeAction.DELETE
            elif "update" in actions:
                change_actions[address] = ChangeAction.UPDATE
            elif "delete" in actions and "create" in actions:
                change_actions[address] = ChangeAction.REPLACE
            elif actions == ["read"]:
                continue  # Skip data sources

        # Collect resources from planned_values (complete desired state)
        root_module = plan.get("planned_values", {}).get("root_module", {})
        self._collect_nodes(root_module, stack, change_actions, "")

        # Extract edges from configuration (dependency references)
        config_root = plan.get("configuration", {}).get("root_module", {})
        self._extract_edges(config_root, stack, "")

        return stack

    def _collect_nodes(
        self, module: Dict, stack: TopologyStack,
        change_actions: Dict[str, ChangeAction], prefix: str
    ):
        """Recursively collect resource nodes from planned_values."""
        for resource in module.get("resources", []):
            res_type = resource.get("type", "")
            res_name = resource.get("name", "")
            address = resource.get("address", f"{res_type}.{res_name}")
            if prefix:
                full_address = f"{prefix}.{address}" if not address.startswith(prefix) else address
            else:
                full_address = address

            # Get icon mapping
            meta = get_resource_icon(res_type)

            # Determine action
            action = change_actions.get(full_address, ChangeAction.NO_CHANGE)
            # Also check without prefix for partial matches
            if action == ChangeAction.NO_CHANGE:
                for addr, act in change_actions.items():
                    if address in addr or addr.endswith(address):
                        action = act
                        break

            node = TopologyNode(
                address=full_address,
                resource_type=res_type,
                name=res_name,
                module=prefix or "root",
                icon=meta["icon"],
                label=meta["label"],
                category=meta["category"],
                action=action,
                attributes=resource.get("values", {}),
            )
            stack.nodes.append(node)

        # Recurse into child modules
        for child in module.get("child_modules", []):
            child_prefix = child.get("address", "")
            self._collect_nodes(child, stack, change_actions, child_prefix)

    def _extract_edges(self, config_module: Dict, stack: TopologyStack, prefix: str):
        """Extract dependency edges from configuration block."""
        for resource in config_module.get("resources", []):
            res_address = f"{resource.get('type', '')}.{resource.get('name', '')}"
            if prefix:
                res_address = f"{prefix}.{res_address}"

            # Look for references in expressions
            for attr_name, attr_config in resource.get("expressions", {}).items():
                refs = attr_config.get("references", []) if isinstance(attr_config, dict) else []
                for ref in refs:
                    if ref and not ref.startswith("var.") and not ref.startswith("local."):
                        stack.edges.append(TopologyEdge(
                            source=res_address,
                            target=ref,
                            label=attr_name,
                        ))

        # Recurse into child modules
        for child in config_module.get("module_calls", {}).values():
            child_module = child.get("module", {})
            child_prefix = prefix  # simplified
            self._extract_edges(child_module, stack, child_prefix)

    def _count_categories(self, topology: InfraTopology) -> Dict[str, int]:
        """Count resources by category."""
        counts: Dict[str, int] = {}
        for stack in topology.stacks:
            for node in stack.nodes:
                cat = node.category.value
                counts[cat] = counts.get(cat, 0) + 1
        return counts


# ── Mermaid Renderer ────────────────────────────────────────────────────────

class MermaidTopologyRenderer:
    """Render InfraTopology as a Mermaid diagram with AWS icons."""

    # Action → mermaid class name
    ACTION_STYLES = {
        ChangeAction.CREATE: "createNode",
        ChangeAction.UPDATE: "updateNode",
        ChangeAction.DELETE: "deleteNode",
        ChangeAction.REPLACE: "replaceNode",
        ChangeAction.NO_CHANGE: "existingNode",
    }

    def render(self, topology: InfraTopology, show_unchanged: bool = True) -> str:
        """Render topology as Mermaid flowchart diagram.
        
        Args:
            topology: The infrastructure topology to render
            show_unchanged: If False, only show changed resources
            
        Returns:
            Mermaid diagram string
        """
        lines = [
            "%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#e3f2fd','primaryTextColor':'#1565c0','primaryBorderColor':'#1976d2','lineColor':'#42a5f5','fontSize':'14px'}}}%%",
            "graph LR",
        ]

        # Collect all valid node IDs for edge filtering
        valid_node_ids: Set[str] = set()

        # Generate subgraphs per stack
        for stack in topology.stacks:
            stack_id = self._sanitize_id(stack.name)
            stack_label = stack.name.replace("/", " / ")
            lines.append(f'    subgraph {stack_id}["{stack_label}"]')

            for node in stack.nodes:
                if not show_unchanged and node.action == ChangeAction.NO_CHANGE:
                    continue

                node_id = self._sanitize_id(node.address)
                valid_node_ids.add(node_id)
                action_badge = self._get_action_badge(node.action)
                node_label = f"{node.icon} {node.label}"
                if action_badge:
                    node_label += f" {action_badge}"

                style_class = self.ACTION_STYLES.get(node.action, "existingNode")
                lines.append(f'        {node_id}["{node_label}"]:::{style_class}')

            lines.append("    end")
            lines.append("")

        # Add meaningful edges only (match by resource suffix since config uses bare names)
        # Build a lookup: bare "type.name" → full sanitized node_id
        bare_to_node_id: Dict[str, str] = {}
        for stack in topology.stacks:
            for node in stack.nodes:
                # Key: "aws_rds_cluster.this" from "module.aurora.aws_rds_cluster.this[0]"
                parts = node.address.split(".")
                # Find the resource type.name (last two meaningful parts before [])
                bare_parts = []
                for p in parts:
                    if p.startswith("module"):
                        continue
                    bare_parts.append(p.split("[")[0])
                bare_key = ".".join(bare_parts[-2:]) if len(bare_parts) >= 2 else ".".join(bare_parts)
                node_id = self._sanitize_id(node.address)
                if node_id in valid_node_ids:
                    bare_to_node_id[self._sanitize_id(bare_key)] = node_id

        edge_count = 0
        max_edges = 40
        seen_edges: Set[Tuple[str, str]] = set()

        for stack in topology.stacks:
            for edge in stack.edges:
                if edge_count >= max_edges:
                    break
                # Try direct match first
                source_id = self._sanitize_id(edge.source)
                target_id = self._sanitize_id(edge.target)

                # Resolve via bare name lookup
                resolved_source = bare_to_node_id.get(source_id, source_id)
                resolved_target = bare_to_node_id.get(target_id, target_id)

                # Also try without trailing attribute (e.g. "aws_rds_cluster_this_0_cluster_identifier" → "aws_rds_cluster_this_0")
                if resolved_target not in valid_node_ids:
                    # Try progressively shorter keys
                    tgt_parts = target_id.split("_")
                    for i in range(len(tgt_parts), 1, -1):
                        candidate = "_".join(tgt_parts[:i])
                        if candidate in bare_to_node_id:
                            resolved_target = bare_to_node_id[candidate]
                            break
                        if candidate in valid_node_ids:
                            resolved_target = candidate
                            break

                edge_pair = (resolved_source, resolved_target)
                if (resolved_source in valid_node_ids and resolved_target in valid_node_ids
                        and resolved_source != resolved_target and edge_pair not in seen_edges):
                    seen_edges.add(edge_pair)
                    lines.append(f"    {resolved_source} -.-> {resolved_target}")
                    edge_count += 1

        # Add classDefs for action styling
        lines.extend([
            "",
            "    classDef existingNode fill:#e8f5e9,stroke:#4caf50,stroke-width:1px,color:#2e7d32",
            "    classDef createNode fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#0d47a1",
            "    classDef updateNode fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#e65100",
            "    classDef deleteNode fill:#ffebee,stroke:#d32f2f,stroke-width:3px,color:#b71c1c,stroke-dasharray: 5 5",
            "    classDef replaceNode fill:#fce4ec,stroke:#c2185b,stroke-width:3px,color:#880e4f",
        ])

        return "\n".join(lines)

    def _sanitize_id(self, address: str) -> str:
        """Convert a resource address to a valid mermaid node ID."""
        return (
            address.replace(".", "_")
            .replace("[", "_")
            .replace("]", "")
            .replace('"', "")
            .replace("/", "_")
            .replace("-", "_")
            .replace(" ", "_")
        )

    def _get_action_badge(self, action: ChangeAction) -> str:
        """Get a badge string for the change action."""
        badges = {
            ChangeAction.CREATE: "🆕",
            ChangeAction.UPDATE: "✏️",
            ChangeAction.DELETE: "🗑️",
            ChangeAction.REPLACE: "♻️",
        }
        return badges.get(action, "")


# ── Public API ──────────────────────────────────────────────────────────────

def generate_topology(plan_dir: str, project_name: str = "") -> InfraTopology:
    """Generate infrastructure topology from plan files."""
    generator = TopologyGenerator()
    return generator.generate_from_plans(plan_dir, project_name)


def render_topology_mermaid(topology: InfraTopology, show_unchanged: bool = True) -> str:
    """Render topology as Mermaid diagram string."""
    renderer = MermaidTopologyRenderer()
    return renderer.render(topology, show_unchanged)


def topology_to_dict(topology: InfraTopology) -> Dict:
    """Convert topology to a JSON-serializable dict for the API."""
    return {
        "project_name": topology.project_name,
        "summary": topology.summary,
        "stacks": [
            {
                "name": stack.name,
                "path": stack.path,
                "nodes": [
                    {
                        "address": n.address,
                        "resource_type": n.resource_type,
                        "name": n.name,
                        "module": n.module,
                        "icon": n.icon,
                        "label": n.label,
                        "category": n.category.value,
                        "action": n.action.value,
                    }
                    for n in stack.nodes
                ],
                "edges": [
                    {"source": e.source, "target": e.target, "label": e.label}
                    for e in stack.edges
                ],
            }
            for stack in topology.stacks
        ],
    }
