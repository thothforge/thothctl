import json
from typing import Dict, List, Optional

import requests

from .terraform_modules_fetcher import TerraformModulesCache


class TerraformModuleDetails:
    def __init__(self, base_url: str = "https://registry.terraform.io/v1/modules"):
        self.base_url = base_url
        self.cache = TerraformModulesCache()

    def get_module_details(
        self, namespace: str, name: str, provider: str
    ) -> Optional[Dict]:
        """
        Get detailed information about a specific module, including inputs and outputs.
        First tries to get from cache, then falls back to API if needed.
        """
        # Try to get basic module info from cache first
        cached_modules = self.cache.get(namespace, provider)
        cached_module = None

        if cached_modules:
            for module in cached_modules:
                if (
                    module.get("namespace") == namespace
                    and module.get("name") == name
                    and module.get("provider") == provider
                ):
                    cached_module = module
                    break

        # If not in cache or we need fresh data, fetch from API
        try:
            url = f"{self.base_url}/{namespace}/{name}/{provider}"
            response = requests.get(url)
            response.raise_for_status()
            module_data = response.json()

            # Extract the relevant information
            details = {
                "basic_info": {
                    "id": module_data.get("id"),
                    "namespace": module_data.get("namespace"),
                    "name": module_data.get("name"),
                    "provider": module_data.get("provider"),
                    "version": module_data.get("version"),
                    "description": module_data.get("description"),
                    "source": module_data.get("source"),
                    "downloads": module_data.get("downloads"),
                    "published_at": module_data.get("published_at"),
                },
                "root": self._extract_module_components(module_data.get("root", {})),
                "submodules": [
                    self._extract_module_components(submodule)
                    for submodule in module_data.get("submodules", [])
                ],
            }

            return details

        except requests.exceptions.RequestException as e:
            print(f"Error fetching module details: {e}")
            # If API call fails and we have cached data, use that
            if cached_module:
                print("Using cached module data")
                return {"basic_info": cached_module}
            return None

    def _extract_module_components(self, module_data: Dict) -> Dict:
        """Extract and format module components (inputs, outputs, etc.)."""
        return {
            "path": module_data.get("path", ""),
            "inputs": self._format_variables(module_data.get("inputs", [])),
            "outputs": self._format_variables(module_data.get("outputs", [])),
            "resources": module_data.get("resources", []),
            "dependencies": module_data.get("dependencies", []),
        }

    def _format_variables(self, variables: List[Dict]) -> List[Dict]:
        """Format variables (inputs or outputs) with consistent structure."""
        formatted = []
        for var in variables:
            formatted_var = {
                "name": var.get("name", ""),
                "description": var.get("description", ""),
            }
            # Only include default if it exists (inputs only)
            if "default" in var:
                formatted_var["default"] = var["default"]
            formatted.append(formatted_var)
        return formatted


def main():
    module_fetcher = TerraformModuleDetails()

    # Example usage
    module_info = module_fetcher.get_module_details(
        namespace="terraform-aws-modules", name="rds", provider="aws"
    )

    if module_info:
        print("\nModule Details:")
        print(json.dumps(module_info["basic_info"], indent=2))

        print("\nRoot Module:")
        root = module_info.get("root", {})

        print("\nInputs:")
        for input_var in root.get("inputs", []):
            print(f"\nName: {input_var['name']}")
            print(f"Description: {input_var['description']}")
            if "default" in input_var:
                print(f"Default: {input_var['default']}")

        print("\nOutputs:")
        for output_var in root.get("outputs", []):
            print(f"\nName: {output_var['name']}")
            print(f"Description: {output_var['description']}")

        if module_info.get("submodules"):
            print("\nSubmodules:")
            for submodule in module_info["submodules"]:
                print(f"\nSubmodule Path: {submodule['path']}")
                print("Inputs:", len(submodule.get("inputs", [])))
                print("Outputs:", len(submodule.get("outputs", [])))
                print("Resources:", len(submodule.get("resources", [])))


if __name__ == "__main__":
    main()
