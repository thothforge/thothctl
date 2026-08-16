"""ECR repository pricing provider."""

import logging
from typing import Any, Dict, List, Optional

from ...models.cost_models import ResourceCost
from ..aws_pricing_client import AWSPricingClient
from ..base_pricing import BasePricingProvider

logger = logging.getLogger(__name__)


class ECRPricingProvider(BasePricingProvider):
    """ECR repository pricing provider"""

    def __init__(self, pricing_client: AWSPricingClient):
        self.pricing_client = pricing_client

        # ECR pricing
        self.private_storage_per_gb = 0.10  # $0.10 per GB/month
        self.public_storage_per_gb = 0.0  # Free for first 50GB

    def get_service_code(self) -> str:
        return "AmazonECR"

    def get_supported_resources(self) -> List[str]:
        return ["aws_ecr_repository"]

    def calculate_cost(
        self, resource_change: Dict[str, Any], region: str
    ) -> Optional[ResourceCost]:
        """Calculate ECR repository cost"""
        return self.get_offline_estimate(resource_change, region)

    def get_offline_estimate(
        self, resource_change: Dict[str, Any], region: str
    ) -> Optional[ResourceCost]:
        """Provide offline estimate for ECR"""
        config = resource_change["change"].get("after", {})
        image_tag_mutability = config.get("image_tag_mutability", "MUTABLE")

        # ECR cost is storage-dependent (not defined in IaC)
        # Moderate estimate: 5GB average storage per repository
        estimated_storage_gb = 5
        monthly_cost = estimated_storage_gb * self.private_storage_per_gb
        hourly_cost = monthly_cost / (24 * 30)

        return self._create_resource_cost(
            resource_change,
            f"Private repo ({image_tag_mutability})",
            region,
            hourly_cost,
            "low",
            note=(
                f"Usage-dependent estimate: {estimated_storage_gb}GB storage "
                f"× ${self.private_storage_per_gb}/GB/month. "
                f"Actual cost depends on image count and size (not defined in IaC)."
            ),
        )

    def _create_resource_cost(
        self,
        resource_change: Dict,
        config_desc: str,
        region: str,
        hourly_cost: float,
        confidence: str,
        note: str = None,
    ) -> ResourceCost:
        """Create ResourceCost object"""
        actions = resource_change["change"]["actions"]
        action = self._safe_action(actions)

        return ResourceCost(
            resource_address=resource_change["address"],
            resource_type="aws_ecr_repository",
            service_name="ECR",
            region=region,
            action=action,
            hourly_cost=hourly_cost,
            monthly_cost=hourly_cost * 24 * 30,
            annual_cost=hourly_cost * 24 * 365,
            pricing_details={
                "config": config_desc,
                "cost_type": "usage-dependent",
                "note": note
                or "Usage-dependent: actual cost depends on stored image size",
            },
            confidence_level=confidence,
        )
