"""Unit tests for provider source URL fix."""

import unittest
import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from thothctl.services.inventory.version_service import ProviderVersionChecker, ProviderVersionManager


class TestProviderSourceUrlFix(unittest.TestCase):
    """Test cases for the provider source URL fix."""

    def test_get_latest_provider_version_returns_tuple(self):
        """Test that get_latest_provider_version returns a tuple of (version, source_url)."""
        
        async def run_test():
            async with ProviderVersionChecker() as checker:
                # Test with a known provider
                version, source_url, published_at = await checker.get_latest_provider_version(
                    "registry.terraform.io/hashicorp/aws", "aws"
                )
                
                # Should return a tuple
                self.assertIsInstance(version, (str, type(None)))
                self.assertIsInstance(source_url, str)
                
                # Source URL should be a valid URL
                if not source_url.startswith("Error:"):
                    self.assertTrue(source_url.startswith("https://"))
                    self.assertIn("providers", source_url)
                    self.assertIn("hashicorp", source_url)
                    self.assertIn("aws", source_url)
        
        # Run the async test
        asyncio.run(run_test())

    def test_provider_version_manager_sets_source_url(self):
        """Test that ProviderVersionManager properly sets source_url in provider dictionaries."""
        
        async def run_test():
            test_providers = [
                {
                    "name": "aws",
                    "version": "5.0.0",
                    "source": "registry.terraform.io/hashicorp/aws",
                    "module": "Root",
                    "component": "test_component"
                }
            ]
            
            version_manager = ProviderVersionManager()
            updated_providers = await version_manager.check_provider_versions(test_providers)
            
            # Should have one provider
            self.assertEqual(len(updated_providers), 1)
            
            provider = updated_providers[0]
            
            # Should have all required fields
            self.assertIn("latest_version", provider)
            self.assertIn("source_url", provider)
            self.assertIn("status", provider)
            
            # Source URL should be set and not Null
            source_url = provider.get("source_url")
            self.assertIsNotNone(source_url)
            self.assertNotEqual(source_url, "Null")
            self.assertNotEqual(source_url, "Not set")
            
            # If not an error, should be a valid URL
            if not source_url.startswith("Error:"):
                self.assertTrue(source_url.startswith("https://"))
        
        # Run the async test
        asyncio.run(run_test())

    def test_provider_source_url_consistency(self):
        """Test that provider source URLs are consistent with the provider source."""
        
        async def run_test():
            test_cases = [
                {
                    "provider_source": "registry.terraform.io/hashicorp/aws",
                    "provider_name": "aws",
                    "expected_url_contains": ["hashicorp", "aws"]
                },
                {
                    "provider_source": "registry.opentofu.org/hashicorp/random",
                    "provider_name": "random", 
                    "expected_url_contains": ["hashicorp", "random"]
                }
            ]
            
            async with ProviderVersionChecker() as checker:
                for test_case in test_cases:
                    version, source_url, published_at = await checker.get_latest_provider_version(
                        test_case["provider_source"], test_case["provider_name"]
                    )
                    
                    # If not an error, check URL contains expected parts
                    if not source_url.startswith("Error:"):
                        for expected_part in test_case["expected_url_contains"]:
                            self.assertIn(expected_part, source_url, 
                                f"Source URL '{source_url}' should contain '{expected_part}'")
        
        # Run the async test
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
