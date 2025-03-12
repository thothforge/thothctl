import requests
import json
import os
import gzip
from datetime import datetime
import logging
from pathlib import Path
import time
from typing import Optional, Dict, List
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TerraformModuleSearch:
    def __init__(self, cache_dir="~/.terraform-cache"):
        self.base_url = "https://registry.terraform.io/v1"
        self.cache_dir = os.path.expanduser(cache_dir)
        self.cache_expiry_days = 1

    def get_cache_filename(self, namespace: str, provider: str) -> str:
        return os.path.join(self.cache_dir, f"search_{namespace}_{provider}.json.gz")

    def get_metadata_filename(self, namespace: str, provider: str) -> str:
        return os.path.join(self.cache_dir, f"metadata_search_{namespace}_{provider}.json")

    def ensure_cache_dir(self):
        os.makedirs(self.cache_dir, exist_ok=True)

    def is_cache_valid(self, namespace: str, provider: str) -> bool:
        try:
            metadata_file = self.get_metadata_filename(namespace, provider)
            if not os.path.exists(metadata_file):
                return False

            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                last_updated = datetime.fromisoformat(metadata['last_updated'])
                age = (datetime.now() - last_updated).days
                return age < self.cache_expiry_days
        except Exception as e:
            logger.error(f"Error checking cache validity: {e}")
            return False

    def save_to_cache(self, data: Dict, namespace: str, provider: str):
        try:
            self.ensure_cache_dir()

            cache_file = self.get_cache_filename(namespace, provider)
            with gzip.open(cache_file, 'wt') as f:
                json.dump(data, f)

            metadata = {
                'last_updated': datetime.now().isoformat(),
                'namespace': namespace,
                'provider': provider,
                'module_count': len(data.get('modules', [])),
                'pages_fetched': data.get('pages_fetched', 0)
            }

            metadata_file = self.get_metadata_filename(namespace, provider)
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f)

            logger.info(
                f"Cache saved successfully with {metadata['module_count']} modules "
                f"from {metadata['pages_fetched']} pages"
            )
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def load_from_cache(self, namespace: str, provider: str) -> Optional[Dict]:
        try:
            cache_file = self.get_cache_filename(namespace, provider)
            with gzip.open(cache_file, 'rt') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return None

    def search_modules(self, namespace: str, provider: str, force_refresh: bool = False) -> Optional[Dict]:
        """
        Search for modules with specific namespace and provider
        """
        if not force_refresh and self.is_cache_valid(namespace, provider):
            logger.info(f"Loading {namespace}/{provider} modules from cache...")
            data = self.load_from_cache(namespace, provider)
            if data:
                return data

        try:
            all_modules = []
            current_offset = 0
            pages_fetched = 0
            limit = 100  # Maximum allowed by the API

            while True:
                logger.info(f"Fetching page {pages_fetched + 1} (offset: {current_offset})...")

                url = f"{self.base_url}/modules/search"
                params = {
                    "q": "*",  # Search all modules
                    "limit": limit,
                    "offset": current_offset,
                    "provider": provider,
                    "namespace": namespace
                }

                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                modules = data.get('modules', [])
                if not modules:
                    break

                all_modules.extend(modules)
                pages_fetched += 1

                # Check if there are more pages
                meta = data.get('meta', {})
                next_offset = meta.get('next_offset')
                if next_offset is None:
                    break

                current_offset = next_offset
                time.sleep(1)  # Rate limiting

            result = {
                'modules': all_modules,
                'pages_fetched': pages_fetched,
                'total_modules': len(all_modules)
            }

            self.save_to_cache(result, namespace, provider)
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching modules: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}")
            return None


def print_modules_summary(data: Dict):
    """Print a summary of found modules"""
    if not data or 'modules' not in data:
        logger.error("No module data available")
        return

    modules = data['modules']
    total_pages = data.get('pages_fetched', 0)

    logger.info(f"\nTotal modules found: {len(modules)} (from {total_pages} pages)")

    # Sort modules by downloads
    sorted_modules = sorted(modules, key=lambda x: x.get('downloads', 0), reverse=True)

    logger.info("\nTop modules by downloads:")
    for module in sorted_modules:
        logger.info(
            f"\nModule: {module['namespace']}/{module['name']}/{module['provider']}"
            f"\n  Version: {module['version']}"
            f"\n  Downloads: {module.get('downloads', 0):,}"
            f"\n  Published: {module['published_at']}"
            f"\n  Description: {module.get('description', 'No description')}"
            f"\n  Verified: {module.get('verified', False)}"
        )


def main():
    client = TerraformModuleSearch()

    # Search for terraform-aws-modules
    namespace = "terraform-aws-modules"
    provider = "aws"

    logger.info(f"Searching for modules in {namespace} with provider {provider}...")

    # Force refresh to get latest data
    modules_data = client.search_modules(namespace, provider, force_refresh=True)

    if modules_data:
        print_modules_summary(modules_data)
    else:
        logger.error("No modules found or error occurred")


if __name__ == "__main__":
    main()
