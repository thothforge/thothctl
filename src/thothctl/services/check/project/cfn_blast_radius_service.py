"""CloudFormation/CDK blast radius assessment service.

Supports two modes:
- Static: parses template structure, builds dependency graph from
  DependsOn/!Ref/!GetAtt, detects changes via git diff
- Live: creates AWS change set (read-only), parses exact changes,
  then deletes the change set (no infrastructure changes)
"""
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CfnResource:
    """A CloudFormation resource in the topology."""
    logical_id: str
    resource_type: str
    action: str = "no-change"  # add, modify, remove, no-change
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    scope: List[str] = field(default_factory=list)  # what changed (Properties, Tags, etc.)


@dataclass
class CfnBlastRadiusResult:
    """Result of a CloudFormation blast radius assessment."""
    mode: str  # "static" or "live"
    stack_name: str
    template_path: str
    total_resources: int
    changed_resources: List[CfnResource]
    unchanged_resources: List[CfnResource]
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    blast_radius_percentage: float
    dependency_graph: Dict[str, List[str]]
    recommendations: List[str]


class CfnBlastRadiusService:
    """CloudFormation/CDK blast radius assessment with static and live modes."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # ── Static Mode ─────────────────────────────────────────────────────

    def assess_static(self, template_path: str, directory: str = None) -> CfnBlastRadiusResult:
        """Assess blast radius statically by parsing template and using git diff.

        Args:
            template_path: Path to CloudFormation template (YAML/JSON)
            directory: Project directory for git diff detection

        Returns:
            CfnBlastRadiusResult with static analysis
        """
        self.logger.info(f"Static blast radius assessment: {template_path}")

        # Parse template
        template = self._parse_template(template_path)
        if not template:
            return self._empty_result("static", template_path)

        resources = template.get("Resources", {})
        total = len(resources)

        # Build dependency graph
        dep_graph = self._build_dependency_graph(resources)

        # Detect changes via git diff
        changed_ids = self._detect_changes_git(template_path, directory)

        # Propagate changes through dependency graph
        affected_ids = self._propagate_changes(changed_ids, dep_graph)

        # Build resource lists
        changed_resources = []
        unchanged_resources = []
        for logical_id, config in resources.items():
            deps = dep_graph.get(logical_id, [])
            dependents = [k for k, v in dep_graph.items() if logical_id in v]
            resource = CfnResource(
                logical_id=logical_id,
                resource_type=config.get("Type", "Unknown"),
                action="modify" if logical_id in changed_ids else (
                    "affected" if logical_id in affected_ids else "no-change"
                ),
                dependencies=deps,
                dependents=dependents,
                scope=["Properties"] if logical_id in changed_ids else [],
            )
            if resource.action != "no-change":
                changed_resources.append(resource)
            else:
                unchanged_resources.append(resource)

        # Assess risk
        blast_pct = (len(changed_resources) / total * 100) if total > 0 else 0
        risk_level = self._calculate_risk(blast_pct, changed_resources)
        recommendations = self._generate_recommendations(risk_level, changed_resources, total)

        return CfnBlastRadiusResult(
            mode="static",
            stack_name=Path(template_path).stem,
            template_path=template_path,
            total_resources=total,
            changed_resources=changed_resources,
            unchanged_resources=unchanged_resources,
            risk_level=risk_level,
            blast_radius_percentage=blast_pct,
            dependency_graph=dep_graph,
            recommendations=recommendations,
        )

    # ── Live Mode (AWS Change Set) ──────────────────────────────────────

    def assess_live(
        self,
        template_path: str,
        stack_name: str,
        region: str = "us-east-1",
        profile: str = None,
        parameters: Dict[str, str] = None,
        capabilities: List[str] = None,
    ) -> CfnBlastRadiusResult:
        """Assess blast radius using AWS CloudFormation change set.

        Creates a change set (read-only), parses the changes, then deletes it.
        Requires valid AWS credentials. Supports:
        - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
        - AWS CLI profiles (~/.aws/credentials)
        - IAM instance roles (EC2/ECS)
        - SSO sessions

        Args:
            template_path: Path to CloudFormation template
            stack_name: Name of the existing CloudFormation stack
            region: AWS region
            profile: AWS CLI profile name (uses default credential chain if None)
            parameters: Stack parameters (key: value)
            capabilities: IAM capabilities (e.g., CAPABILITY_IAM)

        Returns:
            CfnBlastRadiusResult with live change set data
        """
        self.logger.info(f"Live blast radius assessment: stack={stack_name}, template={template_path}, profile={profile}")

        try:
            import boto3
        except ImportError:
            self.logger.error("boto3 required for live mode. Install: pip install boto3")
            return self._empty_result("live", template_path, error="boto3 not installed")

        # Parse template for total resource count and dependency graph
        template = self._parse_template(template_path)
        if not template:
            return self._empty_result("live", template_path, error="Failed to parse template")

        resources = template.get("Resources", {})
        total = len(resources)
        dep_graph = self._build_dependency_graph(resources)

        # Create boto3 session respecting standard credential chain + optional profile
        session_kwargs = {}
        if profile:
            session_kwargs["profile_name"] = profile
        if region:
            session_kwargs["region_name"] = region
        session = boto3.Session(**session_kwargs)
        client = session.client("cloudformation")
        change_set_name = f"thothctl-blast-radius-{int(__import__('time').time())}"

        try:
            # Read template body
            template_body = Path(template_path).read_text()

            create_params = {
                "StackName": stack_name,
                "ChangeSetName": change_set_name,
                "TemplateBody": template_body,
                "ChangeSetType": "UPDATE",
            }
            if parameters:
                create_params["Parameters"] = [
                    {"ParameterKey": k, "ParameterValue": v}
                    for k, v in parameters.items()
                ]
            if capabilities:
                create_params["Capabilities"] = capabilities
            else:
                create_params["Capabilities"] = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"]

            self.logger.info(f"Creating change set: {change_set_name}")
            client.create_change_set(**create_params)

            # Wait for change set to be ready
            waiter = client.get_waiter("change_set_create_complete")
            try:
                waiter.wait(
                    StackName=stack_name,
                    ChangeSetName=change_set_name,
                    WaiterConfig={"Delay": 5, "MaxAttempts": 30},
                )
            except Exception as wait_err:
                # Change set may have status FAILED if no changes
                pass

            # Describe change set
            response = client.describe_change_set(
                StackName=stack_name,
                ChangeSetName=change_set_name,
            )

            # Parse changes
            changes = response.get("Changes", [])
            status = response.get("Status", "")
            status_reason = response.get("StatusReason", "")

            # Handle "no changes" case
            if status == "FAILED" and "didn't contain changes" in status_reason.lower():
                self.logger.info("No changes detected in change set")
                result = CfnBlastRadiusResult(
                    mode="live",
                    stack_name=stack_name,
                    template_path=template_path,
                    total_resources=total,
                    changed_resources=[],
                    unchanged_resources=[
                        CfnResource(logical_id=lid, resource_type=cfg.get("Type", ""))
                        for lid, cfg in resources.items()
                    ],
                    risk_level="LOW",
                    blast_radius_percentage=0.0,
                    dependency_graph=dep_graph,
                    recommendations=[
                        "✅ No infrastructure changes detected",
                        f"ℹ️ Stack '{stack_name}' has {total} resources in desired state",
                    ],
                )
            else:
                # Parse actual changes
                changed_resources = []
                changed_ids = set()
                for change in changes:
                    rc = change.get("ResourceChange", {})
                    logical_id = rc.get("LogicalResourceId", "")
                    changed_ids.add(logical_id)
                    action_map = {"Add": "add", "Modify": "modify", "Remove": "remove"}
                    action = action_map.get(rc.get("Action", ""), "modify")
                    scope = [d.get("Target", {}).get("Attribute", "") for d in rc.get("Details", [])]

                    deps = dep_graph.get(logical_id, [])
                    dependents = [k for k, v in dep_graph.items() if logical_id in v]

                    changed_resources.append(CfnResource(
                        logical_id=logical_id,
                        resource_type=rc.get("ResourceType", ""),
                        action=action,
                        dependencies=deps,
                        dependents=dependents,
                        scope=scope or [rc.get("Scope", ["Properties"])[0] if rc.get("Scope") else "Properties"],
                    ))

                # Propagate through deps
                affected_ids = self._propagate_changes(changed_ids, dep_graph)
                for lid in affected_ids - changed_ids:
                    if lid in resources:
                        changed_resources.append(CfnResource(
                            logical_id=lid,
                            resource_type=resources[lid].get("Type", ""),
                            action="affected",
                            dependencies=dep_graph.get(lid, []),
                            dependents=[k for k, v in dep_graph.items() if lid in v],
                        ))

                unchanged_resources = [
                    CfnResource(logical_id=lid, resource_type=cfg.get("Type", ""))
                    for lid, cfg in resources.items()
                    if lid not in changed_ids and lid not in affected_ids
                ]

                blast_pct = (len(changed_resources) / total * 100) if total > 0 else 0
                risk_level = self._calculate_risk(blast_pct, changed_resources)
                recommendations = self._generate_recommendations(risk_level, changed_resources, total)

                result = CfnBlastRadiusResult(
                    mode="live",
                    stack_name=stack_name,
                    template_path=template_path,
                    total_resources=total,
                    changed_resources=changed_resources,
                    unchanged_resources=unchanged_resources,
                    risk_level=risk_level,
                    blast_radius_percentage=blast_pct,
                    dependency_graph=dep_graph,
                    recommendations=recommendations,
                )

        except client.exceptions.ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]
            self.logger.error(f"AWS error: {error_code} - {error_msg}")
            return self._empty_result("live", template_path, error=f"{error_code}: {error_msg}")

        except Exception as e:
            self.logger.error(f"Live blast radius failed: {e}")
            return self._empty_result("live", template_path, error=str(e))

        finally:
            # Always clean up the change set
            try:
                client.delete_change_set(
                    StackName=stack_name,
                    ChangeSetName=change_set_name,
                )
                self.logger.info(f"Deleted change set: {change_set_name}")
            except Exception:
                pass

        return result

    # ── Dependency Graph Builder ────────────────────────────────────────

    def _build_dependency_graph(self, resources: Dict[str, Any]) -> Dict[str, List[str]]:
        """Build dependency graph from CloudFormation template Resources.

        Extracts dependencies from:
        - DependsOn (explicit)
        - !Ref / Ref (implicit)
        - !GetAtt / Fn::GetAtt (implicit)
        - !Sub with ${Resource.Attr} references
        """
        graph: Dict[str, List[str]] = {lid: [] for lid in resources}

        for logical_id, config in resources.items():
            deps: Set[str] = set()

            # Explicit DependsOn
            depends_on = config.get("DependsOn", [])
            if isinstance(depends_on, str):
                depends_on = [depends_on]
            deps.update(depends_on)

            # Implicit from Properties (Ref, GetAtt, Sub)
            properties = config.get("Properties", {})
            self._extract_refs(properties, resources.keys(), deps)

            graph[logical_id] = [d for d in deps if d != logical_id and d in resources]

        return graph

    def _extract_refs(self, obj: Any, valid_ids: set, deps: Set[str]):
        """Recursively extract Ref/GetAtt/Sub references from template properties."""
        if isinstance(obj, dict):
            # !Ref / Ref (both Fn:: form and short form from YAML tags)
            if "Ref" in obj:
                ref = obj["Ref"]
                if ref in valid_ids:
                    deps.add(ref)
            # !GetAtt / Fn::GetAtt / GetAtt (from custom YAML constructor)
            for getatt_key in ("Fn::GetAtt", "GetAtt"):
                if getatt_key in obj:
                    get_att = obj[getatt_key]
                    if isinstance(get_att, list) and len(get_att) >= 1:
                        if get_att[0] in valid_ids:
                            deps.add(get_att[0])
                    elif isinstance(get_att, str) and "." in get_att:
                        ref = get_att.split(".")[0]
                        if ref in valid_ids:
                            deps.add(ref)
            # !Sub / Fn::Sub / Sub — extract ${ResourceId.Attr} patterns
            for sub_key in ("Fn::Sub", "Sub"):
                if sub_key in obj:
                    sub_val = obj[sub_key]
                    sub_str = sub_val if isinstance(sub_val, str) else (sub_val[0] if isinstance(sub_val, list) else "")
                    import re
                    for match in re.findall(r'\$\{([A-Za-z0-9]+)', sub_str):
                        if match in valid_ids:
                            deps.add(match)
            # Recurse into other dict values
            skip_keys = {"Ref", "Fn::GetAtt", "GetAtt", "Fn::Sub", "Sub"}
            for key, val in obj.items():
                if key not in skip_keys:
                    self._extract_refs(val, valid_ids, deps)

        elif isinstance(obj, list):
            for item in obj:
                self._extract_refs(item, valid_ids, deps)

    # ── Git Diff Change Detection ───────────────────────────────────────

    def _detect_changes_git(self, template_path: str, directory: str = None) -> Set[str]:
        """Detect which resources changed by comparing with git HEAD."""
        changed_ids: Set[str] = set()
        work_dir = directory or str(Path(template_path).parent)

        try:
            # Get git diff for the template file
            result = subprocess.run(
                ["git", "diff", "HEAD", "--", template_path],
                capture_output=True, text=True, timeout=10, cwd=work_dir,
            )
            if result.returncode != 0 or not result.stdout.strip():
                # No git or no changes — try diff against last commit
                result = subprocess.run(
                    ["git", "diff", "HEAD~1", "HEAD", "--", template_path],
                    capture_output=True, text=True, timeout=10, cwd=work_dir,
                )

            if result.stdout:
                # Parse diff to find changed resource logical IDs
                changed_ids = self._parse_diff_for_resources(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.logger.debug("Git not available for change detection")

        # If no git changes detected, mark all as potentially changed (conservative)
        if not changed_ids:
            template = self._parse_template(template_path)
            if template:
                # Return all resources — static mode without git is "full blast"
                changed_ids = set(template.get("Resources", {}).keys())

        return changed_ids

    def _parse_diff_for_resources(self, diff_output: str) -> Set[str]:
        """Parse git diff to identify which logical resource IDs were modified."""
        import re
        changed_ids: Set[str] = set()

        # Look for resource logical IDs in added/modified lines
        # Pattern: lines starting with + that contain a logical ID followed by a colon
        # In YAML: "  MyResource:" at indent level 1 under Resources
        in_resources = False
        for line in diff_output.split("\n"):
            if "+Resources:" in line or " Resources:" in line:
                in_resources = True
                continue
            if in_resources and line.startswith("+") and not line.startswith("+++"):
                # Match top-level resource IDs (2-space indent under Resources)
                match = re.match(r'\+\s{2}([A-Za-z][A-Za-z0-9]*):', line)
                if match:
                    changed_ids.add(match.group(1))
                # Also match property changes under a resource
                match = re.match(r'\+\s{4,}(\w+):', line)
                if match and not line.strip().startswith("#"):
                    pass  # property changed, need context

        # Also look for JSON-style changes
        for match in re.finditer(r'"([A-Za-z][A-Za-z0-9]+)":\s*\{[^}]*"Type":\s*"AWS::', diff_output):
            changed_ids.add(match.group(1))

        return changed_ids

    # ── Risk Calculation ────────────────────────────────────────────────

    def _calculate_risk(self, blast_pct: float, changed: List[CfnResource]) -> str:
        """Calculate risk level from blast radius percentage and resource types."""
        # Critical resource types that increase risk
        critical_types = {
            "AWS::EC2::VPC", "AWS::RDS::DBInstance", "AWS::RDS::DBCluster",
            "AWS::EKS::Cluster", "AWS::IAM::Role", "AWS::KMS::Key",
            "AWS::Route53::HostedZone", "AWS::CloudTrail::Trail",
        }
        has_critical = any(r.resource_type in critical_types for r in changed)
        has_removes = any(r.action == "remove" for r in changed)

        if blast_pct > 60 or (has_critical and has_removes):
            return "CRITICAL"
        if blast_pct > 40 or has_removes:
            return "HIGH"
        if blast_pct > 20 or has_critical:
            return "MEDIUM"
        return "LOW"

    def _generate_recommendations(self, risk: str, changed: List[CfnResource], total: int) -> List[str]:
        """Generate ITIL-aligned recommendations."""
        recs = []
        change_count = len(changed)
        if total > 0:
            recs.append(f"📊 Change scope: {change_count}/{total} resources ({change_count/total*100:.1f}% blast radius)")

        if risk == "CRITICAL":
            recs.extend([
                "🚨 CRITICAL: Require Change Advisory Board (CAB) approval",
                "🚨 Schedule during maintenance window",
                "🚨 Prepare rollback plan (previous template version in S3/Git)",
            ])
        elif risk == "HIGH":
            recs.extend([
                "⚠️ HIGH: Require senior approval before deployment",
                "⚠️ Deploy to staging first",
                "⚠️ Monitor CloudWatch alarms closely after deploy",
            ])
        elif risk == "MEDIUM":
            recs.extend([
                "📋 MEDIUM: Standard change process applies",
                "📋 Verify in staging environment first",
            ])
        else:
            recs.append("✅ LOW: Standard deployment approved")

        # Specific recommendations based on resource types
        removes = [r for r in changed if r.action == "remove"]
        if removes:
            recs.append(f"🗑️ {len(removes)} resource(s) will be DELETED — verify data retention")

        return recs

    # ── Helpers ─────────────────────────────────────────────────────────

    def _parse_template(self, template_path: str) -> Optional[Dict]:
        """Parse a CloudFormation template (YAML or JSON).
        
        Handles CloudFormation intrinsic functions (!Ref, !GetAtt, !Sub, etc.)
        by using a custom YAML loader.
        """
        try:
            content = Path(template_path).read_text()
            if template_path.endswith(".json"):
                return json.loads(content)
            else:
                # Custom loader that handles CFN intrinsic functions
                loader = yaml.SafeLoader
                # Add constructors for all CFN intrinsic functions
                cfn_tags = [
                    "!Ref", "!GetAtt", "!Sub", "!Join", "!Select", "!Split",
                    "!If", "!Equals", "!Not", "!And", "!Or", "!Condition",
                    "!Base64", "!Cidr", "!FindInMap", "!GetAZs",
                    "!ImportValue", "!Transform",
                ]
                for tag in cfn_tags:
                    loader.add_constructor(
                        tag,
                        lambda loader, node: self._cfn_tag_constructor(loader, node, tag),
                    )
                # Multi-constructor for any remaining !Tag
                loader.add_multi_constructor(
                    "!",
                    lambda loader, suffix, node: self._cfn_tag_constructor(loader, node, f"!{suffix}"),
                )
                return yaml.load(content, Loader=loader)
        except Exception as e:
            self.logger.error(f"Failed to parse template {template_path}: {e}")
            return None

    @staticmethod
    def _cfn_tag_constructor(loader, node, tag):
        """Convert CFN YAML tags into dict representation for graph analysis."""
        tag_name = tag.lstrip("!")
        if isinstance(node, yaml.ScalarNode):
            value = loader.construct_scalar(node)
            return {tag_name: value}
        elif isinstance(node, yaml.SequenceNode):
            value = loader.construct_sequence(node)
            return {tag_name: value}
        elif isinstance(node, yaml.MappingNode):
            value = loader.construct_mapping(node)
            return {tag_name: value}
        return {tag_name: None}

    def _propagate_changes(self, changed_ids: Set[str], dep_graph: Dict[str, List[str]]) -> Set[str]:
        """Propagate changes through the dependency graph (BFS)."""
        affected = set(changed_ids)
        queue = list(changed_ids)

        while queue:
            current = queue.pop(0)
            # Find resources that depend on the current one
            for resource_id, deps in dep_graph.items():
                if current in deps and resource_id not in affected:
                    affected.add(resource_id)
                    queue.append(resource_id)

        return affected

    def _empty_result(self, mode: str, template_path: str, error: str = None) -> CfnBlastRadiusResult:
        """Return an empty result for error cases."""
        return CfnBlastRadiusResult(
            mode=mode,
            stack_name=Path(template_path).stem,
            template_path=template_path,
            total_resources=0,
            changed_resources=[],
            unchanged_resources=[],
            risk_level="LOW",
            blast_radius_percentage=0.0,
            dependency_graph={},
            recommendations=[f"⚠️ Assessment failed: {error}"] if error else [],
        )


def result_to_dict(result: CfnBlastRadiusResult) -> Dict[str, Any]:
    """Convert CfnBlastRadiusResult to JSON-serializable dict."""
    return {
        "mode": result.mode,
        "stack_name": result.stack_name,
        "template_path": result.template_path,
        "total_resources": result.total_resources,
        "risk_level": result.risk_level,
        "blast_radius_percentage": round(result.blast_radius_percentage, 1),
        "changed_resources": [
            {
                "logical_id": r.logical_id,
                "resource_type": r.resource_type,
                "action": r.action,
                "scope": r.scope,
                "dependencies": r.dependencies,
                "dependents": r.dependents,
            }
            for r in result.changed_resources
        ],
        "dependency_graph": result.dependency_graph,
        "recommendations": result.recommendations,
    }
