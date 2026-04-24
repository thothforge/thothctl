#!/usr/bin/env python3
"""Test script for provider version checking functionality."""

import asyncio
import sys
import logging
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from thothctl.services.inventory.version_service import ProviderVersionChecker, ProviderVersionManager

# Set up logging to see debug information
logging.basicConfig(level=logging.INFO)


async def test_provider_version_checker():
    """Test the provider version checker functionality."""
    print("🧪 Testing Provider Version Checker...")
    
    # Test data - sample providers with different source formats
    test_providers = [
        {
            "name": "aws",
            "version": "~> 5.0",
            "source": "registry.terraform.io/hashicorp/aws",
            "module": "Root",
            "component": "main"
        },
        {
            "name": "random",
            "version": ">= 3.1",
            "source": "registry.terraform.io/hashicorp/random",
            "module": "Root",
            "component": "main"
        },
        {
            "name": "azurerm",
            "version": "~> 3.0",
            "source": "registry.opentofu.org/hashicorp/azurerm",  # This should fallback to Terraform registry
            "module": "Root",
            "component": "main"
        }
    ]
    
    print(f"📦 Testing with {len(test_providers)} providers...")
    
    # Test individual provider version checking
    async with ProviderVersionChecker() as checker:
        print("\n🔍 Individual Provider Version Checks:")
        for provider in test_providers:
            print(f"  Checking {provider['name']} from {provider['source']}...")
            latest_version, _url, _pub = await checker.get_latest_provider_version(
                provider["source"], 
                provider["name"]
            )
            status = checker._compare_provider_versions(
                provider["version"], 
                latest_version or "unknown"
            )
            
            print(f"  • {provider['name']}: {provider['version']} → {latest_version} ({status})")
    
    # Test provider version manager
    print("\n🔧 Testing Provider Version Manager:")
    manager = ProviderVersionManager()
    updated_providers = await manager.check_provider_versions(test_providers)
    
    print("\n📊 Results:")
    for provider in updated_providers:
        print(f"  • {provider['name']}:")
        print(f"    Current: {provider['version']}")
        print(f"    Latest:  {provider.get('latest_version', 'Unknown')}")
        print(f"    Status:  {provider.get('status', 'Unknown')}")
        print()
    
    # Statistics
    outdated = sum(1 for p in updated_providers if p.get('status') == 'outdated')
    current = sum(1 for p in updated_providers if p.get('status') == 'current')
    unknown = sum(1 for p in updated_providers if p.get('status') == 'unknown')
    newer = sum(1 for p in updated_providers if p.get('status') == 'newer')
    
    print(f"📈 Summary: {outdated} outdated, {current} current, {newer} newer, {unknown} unknown")
    print("✅ Provider version checking test completed!")


async def test_single_provider():
    """Test a single provider to debug issues."""
    print("🔧 Testing single AWS provider...")
    
    async with ProviderVersionChecker() as checker:
        latest_version, _url, _pub = await checker.get_latest_provider_version(
            "registry.terraform.io/hashicorp/aws",
            "aws"
        )
        print(f"AWS latest version: {latest_version}")


if __name__ == "__main__":
    print("Choose test:")
    print("1. Full test")
    print("2. Single provider test")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "2":
        asyncio.run(test_single_provider())
    else:
        asyncio.run(test_provider_version_checker())
