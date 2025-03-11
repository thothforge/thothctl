"""Module for checking and comparing versions of Terraform modules."""
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import aiohttp
from aiohttp import ClientTimeout
from colorama import Fore


logger = logging.getLogger(__name__)


class RegistryType(Enum):
    """Registry types for module sources."""

    TERRAFORM = "terraform"
    GITHUB = "github"
    UNKNOWN = "unknown"


@dataclass
class VersionInfo:
    """Version information for a module."""

    version: str
    source_url: str
    status: str = "Unknown"


class VersionChecker:
    """Handles version checking and comparison for Terraform modules."""

    REGISTRY_URLS = {
        RegistryType.TERRAFORM: "https://registry.terraform.io/v1/modules",
        RegistryType.GITHUB: "https://api.github.com/repos",
    }

    def __init__(self, timeout: int = 30):
        """Initialize version checker with configurable timeout."""
        self.timeout = ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Set up async context."""
        self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up async context."""
        if self._session:
            await self._session.close()

    async def get_public_version(self, resource: str) -> Tuple[str, str]:
        """
        Get public version information for a module.

        Args:
            resource: Module resource identifier

        Returns:
            Tuple of (version, source_url)
        """
        try:
            print(f"{Fore.MAGENTA} Getting version for {resource}{Fore.RESET}")
            clean_resource = self._clean_resource_path(resource)
            source_url = await self._build_source_url(clean_resource)

            if "github" in source_url:
                # TODO: Implement GitHub API version checking
                return "Null", source_url

            version = await self._fetch_version(source_url)
            return version, source_url

        except Exception as e:
            logger.error(f"Failed to get public version for {resource}: {str(e)}")
            return "Null", "Error"

    @staticmethod
    def _clean_resource_path(resource: str) -> str:
        """Clean resource path by removing protocol prefix."""
        return resource.split("//")[0] if "//" in resource else resource

    def _determine_registry_type(self, source: str) -> RegistryType:
        """Determine registry type from source URL."""
        if "github.com" in source:
            return RegistryType.GITHUB
        elif "terraform-aws-modules" in source:
            return RegistryType.TERRAFORM
        return RegistryType.UNKNOWN

    async def _build_source_url(self, resource: str) -> str:
        """Build appropriate registry URL for the resource."""
        registry_type = self._determine_registry_type(resource)
        base_url = self.REGISTRY_URLS.get(
            registry_type, self.REGISTRY_URLS[RegistryType.TERRAFORM]
        )
        return f"{base_url}/{resource}"

    async def _fetch_version(self, url: str) -> str:
        """Fetch version information from registry."""
        try:
            if not self._session:
                raise RuntimeError("HTTP session not initialized")

            async with self._session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("version", "Null")

        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed for {url}: {str(e)}")
            return "Null"
        except Exception as e:
            logger.error(f"Failed to fetch version from {url}: {str(e)}")
            return "Null"

    def check_version_status(
        self, latest_version: str, local_version: str, resource: str, resource_name: str
    ) -> str:
        """
        Compare versions and determine status.

        Args:
            latest_version: Latest available version
            local_version: Current local version
            resource: Resource identifier
            resource_name: Name of the resource

        Returns:
            Status string ("Updated" or "Outdated")
        """
        try:
            if not latest_version or latest_version == "Null":
                return "Unknown"

            is_updated = latest_version in local_version
            status = "Updated" if is_updated else "Outdated"

            color = Fore.GREEN if is_updated else Fore.RED
            print(
                f"{Fore.MAGENTA}The resource {resource_name} is {color}{status}{Fore.MAGENTA}, "
                f"latest_version {latest_version} vs local_version {local_version} for {resource}"
            )

            return status

        except Exception as e:
            logger.error(f"Version comparison failed: {str(e)}")
            return "Error"


class InventoryVersionManager:
    """Manages version checking for entire inventory."""

    def __init__(self):
        """Initialize inventory version manager."""
        self.version_checker = VersionChecker()

    @staticmethod
    def get_component_version(component: Dict[str, Any]) -> Dict[str, Any]:
        """Extract version information from component."""
        try:
            version = component.get("version", "None")
            if version == "Null" and "source" in component:
                resource = component["source"][0]
                if "ref=" in resource:
                    version = [resource.split("ref=")[1]]
                    component["version"] = version
                    logger.info(f"Extracted version {version} from ref")
            return {"version": version}
        except Exception as e:
            logger.error(f"Failed to get component version: {str(e)}")
            return {"version": "Error"}

    async def check_versions(self, inventory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check versions for all components in inventory.

        Args:
            inventory: Inventory dictionary

        Returns:
            Updated inventory with version information
        """
        try:
            inventory["version"] = 2

            async with self.version_checker as checker:
                for components in inventory.get("components", []):
                    for component in components.get("components", []):
                        await self._process_component(checker, component)

            return inventory

        except Exception as e:
            logger.error(f"Failed to check versions: {str(e)}")
            return inventory

    async def _process_component(
        self, checker: VersionChecker, component: Dict[str, Any]
    ) -> None:
        """Process individual component version checking."""
        try:
            local_version = self.get_component_version(component)["version"]
            logger.debug(f"Processing component: {component}")

            if not isinstance(local_version, list):
                self._set_null_values(component)
                return

            resource = component.get("source", [None])[0]
            if not resource:
                self._set_null_values(component)
                return

            version, source_url = await checker.get_public_version(resource)

            component.update(
                {
                    "latest_version": version,
                    "source_url": source_url,
                    "status": checker.check_version_status(
                        latest_version=version,
                        local_version=local_version[0],
                        resource=resource,
                        resource_name=component.get("name", "unknown"),
                    ),
                }
            )

        except Exception as e:
            logger.error(f"Component processing failed: {str(e)}")
            self._set_null_values(component)

    @staticmethod
    def _set_null_values(component: Dict[str, Any]) -> None:
        """Set null values for component fields."""
        component.update(
            {"latest_version": "Null", "source_url": "Null", "status": "Null"}
        )


# Usage example
async def main():
    inventory = {
        "version": 2,
        "projectName": "terraform_aws_eks_pattern",
        "components": [
            {
                "path": "./resources/databases/elasticache_redis",
                "components": [
                    {
                        "type": "module",
                        "name": "secrets_manager_default",
                        "version": ["1.1.2"],
                        "source": ["terraform-aws-modules/secrets-manager/aws"],
                        "file": "./resources/databases/elasticache_redis/main.tf",
                        "latest_version": "1.3.1",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/secrets-manager/aws",
                        "status": "Outdated",
                    },
                    {
                        "type": "module",
                        "name": "secrets_manager_buc",
                        "version": ["1.1.2"],
                        "source": ["terraform-aws-modules/secrets-manager/aws"],
                        "file": "./resources/databases/elasticache_redis/main.tf",
                        "latest_version": "1.3.1",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/secrets-manager/aws",
                        "status": "Outdated",
                    },
                    {
                        "type": "module",
                        "name": "elasticache_user_group",
                        "version": ["1.2.0"],
                        "source": [
                            "terraform-aws-modules/elasticache/aws//modules/user-group"
                        ],
                        "file": "./resources/databases/elasticache_redis/main.tf",
                        "latest_version": "1.4.1",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/elasticache/aws",
                        "status": "Outdated",
                    },
                    {
                        "type": "module",
                        "name": "elasticache",
                        "version": ["1.2.0"],
                        "source": ["terraform-aws-modules/elasticache/aws"],
                        "file": "./resources/databases/elasticache_redis/main.tf",
                        "latest_version": "1.4.1",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/elasticache/aws",
                        "status": "Outdated",
                    },
                ],
            },
            {
                "path": "./resources/operations",
                "components": [
                    {
                        "type": "module",
                        "name": "project_resources",
                        "version": "Null",
                        "source": ["../../modules/terraform-aws-resource-groups"],
                        "file": "./resources/operations/main.tf",
                        "latest_version": "Null",
                        "source_url": "Null",
                        "status": "Null",
                    }
                ],
            },
            {
                "path": "./resources/security/cognito",
                "components": [
                    {
                        "type": "module",
                        "name": "cognito",
                        "version": "Null",
                        "source": ["../../../modules/terraform-aws-cognito-user-pool"],
                        "file": "./resources/security/cognito/main.tf",
                        "latest_version": "Null",
                        "source_url": "Null",
                        "status": "Null",
                    }
                ],
            },
            {
                "path": "./resources/security/kms/infrastructure",
                "components": [
                    {
                        "type": "module",
                        "name": "kms",
                        "version": ["3.0.0"],
                        "source": ["terraform-aws-modules/kms/aws"],
                        "file": "./resources/security/kms/infrastructure/main.tf",
                        "latest_version": "3.1.1",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/kms/aws",
                        "status": "Outdated",
                    },
                    {
                        "type": "module",
                        "name": "parameter_store",
                        "version": ["0.13.0"],
                        "source": ["cloudposse/ssm-parameter-store/aws"],
                        "file": "./resources/security/kms/infrastructure/main.tf",
                        "latest_version": "0.13.0",
                        "source_url": "https://registry.terraform.io/v1/modules/cloudposse/ssm-parameter-store/aws",
                        "status": "Updated",
                    },
                ],
            },
            {
                "path": "./resources/security/secretsmanager/custom_app_secrets",
                "components": [
                    {
                        "type": "module",
                        "name": "secrets_manager_buc",
                        "version": ["1.1.2"],
                        "source": ["terraform-aws-modules/secrets-manager/aws"],
                        "file": "./resources/security/secretsmanager/custom_app_secrets/main.tf",
                        "latest_version": "1.3.1",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/secrets-manager/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/security/iam/instance_profile/ec2_bastion",
                "components": [
                    {
                        "type": "module",
                        "name": "asg_instance_profile",
                        "version": "Null",
                        "source": ["../../../../../modules/aws-ec2-instance-profile"],
                        "file": "./resources/security/iam/instance_profile/ec2_bastion/main.tf",
                        "latest_version": "Null",
                        "source_url": "Null",
                        "status": "Null",
                    }
                ],
            },
            {
                "path": "./resources/security/iam/iam_service_accounts",
                "components": [
                    {
                        "type": "module",
                        "name": "iam_eks_role",
                        "version": ["5.39.1"],
                        "source": [
                            "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
                        ],
                        "file": "./resources/security/iam/iam_service_accounts/main.tf",
                        "latest_version": "5.52.2",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/iam/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/security/iam/policies/iam_service_account_policies",
                "components": [
                    {
                        "type": "module",
                        "name": "iam_policy",
                        "version": ["5.39.1"],
                        "source": ["terraform-aws-modules/iam/aws//modules/iam-policy"],
                        "file": "./resources/security/iam/policies/iam_service_account_policies/main.tf",
                        "latest_version": "5.52.2",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/iam/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/compute/ec2/ec2_bastion",
                "components": [
                    {
                        "type": "module",
                        "name": "ec2",
                        "version": ["5.6.1"],
                        "source": ["terraform-aws-modules/ec2-instance/aws"],
                        "file": "./resources/compute/ec2/ec2_bastion/main.tf",
                        "latest_version": "5.7.1",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/ec2-instance/aws",
                        "status": "Outdated",
                    },
                    {
                        "type": "module",
                        "name": "scheduler_ops",
                        "version": "Null",
                        "source": [
                            "../../../../modules/aws-automations/instance_strat_stop"
                        ],
                        "file": "./resources/compute/ec2/ec2_bastion/main.tf",
                        "latest_version": "Null",
                        "source_url": "Null",
                        "status": "Null",
                    },
                ],
            },
            {
                "path": "./resources/compute/key_pairs",
                "components": [
                    {
                        "type": "module",
                        "name": "key_pair",
                        "version": ["2.0.3"],
                        "source": ["terraform-aws-modules/key-pair/aws"],
                        "file": "./resources/compute/key_pairs/main.tf",
                        "latest_version": "2.0.3",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/key-pair/aws",
                        "status": "Updated",
                    },
                    {
                        "type": "module",
                        "name": "parameter_store",
                        "version": ["0.13.0"],
                        "source": ["cloudposse/ssm-parameter-store/aws"],
                        "file": "./resources/compute/key_pairs/main.tf",
                        "latest_version": "0.13.0",
                        "source_url": "https://registry.terraform.io/v1/modules/cloudposse/ssm-parameter-store/aws",
                        "status": "Updated",
                    },
                ],
            },
            {
                "path": "./resources/containers/eks_cluster",
                "components": [
                    {
                        "type": "module",
                        "name": "eks",
                        "version": ["20.12.0"],
                        "source": ["terraform-aws-modules/eks/aws"],
                        "file": "./resources/containers/eks_cluster/main.tf",
                        "latest_version": "20.33.1",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/eks/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/containers/eks_addons/apigateway",
                "components": [
                    {
                        "type": "module",
                        "name": "eks_blueprints_addons",
                        "version": ["~> 1.16"],
                        "source": ["aws-ia/eks-blueprints-addons/aws"],
                        "file": "./resources/containers/eks_addons/apigateway/main.tf",
                        "latest_version": "1.20.0",
                        "source_url": "https://registry.terraform.io/v1/modules/aws-ia/eks-blueprints-addons/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/containers/eks_addons/cloudwatch",
                "components": [
                    {
                        "type": "module",
                        "name": "eks_blueprints_addons",
                        "version": ["~> 1.16"],
                        "source": ["aws-ia/eks-blueprints-addons/aws"],
                        "file": "./resources/containers/eks_addons/cloudwatch/main.tf",
                        "latest_version": "1.20.0",
                        "source_url": "https://registry.terraform.io/v1/modules/aws-ia/eks-blueprints-addons/aws",
                        "status": "Outdated",
                    },
                    {
                        "type": "module",
                        "name": "iam_eks_role",
                        "version": ["5.39.1"],
                        "source": [
                            "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
                        ],
                        "file": "./resources/containers/eks_addons/cloudwatch/main.tf",
                        "latest_version": "5.52.2",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/iam/aws",
                        "status": "Outdated",
                    },
                ],
            },
            {
                "path": "./resources/containers/eks_addons/open_telemetry",
                "components": [
                    {
                        "type": "module",
                        "name": "eks_blueprints_addons",
                        "version": ["~> 1.16"],
                        "source": ["aws-ia/eks-blueprints-addons/aws"],
                        "file": "./resources/containers/eks_addons/open_telemetry/main.tf",
                        "latest_version": "1.20.0",
                        "source_url": "https://registry.terraform.io/v1/modules/aws-ia/eks-blueprints-addons/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/containers/eks_addons/karpenter",
                "components": [
                    {
                        "type": "module",
                        "name": "eks-blueprints-addons",
                        "version": ["1.16.2"],
                        "source": ["aws-ia/eks-blueprints-addons/aws"],
                        "file": "./resources/containers/eks_addons/karpenter/main.tf",
                        "latest_version": "1.20.0",
                        "source_url": "https://registry.terraform.io/v1/modules/aws-ia/eks-blueprints-addons/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/containers/eks_addons/istio",
                "components": [
                    {
                        "type": "module",
                        "name": "eks_blueprints_addons",
                        "version": ["~> 1.16"],
                        "source": ["aws-ia/eks-blueprints-addons/aws"],
                        "file": "./resources/containers/eks_addons/istio/main.tf",
                        "latest_version": "1.20.0",
                        "source_url": "https://registry.terraform.io/v1/modules/aws-ia/eks-blueprints-addons/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/network/vpc",
                "components": [
                    {
                        "type": "module",
                        "name": "vpc",
                        "version": ["5.8.1"],
                        "source": ["terraform-aws-modules/vpc/aws"],
                        "file": "./resources/network/vpc/main.tf",
                        "latest_version": "5.19.0",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/vpc/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/network/security_groups/alb_main",
                "components": [
                    {
                        "type": "module",
                        "name": "sg",
                        "version": ["5.1.2"],
                        "source": ["terraform-aws-modules/security-group/aws"],
                        "file": "./resources/network/security_groups/alb_main/main.tf",
                        "latest_version": "5.3.0",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/security-group/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/network/security_groups/vpce_secretsmanager",
                "components": [
                    {
                        "type": "module",
                        "name": "sg",
                        "version": ["5.1.2"],
                        "source": ["terraform-aws-modules/security-group/aws"],
                        "file": "./resources/network/security_groups/vpce_secretsmanager/main.tf",
                        "latest_version": "5.3.0",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/security-group/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/network/security_groups/ec2_bastion",
                "components": [
                    {
                        "type": "module",
                        "name": "sg",
                        "version": ["5.1.2"],
                        "source": ["terraform-aws-modules/security-group/aws"],
                        "file": "./resources/network/security_groups/ec2_bastion/main.tf",
                        "latest_version": "5.3.0",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/security-group/aws",
                        "status": "Outdated",
                    }
                ],
            },
            {
                "path": "./resources/network/vpc_endpoints",
                "components": [
                    {
                        "type": "module",
                        "name": "vpc_endpoints",
                        "version": ["5.8.1"],
                        "source": [
                            "terraform-aws-modules/vpc/aws//modules/vpc-endpoints"
                        ],
                        "file": "./resources/network/vpc_endpoints/main.tf",
                        "latest_version": "5.19.0",
                        "source_url": "https://registry.terraform.io/v1/modules/terraform-aws-modules/vpc/aws",
                        "status": "Outdated",
                    }
                ],
            },
        ],
    }

    manager = InventoryVersionManager()
    updated_inventory = await manager.check_versions(inventory)
    return updated_inventory


if __name__ == "__main__":
    asyncio.run(main())
