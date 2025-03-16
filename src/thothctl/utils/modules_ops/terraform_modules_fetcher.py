import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import os
import requests


class TerraformModulesCache:
    def __init__(self, cache_dir: str = ".registry_cache"):
        self.cache_dir = cache_dir
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def _generate_cache_key(
        self, namespaces: Union[str, List[str]], provider: str
    ) -> str:
        if isinstance(namespaces, str):
            namespaces = [namespaces]
        key_string = f"{'-'.join(sorted(namespaces))}_{provider}"
        print(f"Generated key string: {key_string}")
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> str:
        return os.path.join(self.cache_dir, f"{cache_key}.json")

    def save(
        self, modules: List[Dict], namespaces: Union[str, List[str]], provider: str
    ):
        """Save modules data to cache with timestamp."""
        if isinstance(namespaces, str):
            namespaces = [namespaces]

        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "modules": modules,
            "namespaces": namespaces,
            "provider": provider,
        }

        cache_key = self._generate_cache_key(namespaces, provider)
        cache_path = self._get_cache_path(cache_key)

        print(f"Saving cache to: {cache_path}")
        with open(cache_path, "w") as f:
            json.dump(cache_data, f, indent=2)

    def get(
        self, namespaces: Union[str, List[str]], provider: str, max_age_hours: int = 24
    ) -> Optional[List[Dict]]:
        """
        Get modules from cache with debug information.
        """
        cache_key = self._generate_cache_key(namespaces, provider)
        cache_path = self._get_cache_path(cache_key)

        print(f"Looking for cache file: {cache_path}")

        # List all files in cache directory for debugging
        print("Available files in cache directory:")
        for f in os.listdir(self.cache_dir):
            print(f"- {f}")

        if not os.path.exists(cache_path):
            print(f"Cache file not found at: {cache_path}")
            # Try to find a matching file
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                        cached_namespaces = data.get("namespaces", [])
                        cached_provider = data.get("provider")

                        # Check if this cache file contains our target namespace
                        if (
                            isinstance(namespaces, str)
                            and namespaces in cached_namespaces
                        ) or (
                            isinstance(namespaces, list)
                            and any(ns in cached_namespaces for ns in namespaces)
                        ):
                            if cached_provider == provider:
                                print(f"Found matching cache file: {filename}")
                                modules = data.get("modules", [])
                                # Filter for specific namespace
                                if isinstance(namespaces, str):
                                    modules = [
                                        m
                                        for m in modules
                                        if m.get("namespace") == namespaces
                                    ]
                                return modules
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
            return None

        try:
            with open(cache_path, "r") as f:
                cache_data = json.load(f)

            print("Cache file found and loaded")
            cache_time = datetime.fromisoformat(cache_data["timestamp"])
            if datetime.now() - cache_time > timedelta(hours=max_age_hours):
                print(f"Cache expired (older than {max_age_hours} hours)")
                return None

            modules = cache_data.get("modules", [])

            # Filter modules for specific namespace
            if isinstance(namespaces, str):
                modules = [m for m in modules if m.get("namespace") == namespaces]

            return modules

        except Exception as e:
            print(f"Error reading cache: {e}")
            return None

    def list_cache_files(self):
        """List all cache files and their contents summary."""
        print("\nAvailable cache files:")
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.cache_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                        print(f"\nFile: {filename}")
                        print(f"Namespaces: {data.get('namespaces')}")
                        print(f"Provider: {data.get('provider')}")
                        print(f"Timestamp: {data.get('timestamp')}")
                        print(f"Module count: {len(data.get('modules', []))}")
                except Exception as e:
                    print(f"Error reading {filename}: {e}")


class TerraformModulesFetcher:
    def __init__(self, base_url: str = "https://registry.terraform.io/v1/modules"):
        self.base_url = base_url
        self.cache = TerraformModulesCache()

    def fetch_modules(
        self,
        namespaces: Union[str, List[str]] = "terraform-aws-modules",
        provider: str = "aws",
        limit: int = 20,
        max_modules: int = 100,
        use_cache: bool = True,
    ) -> List[Dict]:
        """
        Fetch Terraform modules from multiple namespaces with caching support.
        """
        if isinstance(namespaces, str):
            namespaces = [namespaces]

        # Try to get from cache first
        if use_cache:
            cached_modules = self.cache.get(namespaces, provider)
            if cached_modules is not None:
                # Add provider filter for cached results as well
                filtered_cached = [
                    module
                    for module in cached_modules
                    if module.get("provider") == provider
                ]
                print(f"Using cached data for namespaces: {', '.join(namespaces)}")
                return filtered_cached[:max_modules]

        # If no cache or cache expired, fetch from API
        all_modules = []
        modules_per_namespace = max_modules // len(namespaces)

        for namespace in namespaces:
            modules = self._fetch_namespace_modules(
                namespace=namespace,
                provider=provider,
                limit=limit,
                max_modules=modules_per_namespace,
            )
            all_modules.extend(modules)

        # Sort modules by downloads (most popular first)
        all_modules.sort(key=lambda x: x.get("downloads", 0), reverse=True)

        # Save to cache
        if all_modules:
            self.cache.save(all_modules, namespaces, provider)

        return all_modules[:max_modules]

    def _fetch_namespace_modules(
        self, namespace: str, provider: str, limit: int, max_modules: int
    ) -> List[Dict]:
        """Fetch modules for a single namespace."""
        modules = []
        offset = 0

        while len(modules) < max_modules:
            page_modules, next_offset = self._fetch_page(
                namespace=namespace, provider=provider, limit=limit, offset=offset
            )

            if not page_modules:
                break

            # Filter modules to include only the specified provider
            filtered_modules = [
                module for module in page_modules if module.get("provider") == provider
            ]

            modules.extend(filtered_modules)

            if next_offset is None:
                break

            offset = next_offset

        return modules[:max_modules]

    def _fetch_page(
        self, namespace: str, provider: str, limit: int, offset: int
    ) -> tuple[List[Dict], Optional[int]]:
        url = f"{self.base_url}/{namespace}"
        params = {"provider": provider, "limit": limit, "offset": offset}

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            modules = data.get("modules", [])
            meta = data.get("meta", {})
            next_offset = meta.get("next_offset")

            return modules, next_offset

        except requests.exceptions.RequestException as e:
            print(f"Error fetching modules for namespace {namespace}: {e}")
            return [], None
        except json.JSONDecodeError:
            print(f"Error parsing JSON response for namespace {namespace}")
            return [], None


def display_modules(modules: List[Dict]) -> None:
    print(f"\nTotal modules found: {len(modules)}\n")

    for module in modules:
        print(f"Namespace: {module['namespace']}")
        print(f"Name: {module['name']}")
        print(f"Provider: {module['provider']}")
        print(f"Version: {module['version']}")
        print(f"Downloads: {module['downloads']}")
        print(f"Description: {module['description']}")
        print("-" * 80)


def main():
    fetcher = TerraformModulesFetcher()

    # Example using multiple namespaces
    namespaces = ["terraform-aws-modules", "aws-ia"]

    # First fetch - will get from API and cache
    modules = fetcher.fetch_modules(
        namespaces=namespaces, provider="aws", limit=20, max_modules=100, use_cache=True
    )

    display_modules(modules)


if __name__ == "__main__":
    main()

    # Create a cache instance
    cache = TerraformModulesCache()

    # List all available cache files first
    cache.list_cache_files()

    # Get cached modules with debug information
    modules = cache.get("aws-ia", "aws")
    print(modules)
    if modules:
        # Process cached data
        for module in modules:
            if module["name"] == "sce-core":
                print("\nFound target module:")
                print(json.dumps(module, indent=2))
    else:
        print("\nNo matching modules found in cache")
