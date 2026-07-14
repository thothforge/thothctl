"""CloudFormation/CDK drift detection service.

Uses AWS CloudFormation APIs:
  - detect-stack-drift (triggers detection)
  - describe-stack-drift-detection-status (polls completion)
  - describe-stack-resource-drifts (gets drifted resources)

Also supports static detection via template diff for offline/pre-deploy use.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import (
    DriftedResource,
    DriftResult,
    DriftSeverity,
    DriftSummary,
    DriftType,
)

logger = logging.getLogger(__name__)

# CFN resource types severity classification
_CRITICAL_CFN_TYPES = {
    "AWS::RDS::DBInstance", "AWS::RDS::DBCluster", "AWS::DynamoDB::Table",
    "AWS::S3::Bucket", "AWS::KMS::Key", "AWS::SecretsManager::Secret",
    "AWS::ElastiCache::CacheCluster", "AWS::Redshift::Cluster",
    "AWS::EFS::FileSystem", "AWS::RDS::GlobalCluster",
}

_HIGH_CFN_TYPES = {
    "AWS::EKS::Cluster", "AWS::ECS::Cluster", "AWS::Lambda::Function",
    "AWS::IAM::Role", "AWS::IAM::Policy", "AWS::IAM::ManagedPolicy",
    "AWS::EC2::VPC", "AWS::EC2::Subnet", "AWS::EC2::SecurityGroup",
    "AWS::ElasticLoadBalancingV2::LoadBalancer",
    "AWS::AutoScaling::AutoScalingGroup", "AWS::EC2::Instance",
    "AWS::CloudFront::Distribution", "AWS::Route53::HostedZone",
}


class CfnDriftDetectionService:
    """Detect drift for CloudFormation/CDK stacks."""

    def __init__(self, region: str = None, profile: str = None):
        self.region = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self.profile = profile
        self._client = None

    @property
    def client(self):
        """Lazy-init boto3 CloudFormation client."""
        if self._client is None:
            import boto3
            session_kwargs = {}
            if self.profile:
                session_kwargs["profile_name"] = self.profile
            if self.region:
                session_kwargs["region_name"] = self.region
            session = boto3.Session(**session_kwargs)
            self._client = session.client("cloudformation")
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_drift_live(self, stack_name: str) -> DriftResult:
        """Trigger drift detection on a live CloudFormation stack.

        This calls AWS APIs:
          1. detect_stack_drift() - initiates detection
          2. Poll describe_stack_drift_detection_status() until complete
          3. describe_stack_resource_drifts() - get detailed results
        """
        try:
            # Trigger drift detection
            response = self.client.detect_stack_drift(StackName=stack_name)
            detection_id = response["StackDriftDetectionId"]
            logger.info(f"Drift detection started for {stack_name}: {detection_id}")

            # Poll until complete (max 5 minutes)
            status = self._poll_detection(detection_id, timeout=300)

            if status.get("DetectionStatus") == "DETECTION_FAILED":
                return DriftResult(
                    directory=stack_name,
                    error=f"Drift detection failed: {status.get('DetectionStatusReason', 'Unknown')}"
                )

            # Get detailed drift results
            drift_status = status.get("StackDriftStatus", "NOT_CHECKED")
            if drift_status == "IN_SYNC":
                return DriftResult(
                    directory=stack_name,
                    total_resources=status.get("DriftedStackResourceCount", 0)
                    + self._get_stack_resource_count(stack_name),
                )

            # DRIFTED — get resource-level details
            return self._get_resource_drifts(stack_name, status)

        except ImportError:
            return DriftResult(directory=stack_name, error="boto3 not installed. Run: pip install boto3")
        except Exception as e:
            logger.error(f"CFN drift detection failed for {stack_name}: {e}")
            return DriftResult(directory=stack_name, error=str(e))

    def detect_drift_static(self, template_path: str, stack_name: str = None) -> DriftResult:
        """Detect drift by comparing deployed stack with local template (no mutation).

        Uses describe_stack_resources to compare deployed state against the local template.
        Does NOT trigger detect-stack-drift (non-mutating).
        """
        actual_stack_name = stack_name or Path(template_path).stem

        try:
            # Parse local template
            template = self._parse_template(template_path)
            if not template:
                return DriftResult(directory=template_path, error=f"Cannot parse template: {template_path}")

            local_resources = template.get("Resources", {})

            # Get deployed resources
            deployed = self._get_deployed_resources(actual_stack_name)
            if deployed is None:
                return DriftResult(
                    directory=template_path,
                    error=f"Stack '{actual_stack_name}' not found or not accessible. "
                    f"Use --stack-name to specify the deployed stack name.",
                )

            # Compare
            return self._compare_template_vs_deployed(
                template_path, local_resources, deployed, actual_stack_name
            )

        except ImportError:
            return DriftResult(directory=template_path, error="boto3 not installed. Run: pip install boto3")
        except Exception as e:
            logger.error(f"Static CFN drift detection failed: {e}")
            return DriftResult(directory=template_path, error=str(e))

    def detect_drift(
        self,
        directory: str,
        recursive: bool = False,
        stack_names: Optional[List[str]] = None,
        live: bool = True,
        filter_tags: Optional[Dict[str, str]] = None,
    ) -> DriftSummary:
        """High-level entry point for CloudFormation/CDK drift detection.

        Args:
            directory: Project directory containing templates
            recursive: Walk subdirectories for templates
            stack_names: Explicit stack names to check (live mode)
            live: If True, use AWS API (detect_stack_drift). If False, template-only comparison.
            filter_tags: Filter resources by tags
        """
        from ...scan.scan_service import ScanService

        summary = DriftSummary()
        scan_svc = ScanService()

        if stack_names and live:
            # Live detection for explicit stacks
            for name in stack_names:
                summary.results.append(self.detect_drift_live(name))
        elif live:
            # Auto-discover stacks from templates and detect live
            stacks = self._discover_stacks(directory, recursive, scan_svc)
            if not stacks:
                summary.results.append(DriftResult(
                    directory=directory,
                    error="No deployed CloudFormation stacks found. Use --stack-name to specify.",
                ))
            for stack_name in stacks:
                summary.results.append(self.detect_drift_live(stack_name))
        else:
            # Static mode — compare templates against deployed state
            templates = self._find_templates(directory, recursive, scan_svc)
            for tpl in templates:
                summary.results.append(self.detect_drift_static(tpl))

        if filter_tags:
            self._apply_tag_filter(summary, filter_tags)

        return summary

    # ------------------------------------------------------------------
    # AWS API helpers
    # ------------------------------------------------------------------

    def _poll_detection(self, detection_id: str, timeout: int = 300) -> Dict:
        """Poll drift detection status until complete."""
        start = time.time()
        while time.time() - start < timeout:
            response = self.client.describe_stack_drift_detection_status(
                StackDriftDetectionId=detection_id
            )
            status = response.get("DetectionStatus")
            if status in ("DETECTION_COMPLETE", "DETECTION_FAILED"):
                return response
            time.sleep(5)

        return {"DetectionStatus": "DETECTION_FAILED", "DetectionStatusReason": "Timeout"}

    def _get_resource_drifts(self, stack_name: str, detection_status: Dict) -> DriftResult:
        """Get per-resource drift details after detection completes."""
        drifted: List[DriftedResource] = []
        total = 0

        paginator = self.client.get_paginator("describe_stack_resource_drifts")
        pages = paginator.paginate(
            StackName=stack_name,
            StackResourceDriftStatusFilters=["MODIFIED", "DELETED", "NOT_CHECKED"],
        )

        for page in pages:
            for drift in page.get("StackResourceDrifts", []):
                total += 1
                status = drift.get("StackResourceDriftStatus")

                if status == "IN_SYNC":
                    continue

                resource_type = drift.get("ResourceType", "")
                logical_id = drift.get("LogicalResourceId", "")
                physical_id = drift.get("PhysicalResourceId", "")

                # Classify
                drift_type = self._cfn_status_to_drift_type(status)
                severity = self._assess_cfn_severity(resource_type, drift_type)
                changed_attrs = self._extract_cfn_property_diffs(drift)

                address = f"{logical_id} ({physical_id})" if physical_id else logical_id

                drifted.append(DriftedResource(
                    address=address,
                    resource_type=resource_type,
                    drift_type=drift_type,
                    severity=severity,
                    changed_attributes=changed_attrs,
                    actions=[status.lower()],
                    detail=f"CloudFormation drift status: {status}",
                    tags=self._get_resource_tags(stack_name, logical_id),
                ))

        # Add in-sync resources to total count
        in_sync_count = detection_status.get("DriftedStackResourceCount", 0)
        total_managed = self._get_stack_resource_count(stack_name)
        total = max(total, total_managed)

        coverage = round(((total - len(drifted)) / total) * 100, 1) if total else 100.0

        return DriftResult(
            directory=stack_name,
            total_resources=total,
            drifted_resources=drifted,
            coverage_pct=coverage,
        )

    def _get_stack_resource_count(self, stack_name: str) -> int:
        """Get total resource count in a stack."""
        try:
            response = self.client.list_stack_resources(StackName=stack_name)
            return len(response.get("StackResourceSummaries", []))
        except Exception:
            return 0

    def _get_deployed_resources(self, stack_name: str) -> Optional[Dict]:
        """Get deployed resources from a stack. Returns None if stack doesn't exist."""
        try:
            response = self.client.describe_stack_resources(StackName=stack_name)
            resources = {}
            for r in response.get("StackResources", []):
                resources[r["LogicalResourceId"]] = {
                    "type": r["ResourceType"],
                    "status": r["ResourceStatus"],
                    "physical_id": r.get("PhysicalResourceId"),
                }
            return resources
        except self.client.exceptions.ClientError as e:
            if "does not exist" in str(e):
                return None
            raise

    def _get_resource_tags(self, stack_name: str, logical_id: str) -> Dict[str, str]:
        """Try to get tags for a specific resource."""
        try:
            response = self.client.describe_stack_resource(
                StackName=stack_name, LogicalResourceId=logical_id
            )
            detail = response.get("StackResourceDetail", {})
            # Tags aren't directly on this API — return empty
            return {}
        except Exception:
            return {}

    def _discover_stacks(self, directory: str, recursive: bool, scan_svc) -> List[str]:
        """Discover deployed CFN stack names from the project directory.

        Looks for:
        - samconfig.toml (SAM apps)
        - cdk.json (CDK apps — reads from cdk.out)
        - Stack names matching template file names
        """
        stacks = []

        # Try samconfig.toml
        sam_config = Path(directory) / "samconfig.toml"
        if sam_config.exists():
            try:
                import toml
                config = toml.load(sam_config)
                # Extract stack_name from default deploy parameters
                for env in config.values():
                    if isinstance(env, dict):
                        deploy = env.get("deploy", {}).get("parameters", {})
                        name = deploy.get("stack_name")
                        if name:
                            stacks.append(name)
            except Exception as e:
                logger.debug(f"Failed to parse samconfig.toml: {e}")

        # Try listing active stacks matching template names
        if not stacks:
            templates = self._find_templates(directory, recursive, scan_svc)
            for tpl in templates:
                stem = Path(tpl).stem
                # Common naming: template name = stack name
                if self._stack_exists(stem):
                    stacks.append(stem)

        return stacks

    def _stack_exists(self, stack_name: str) -> bool:
        """Check if a CloudFormation stack exists and is in a usable state."""
        try:
            response = self.client.describe_stacks(StackName=stack_name)
            stack = response["Stacks"][0]
            status = stack.get("StackStatus", "")
            return "DELETE_COMPLETE" not in status
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Static comparison
    # ------------------------------------------------------------------

    def _compare_template_vs_deployed(
        self, template_path: str, local_resources: Dict, deployed: Dict, stack_name: str
    ) -> DriftResult:
        """Compare local template resources against deployed stack."""
        drifted: List[DriftedResource] = []
        all_ids = set(list(local_resources.keys()) + list(deployed.keys()))
        total = len(all_ids)

        for logical_id in all_ids:
            in_local = logical_id in local_resources
            in_deployed = logical_id in deployed

            if in_local and not in_deployed:
                # Resource in template but not deployed — it was deleted
                rtype = local_resources[logical_id].get("Type", "Unknown")
                drifted.append(DriftedResource(
                    address=logical_id,
                    resource_type=rtype,
                    drift_type=DriftType.DELETED,
                    severity=self._assess_cfn_severity(rtype, DriftType.DELETED),
                    actions=["deleted"],
                    detail="Resource defined in template but not found in deployed stack",
                ))
            elif in_deployed and not in_local:
                # Resource deployed but not in template — unmanaged
                rtype = deployed[logical_id].get("type", "Unknown")
                drifted.append(DriftedResource(
                    address=logical_id,
                    resource_type=rtype,
                    drift_type=DriftType.UNMANAGED,
                    severity=self._assess_cfn_severity(rtype, DriftType.UNMANAGED),
                    actions=["unmanaged"],
                    detail="Resource exists in stack but not in local template",
                ))
            # For in_local AND in_deployed — we can't compare properties without calling describe
            # The live mode handles property-level drift

        coverage = round(((total - len(drifted)) / total) * 100, 1) if total else 100.0

        return DriftResult(
            directory=template_path,
            total_resources=total,
            drifted_resources=drifted,
            coverage_pct=coverage,
        )

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cfn_status_to_drift_type(status: str) -> DriftType:
        if status == "MODIFIED":
            return DriftType.CHANGED
        elif status == "DELETED":
            return DriftType.DELETED
        else:
            return DriftType.CHANGED

    @staticmethod
    def _assess_cfn_severity(resource_type: str, drift_type: DriftType) -> DriftSeverity:
        if resource_type in _CRITICAL_CFN_TYPES:
            return DriftSeverity.CRITICAL if drift_type == DriftType.DELETED else DriftSeverity.HIGH
        if resource_type in _HIGH_CFN_TYPES:
            return DriftSeverity.HIGH if drift_type == DriftType.DELETED else DriftSeverity.MEDIUM
        if drift_type == DriftType.DELETED:
            return DriftSeverity.MEDIUM
        return DriftSeverity.LOW

    @staticmethod
    def _extract_cfn_property_diffs(drift_detail: Dict) -> List[str]:
        """Extract changed property names from CFN property differences."""
        diffs = drift_detail.get("PropertyDifferences", [])
        return [d.get("PropertyPath", "unknown") for d in diffs]

    # ------------------------------------------------------------------
    # Template/file utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_template(path: str) -> Optional[Dict]:
        """Parse a CloudFormation YAML or JSON template."""
        try:
            import yaml
            content = Path(path).read_text()
            if path.endswith(".json"):
                return json.loads(content)
            return yaml.safe_load(content)
        except Exception as e:
            logger.error(f"Failed to parse template {path}: {e}")
            return None

    @staticmethod
    def _find_templates(directory: str, recursive: bool, scan_svc) -> List[str]:
        """Find CloudFormation/CDK templates in directory."""
        templates = []

        # CDK templates in cdk.out/
        cdk_out = Path(directory) / "cdk.out"
        if cdk_out.exists():
            for f in cdk_out.glob("*.template.json"):
                templates.append(str(f))

        # CloudFormation templates
        try:
            cfn_templates = scan_svc._find_cloudformation_templates(directory)
            templates.extend(cfn_templates)
        except Exception:
            pass

        return templates

    @staticmethod
    def _apply_tag_filter(summary: DriftSummary, filter_tags: Dict[str, str]) -> None:
        """Filter drifted resources by tags."""
        for result in summary.results:
            result.drifted_resources = [
                r for r in result.drifted_resources
                if _matches_tags(r.tags, filter_tags)
            ]


def _matches_tags(resource_tags: Dict, filter_tags: Dict) -> bool:
    """Return True if resource_tags contain ALL filter_tags."""
    if not filter_tags:
        return True
    if not resource_tags:
        return False
    for key, value in filter_tags.items():
        if key not in resource_tags:
            return False
        if value not in ("*", "") and resource_tags[key] != value:
            return False
    return True
