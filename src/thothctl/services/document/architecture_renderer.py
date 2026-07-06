"""Architecture diagram renderer using mingrammer/diagrams.

Converts InfraTopology into professional AWS architecture diagrams
with official AWS icons. Generates PNG/SVG via Graphviz.
"""
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# Map terraform resource types to diagrams classes (import path + class name)
DIAGRAMS_CLASS_MAP: Dict[str, tuple] = {
    # Compute
    "aws_instance": ("diagrams.aws.compute", "EC2"),
    "aws_launch_template": ("diagrams.aws.compute", "EC2"),
    "aws_autoscaling_group": ("diagrams.aws.compute", "AutoScaling"),
    "aws_eks_cluster": ("diagrams.aws.compute", "EKS"),
    # Database
    "aws_db_instance": ("diagrams.aws.database", "RDS"),
    "aws_rds_cluster": ("diagrams.aws.database", "Aurora"),
    "aws_rds_cluster_instance": ("diagrams.aws.database", "AuroraInstance"),
    "aws_dynamodb_table": ("diagrams.aws.database", "DDB"),
    "aws_elasticache_cluster": ("diagrams.aws.database", "ElasticacheForRedis"),
    "aws_db_subnet_group": ("diagrams.aws.database", "RDS"),
    # Network
    "aws_vpc": ("diagrams.aws.network", "VPC"),
    "aws_subnet": ("diagrams.aws.network", "PublicSubnet"),
    "aws_internet_gateway": ("diagrams.aws.network", "InternetGateway"),
    "aws_nat_gateway": ("diagrams.aws.network", "NATGateway"),
    "aws_route_table": ("diagrams.aws.network", "RouteTable"),
    "aws_route_table_association": ("diagrams.aws.network", "RouteTable"),
    "aws_security_group": ("diagrams.aws.network", "VPC"),
    "aws_vpc_security_group_ingress_rule": ("diagrams.aws.network", "VPC"),
    "aws_vpc_security_group_egress_rule": ("diagrams.aws.network", "VPC"),
    "aws_lb": ("diagrams.aws.network", "ALB"),
    "aws_lb_target_group": ("diagrams.aws.network", "ALB"),
    "aws_vpclattice_service_network": ("diagrams.aws.network", "VPC"),
    "aws_vpclattice_service_network_vpc_association": ("diagrams.aws.network", "VPC"),
    "aws_ec2_network_insights_path": ("diagrams.aws.network", "VPC"),
    "aws_ec2_network_insights_analysis": ("diagrams.aws.network", "VPC"),
    # Storage
    "aws_s3_bucket": ("diagrams.aws.storage", "S3"),
    "aws_ebs_volume": ("diagrams.aws.storage", "EBS"),
    "aws_efs_file_system": ("diagrams.aws.storage", "EFS"),
    # Security
    "aws_iam_role": ("diagrams.aws.security", "IAMRole"),
    "aws_iam_policy": ("diagrams.aws.security", "IAM"),
    "aws_iam_role_policy_attachment": ("diagrams.aws.security", "IAM"),
    "aws_kms_key": ("diagrams.aws.security", "KMS"),
    # Serverless
    "aws_lambda_function": ("diagrams.aws.compute", "Lambda"),
    "aws_api_gateway_rest_api": ("diagrams.aws.network", "APIGateway"),
    "aws_apigatewayv2_api": ("diagrams.aws.network", "APIGateway"),
    # Integration
    "aws_sqs_queue": ("diagrams.aws.integration", "SQS"),
    "aws_sns_topic": ("diagrams.aws.integration", "SNS"),
    # Containers
    "aws_ecs_cluster": ("diagrams.aws.compute", "ECS"),
    "aws_ecs_service": ("diagrams.aws.compute", "ECS"),
    "aws_ecs_task_definition": ("diagrams.aws.compute", "ECS"),
    # Monitoring
    "aws_cloudwatch_log_group": ("diagrams.aws.management", "Cloudwatch"),
    "aws_cloudwatch_metric_alarm": ("diagrams.aws.management", "Cloudwatch"),
    "aws_cloudtrail": ("diagrams.aws.management", "Cloudtrail"),
    "aws_flow_log": ("diagrams.aws.network", "VPC"),
}


def get_diagrams_class(resource_type: str) -> Optional[tuple]:
    """Get the diagrams module and class for a resource type."""
    if resource_type in DIAGRAMS_CLASS_MAP:
        return DIAGRAMS_CLASS_MAP[resource_type]
    # Fallback inference
    if "iam" in resource_type:
        return ("diagrams.aws.security", "IAM")
    if "vpc" in resource_type or "subnet" in resource_type:
        return ("diagrams.aws.network", "VPC")
    if "s3" in resource_type:
        return ("diagrams.aws.storage", "S3")
    if "lambda" in resource_type:
        return ("diagrams.aws.compute", "Lambda")
    if "rds" in resource_type or "aurora" in resource_type:
        return ("diagrams.aws.database", "RDS")
    return None


def render_architecture_diagram(topology, output_path: str, fmt: str = "png") -> Optional[str]:
    """Render an InfraTopology as a professional architecture diagram.
    
    Args:
        topology: InfraTopology instance
        output_path: Directory to save the diagram
        fmt: Output format ('png' or 'svg')
        
    Returns:
        Path to the generated diagram file, or None on failure
    """
    try:
        from diagrams import Diagram, Cluster, Edge

        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        diagram_path = str(output_dir / "architecture")

        # Collect unique imports needed
        imports_needed = set()
        for stack in topology.stacks:
            for node in stack.nodes:
                cls_info = get_diagrams_class(node.resource_type)
                if cls_info:
                    imports_needed.add(cls_info)

        # Import all needed classes dynamically
        class_registry = {}
        for module_path, class_name in imports_needed:
            try:
                mod = __import__(module_path, fromlist=[class_name])
                cls = getattr(mod, class_name)
                class_registry[f"{module_path}.{class_name}"] = cls
            except (ImportError, AttributeError) as e:
                logger.debug(f"Could not import {module_path}.{class_name}: {e}")

        # Build diagram
        graph_attr = {
            "fontsize": "12",
            "bgcolor": "white",
            "pad": "0.5",
            "nodesep": "0.6",
            "ranksep": "1.0",
        }

        with Diagram(
            topology.project_name,
            filename=diagram_path,
            outformat=fmt,
            show=False,
            direction="TB",
            graph_attr=graph_attr,
        ):
            node_objects = {}

            for stack in topology.stacks:
                # Create a cluster per stack
                cluster_label = stack.name.replace("/", " / ")

                # Determine cluster color based on changes
                has_changes = any(n.action.value != "no-change" for n in stack.nodes)
                cluster_color = "#1976d2" if has_changes else "#4caf50"
                cluster_bg = "#e3f2fd" if has_changes else "#e8f5e9"

                with Cluster(
                    cluster_label,
                    graph_attr={
                        "bgcolor": cluster_bg,
                        "pencolor": cluster_color,
                        "penwidth": "2",
                        "fontsize": "11",
                        "style": "rounded",
                    },
                ):
                    # Group by category for sub-clusters
                    by_category = {}
                    for node in stack.nodes:
                        cat = node.category.value
                        by_category.setdefault(cat, []).append(node)

                    for category, nodes in by_category.items():
                        for node in nodes:
                            cls_info = get_diagrams_class(node.resource_type)
                            if not cls_info:
                                continue

                            cls_key = f"{cls_info[0]}.{cls_info[1]}"
                            cls = class_registry.get(cls_key)
                            if not cls:
                                continue

                            # Build label
                            short_name = node.name.split("[")[0]
                            action_badge = {
                                "create": " 🆕", "update": " ✏️",
                                "delete": " 🗑️", "replace": " ♻️"
                            }.get(node.action.value, "")
                            label = f"{short_name}{action_badge}"

                            obj = cls(label)
                            node_objects[node.address] = obj

            # Add edges between nodes that exist in the diagram
            seen_edges = set()
            for stack in topology.stacks:
                for edge in stack.edges:
                    src_obj = node_objects.get(edge.source)
                    tgt_obj = node_objects.get(edge.target)
                    if src_obj and tgt_obj and (edge.source, edge.target) not in seen_edges:
                        seen_edges.add((edge.source, edge.target))
                        src_obj >> Edge(color="#42a5f5", style="dashed") >> tgt_obj

        result_path = f"{diagram_path}.{fmt}"
        if os.path.exists(result_path):
            logger.info(f"Architecture diagram generated: {result_path}")
            return result_path
        else:
            logger.error("Diagram file was not created")
            return None

    except ImportError as e:
        logger.error(f"diagrams package not available: {e}. Install: pip install diagrams")
        return None
    except Exception as e:
        logger.error(f"Failed to render architecture diagram: {e}")
        return None
