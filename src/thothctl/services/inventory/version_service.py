"""Module for checking and comparing versions of Terraform modules and providers."""
import asyncio
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from aiohttp import ClientTimeout
from colorama import Fore


logger = logging.getLogger(__name__)


class RegistryType(Enum):
    """Registry types for module sources."""

    TERRAFORM = "terraform"
    GITHUB = "github"
    TERRAGRUNT = "terragrunt"
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
        """Clean resource path by removing protocol prefix and submodule paths."""
        # Handle tfr:/// format (Terraform Registry)
        if resource.startswith("tfr:///"):
            resource = resource.replace("tfr:///", "")
            

        # Handle submodule paths (everything after //)
        return resource.split("//")[0] if "//" in resource else resource

    def _determine_registry_type(self, source: str) -> RegistryType:
        """Determine registry type from source URL."""
        if "github.com" in source:
            return RegistryType.GITHUB
        elif "terraform-aws-modules" in source or source.startswith("tfr:///"):
            return RegistryType.TERRAFORM
        elif "terragrunt" in source:
            return RegistryType.TERRAGRUNT
        return RegistryType.UNKNOWN

    async def _build_source_url(self, resource: str) -> str:
        """Build appropriate registry URL for the resource."""
        registry_type = self._determine_registry_type(resource)
        
        # Handle tfr:/// format
        if resource.startswith("tfr:///"):
            resource = resource.replace("tfr:///", "")
            
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
            
            # If version is null but we have a source, try to extract version from source
            if version == "Null" and "source" in component:
                resource = component["source"][0]
                
                # Check for terragrunt tfr:/// format with ?version=
                if resource.startswith("tfr:///") and "?version=" in resource:
                    version_match = re.search(r"\?version=([0-9\.]+)", resource)
                    if version_match:
                        version = [version_match.group(1)]
                        component["version"] = version
                        logger.info(f"Extracted version {version} from tfr:/// source")
                        return {"version": version}
                
                # Check for ref= in source
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

    def _is_local_module(self, source: str) -> bool:
        """
        Check if a module source is a local path.
        
        Args:
            source: The source string from the module
            
        Returns:
            True if the source is a local path, False otherwise
        """
        if not source or source == "Null":
            return False
            
        # Check for explicit local path indicators
        if (source.startswith("./") or 
            source.startswith("../") or 
            source.startswith("/")):
            return True
        
        # Check for tfr:/// sources (Terraform registry)
        if source.startswith("tfr:///"):
            return False
        
        # Check for Git sources
        if (source.startswith("git::") or 
            source.startswith("git@") or
            source.endswith(".git") or
            "github.com" in source or
            "gitlab.com" in source or
            "bitbucket.org" in source):
            return False
            
        # Check for HTTP sources
        if source.startswith("http://") or source.startswith("https://"):
            return False
        
        # Check for registry.terraform.io sources
        if source.startswith("registry.terraform.io/"):
            return False
        
        # Split on // to separate main module from submodule path
        main_source = source.split("//")[0]
        
        # Check if it matches Terraform registry format: namespace/name/provider
        # This pattern allows for 2 or 3 parts separated by slashes
        # Examples: hashicorp/aws, terraform-aws-modules/vpc/aws
        registry_pattern = r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)?$'
        if re.match(registry_pattern, main_source):
            return False
        
        # If it contains slashes but doesn't match any of the above patterns,
        # it's likely a local path
        if "/" in source:
            return True
            
        return False
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
            
            # Skip version checking for local modules
            if self._is_local_module(resource):
                logger.debug(f"Skipping version check for local module: {resource}")
                self._set_null_values(component)
                return
                
            # Handle terragrunt tfr:/// format
            if resource.startswith("tfr:///"):
                # Extract the module path without version
                resource = re.sub(r"\?version=[0-9\.]+", "", resource)
            
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


class ProviderVersionChecker:
    """Handles provider version checking against registries."""
    
    TERRAFORM_REGISTRY_BASE = "https://registry.terraform.io/v1/providers"
    OPENTOFU_REGISTRY_BASE = "https://registry.opentofu.org/v1/providers"
    
    def __init__(self, timeout: int = 30):
        """Initialize with configurable timeout."""
        self.timeout = ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()

    def _parse_provider_source(self, source: str) -> Tuple[str, str, str]:
        """
        Parse provider source to extract registry, namespace, and name.
        
        Args:
            source: Provider source like 'registry.terraform.io/hashicorp/aws'
            
        Returns:
            Tuple of (registry_url, namespace, provider_name)
        """
        # Always prioritize Terraform registry due to better API compatibility
        # OpenTofu registry has issues with content-type headers
        
        if source.startswith("registry.terraform.io/"):
            registry_base = self.TERRAFORM_REGISTRY_BASE
            parts = source.replace("registry.terraform.io/", "").split("/")
        elif source.startswith("registry.opentofu.org/"):
            # Use Terraform registry instead of OpenTofu due to API issues
            registry_base = self.TERRAFORM_REGISTRY_BASE
            parts = source.replace("registry.opentofu.org/", "").split("/")
            logger.debug(f"Using Terraform registry for OpenTofu source: {source}")
        elif "/" in source and len(source.split("/")) >= 2:
            # Default to Terraform registry for namespace/provider format
            registry_base = self.TERRAFORM_REGISTRY_BASE
            parts = source.split("/")
        else:
            # Single name, assume hashicorp namespace
            registry_base = self.TERRAFORM_REGISTRY_BASE
            parts = ["hashicorp", source]
            
        if len(parts) >= 2:
            namespace = parts[0]
            provider_name = parts[1]
        else:
            namespace = "hashicorp"
            provider_name = parts[0] if parts else source
            
        return registry_base, namespace, provider_name

    async def get_latest_provider_version(self, provider_source: str, provider_name: str) -> Tuple[Optional[str], str]:
        """
        Get the latest version and source URL for a provider from the registry.
        
        Args:
            provider_source: Provider source URL
            provider_name: Provider name
            
        Returns:
            Tuple of (latest_version, source_url) or (None, source_url) if not found
        """
        if not self._session:
            logger.error("Session not initialized. Use async context manager.")
            return None, "Error: Session not initialized"
            
        try:
            registry_base, namespace, name = self._parse_provider_source(provider_source)
            
            # Use the provider info endpoint to get the latest version directly
            # This is more reliable than the versions endpoint which doesn't sort chronologically
            url = f"{registry_base}/{namespace}/{name}"
            
            logger.debug(f"Checking latest version for {provider_name} at {url}")
            
            # Set proper headers to request JSON
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'ThothCTL/1.0'
            }
            
            async with self._session.get(url, headers=headers) as response:
                if response.status == 200:
                    try:
                        # Try to parse as JSON regardless of content-type header
                        text_content = await response.text()
                        
                        # Check if the content looks like JSON
                        if text_content.strip().startswith('{') or text_content.strip().startswith('['):
                            import json
                            data = json.loads(text_content)
                        else:
                            logger.warning(f"Response for {provider_name} doesn't appear to be JSON: {text_content[:100]}...")
                            return None, url
                        
                        # Get the latest version from the provider info
                        latest_version = data.get("version")
                        
                        if latest_version:
                            logger.info(f"Latest version for {provider_name}: {latest_version}")
                            return latest_version, url
                        else:
                            logger.warning(f"No version found for provider {provider_name}")
                            return None, url
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON response for {provider_name}: {str(e)}")
                        return None, url
                        
                else:
                    logger.warning(f"Failed to fetch version for {provider_name}: HTTP {response.status}")
                    return None, url
                    
        except Exception as e:
            logger.error(f"Error fetching latest version for {provider_name}: {str(e)}")
            return None, f"Error: {str(e)}"

    def _compare_provider_versions(self, current: str, latest: str) -> str:
        """
        Compare current and latest provider versions to determine status.
        
        Args:
            current: Current version string
            latest: Latest version string
            
        Returns:
            Status string: 'current', 'outdated', or 'unknown'
        """
        if not current or not latest:
            return "unknown"
            
        try:
            # Handle 'latest' keyword - if current version is 'latest', it's current
            if current.lower() == "latest":
                return "current"
            
            # Clean version strings (remove 'v' prefix, constraints, etc.)
            current_clean = re.sub(r'^[v~>=<!\s]+', '', current).strip()
            latest_clean = re.sub(r'^[v~>=<!\s]+', '', latest).strip()
            
            # If current version is still 'latest' after cleaning, it's current
            if current_clean.lower() == "latest":
                return "current"
            
            # Handle version constraints like "~> 5.0", ">= 3.1", etc.
            # Extract the base version number for comparison
            current_version_match = re.search(r'(\d+(?:\.\d+)*)', current_clean)
            latest_version_match = re.search(r'(\d+(?:\.\d+)*)', latest_clean)
            
            if not current_version_match or not latest_version_match:
                # If we can't extract version numbers, fall back to string comparison
                if current_clean == latest_clean:
                    return "current"
                else:
                    return "unknown"
            
            current_version = current_version_match.group(1)
            latest_version = latest_version_match.group(1)
            
            # Extract version numbers for comparison
            current_parts = [int(x) for x in current_version.split('.')]
            latest_parts = [int(x) for x in latest_version.split('.')]
            
            # Pad shorter version with zeros for comparison
            max_len = max(len(current_parts), len(latest_parts))
            current_padded = current_parts + [0] * (max_len - len(current_parts))
            latest_padded = latest_parts + [0] * (max_len - len(latest_parts))
            
            # Compare versions
            if current_padded == latest_padded:
                return "current"
            elif current_padded < latest_padded:
                # For constraint versions like "~> 5.0", check if latest satisfies constraint
                if current.startswith('~>'):
                    # Pessimistic constraint: ~> 5.0 allows 5.x but not 6.x
                    if len(current_parts) >= 2 and len(latest_parts) >= 2:
                        if (current_parts[0] == latest_parts[0] and 
                            current_parts[1] <= latest_parts[1]):
                            return "current"
                elif current.startswith('>='):
                    # Greater than or equal: >= 3.1 allows any version >= 3.1
                    return "current"
                elif current.startswith('>'):
                    # Greater than: > 3.0 allows any version > 3.0
                    return "current"
                
                return "outdated"
            else:
                return "newer"  # Local version is newer than registry
                
        except Exception as e:
            logger.warning(f"Error comparing provider versions {current} vs {latest}: {str(e)}")
            return "unknown"


class ProviderVersionManager:
    """Manager for provider version operations."""
    
    def __init__(self):
        """Initialize provider version manager."""
        self.version_checker = ProviderVersionChecker()

    async def check_provider_versions(self, providers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Check latest versions for providers and update their information.
        
        Args:
            providers: List of provider dictionaries
            
        Returns:
            Updated list of provider dictionaries with version information
        """
        if not providers:
            return providers
            
        logger.info(f"Checking latest versions for {len(providers)} providers...")
        
        async with self.version_checker as checker:
            updated_providers = []
            
            # Process providers concurrently
            tasks = []
            for provider in providers:
                task = self._check_single_provider_version(checker, provider)
                tasks.append(task)
                
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for i, result in enumerate(results):
                if isinstance(result, dict):
                    updated_providers.append(result)
                else:
                    # If there was an exception, use original provider
                    logger.warning(f"Error checking provider {providers[i].get('name', 'unknown')}: {result}")
                    updated_providers.append(providers[i])
                    
        return updated_providers

    async def _check_single_provider_version(self, checker: ProviderVersionChecker, provider: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check version for a single provider.
        
        Args:
            checker: ProviderVersionChecker instance
            provider: Provider dictionary
            
        Returns:
            Updated provider dictionary
        """
        provider_name = provider.get("name", "")
        provider_source = provider.get("source", "")
        current_version = provider.get("version", "")
        
        # Get latest version and source URL
        latest_version, source_url = await checker.get_latest_provider_version(provider_source, provider_name)
        
        # Update provider information
        updated_provider = provider.copy()
        
        if latest_version:
            updated_provider["latest_version"] = latest_version
            updated_provider["source_url"] = source_url
            updated_provider["status"] = checker._compare_provider_versions(current_version, latest_version)
        else:
            updated_provider["latest_version"] = "Unknown"
            updated_provider["source_url"] = source_url if source_url else "Null"
            updated_provider["status"] = "Unknown"
            
        return updated_provider


if __name__ == "__main__":
    asyncio.run(main())
