import gzip
import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional

import os
import requests


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TerraformModuleVersions:
    def __init__(self, cache_dir="~/.terraform-cache"):
        self.base_url = "https://registry.terraform.io/v1"
        self.cache_dir = os.path.expanduser(cache_dir)
        self.cache_expiry_days = 1

    def get_cache_filename(
        self, namespace: str, type: str = "module", name: str = "", provider: str = ""
    ) -> str:
        """Generate cache filename based on type and module info"""
        if type == "namespace":
            return os.path.join(self.cache_dir, f"namespace_{namespace}.json.gz")
        else:
            module_id = f"{namespace}_{name}_{provider}"
            return os.path.join(self.cache_dir, f"module_{module_id}.json.gz")

    def get_metadata_filename(
        self, namespace: str, type: str = "module", name: str = "", provider: str = ""
    ) -> str:
        """Generate metadata filename based on type and module info"""
        if type == "namespace":
            return os.path.join(self.cache_dir, f"metadata_namespace_{namespace}.json")
        else:
            module_id = f"{namespace}_{name}_{provider}"
            return os.path.join(self.cache_dir, f"metadata_{module_id}.json")

    def ensure_cache_dir(self):
        os.makedirs(self.cache_dir, exist_ok=True)

    def is_cache_valid(
        self, namespace: str, type: str = "module", name: str = "", provider: str = ""
    ) -> bool:
        try:
            metadata_file = self.get_metadata_filename(namespace, type, name, provider)
            if not os.path.exists(metadata_file):
                return False

            with open(metadata_file, "r") as f:
                metadata = json.load(f)
                last_updated = datetime.fromisoformat(metadata["last_updated"])
                age = (datetime.now() - last_updated).days
                return age < self.cache_expiry_days
        except Exception as e:
            logger.error(f"Error checking cache validity: {e}")
            return False

    def save_to_cache(
        self,
        data: Dict,
        namespace: str,
        type: str = "module",
        name: str = "",
        provider: str = "",
    ):
        try:
            self.ensure_cache_dir()

            cache_file = self.get_cache_filename(namespace, type, name, provider)
            with gzip.open(cache_file, "wt") as f:
                json.dump(data, f)

            metadata = {
                "last_updated": datetime.now().isoformat(),
                "namespace": namespace,
                "type": type,
            }

            if type == "module":
                metadata.update(
                    {
                        "name": name,
                        "provider": provider,
                        "version_count": len(data["modules"][0]["versions"])
                        if data.get("modules")
                        else 0,
                    }
                )
            else:
                metadata["module_count"] = len(data.get("modules", []))

            metadata_file = self.get_metadata_filename(namespace, type, name, provider)
            with open(metadata_file, "w") as f:
                json.dump(metadata, f)

            logger.info(f"Cache saved successfully for {type}: {namespace}")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def load_from_cache(
        self, namespace: str, type: str = "module", name: str = "", provider: str = ""
    ) -> Optional[Dict]:
        try:
            cache_file = self.get_cache_filename(namespace, type, name, provider)
            with gzip.open(cache_file, "rt") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return None

    def fetch_namespace_modules(self, namespace: str) -> Optional[Dict]:
        """Fetch all modules for a specific namespace"""
        try:
            modules = []
            page = 1

            while True:
                url = f"{self.base_url}/modules/search"
                params = {
                    "q": f"namespace:{namespace} provider:aws",
                    "namespace": namespace,
                    "page": page,
                    "limit": 100,
                }

                logger.info(f"Fetching page {page} for namespace: {namespace}")
                logger.debug(f"Request URL: {url}")
                logger.debug(f"Request params: {params}")

                response = requests.get(url, params=params)

                # Add detailed response logging
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")

                response.raise_for_status()
                data = response.json()

                logger.debug(f"Response data: {json.dumps(data, indent=2)}")

                if not data.get("modules"):
                    logger.info(f"No more modules found after page {page}")
                    break

                modules.extend(data["modules"])
                logger.info(f"Found {len(data['modules'])} modules on page {page}")

                page += 1
                time.sleep(1)  # Rate limiting

            logger.info(f"Total modules found: {len(modules)}")
            return {"modules": modules}

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching namespace modules: {e}")
            if hasattr(e.response, "text"):
                logger.error(f"Response text: {e.response.text}")
            return None

    def fetch_module_versions(
        self, namespace: str, name: str, provider: str, limit: int = 3
    ) -> Optional[Dict]:
        """Fetch versions for a specific module"""
        try:
            url = f"{self.base_url}/modules/{namespace}/{name}/{provider}/versions"
            logger.info(f"Fetching versions for module: {namespace}/{name}/{provider}")

            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # Limit versions to the latest 'limit' versions
            if data.get("modules"):
                data["modules"][0]["versions"] = data["modules"][0]["versions"][:limit]

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching module versions: {e}")
            return None

    def get_namespace_modules(
        self, namespace: str, force_refresh: bool = False
    ) -> Optional[Dict]:
        """Get all modules for a namespace from cache or fetch if needed"""
        if not force_refresh and self.is_cache_valid(namespace, "namespace"):
            logger.info(f"Loading namespace {namespace} from cache...")
            data = self.load_from_cache(namespace, "namespace")
            if data:
                return data

        logger.info(f"Fetching fresh data for namespace {namespace}...")
        data = self.fetch_namespace_modules(namespace)
        if data:
            self.save_to_cache(data, namespace, "namespace")
        return data

    def get_module_versions(
        self,
        namespace: str,
        name: str,
        provider: str,
        force_refresh: bool = False,
        limit: int = 3,
    ) -> Optional[Dict]:
        """Get module versions from cache or fetch if needed"""
        if not force_refresh and self.is_cache_valid(
            namespace, "module", name, provider
        ):
            logger.info(f"Loading {namespace}/{name}/{provider} from cache...")
            data = self.load_from_cache(namespace, "module", name, provider)
            if data:
                return data

        logger.info(f"Fetching fresh data for {namespace}/{name}/{provider}...")
        data = self.fetch_module_versions(namespace, name, provider, limit)
        if data:
            self.save_to_cache(data, namespace, "module", name, provider)
        return data


def print_namespace_summary(namespace_data: Dict):
    """Print a summary of namespace modules"""
    if not namespace_data or "modules" not in namespace_data:
        logger.error("No namespace data available")
        return

    modules = namespace_data["modules"]
    logger.info(f"\nTotal modules found: {len(modules)}")

    # Group modules by provider
    provider_modules = defaultdict(list)
    for module in modules:
        provider_modules[module["provider"]].append(module["name"])

    for provider, module_names in provider_modules.items():
        logger.info(f"\nProvider: {provider}")
        for name in sorted(module_names):
            logger.info(f"  - {name}")


def print_module_versions(module_data: Dict):
    """Print a summary of the module versions"""
    if not module_data or "modules" not in module_data:
        logger.error("No module data available")
        return

    module = module_data["modules"][0]
    source = module["source"]
    versions = module["versions"]

    logger.info(f"\nModule: {source}")
    logger.info(f"Latest {len(versions)} versions:")

    for version_data in versions:
        version = version_data["version"]
        logger.info(f"\nVersion: {version}")

        if "root" in version_data:
            logger.info("Root Providers:")
            for provider in version_data["root"]["providers"]:
                logger.info(
                    f"  - {provider['name']}"
                    + (f" ({provider['version']})" if provider["version"] else "")
                )


def main():
    # Enable debug logging to see more details
    logging.getLogger(__name__).setLevel(logging.DEBUG)

    client = TerraformModuleVersions()
    namespace = "terraform-aws-modules"

    # 1. List all modules in the namespace
    logger.info(f"Fetching all modules for namespace: {namespace}")
    namespace_data = client.get_namespace_modules(namespace)

    if namespace_data and namespace_data.get("modules"):
        print_namespace_summary(namespace_data)

        # 2. Get latest 3 versions for some example modules
        example_modules = [
            {"name": "vpc", "provider": "aws"},
            {"name": "security-group", "provider": "aws"},
        ]

        for module in example_modules:
            logger.info(f"\nFetching latest versions for {namespace}/{module['name']}")
            module_data = client.get_module_versions(
                namespace=namespace,
                name=module["name"],
                provider=module["provider"],
                limit=3,
            )
            if module_data:
                print_module_versions(module_data)
    else:
        logger.error(f"No modules found for namespace: {namespace}")


if __name__ == "__main__":
    main()
