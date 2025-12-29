"""Tests for the Terragrunt parser."""
import unittest
from pathlib import Path

from src.thothctl.services.inventory.terragrunt_parser import TerragruntParser


class TestTerragruntParser(unittest.TestCase):
    """Test cases for the Terragrunt parser."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = TerragruntParser()
        self.test_file = Path(__file__).parent / "terragrunt_test" / "terragrunt.hcl"

    def test_parse_terragrunt_file(self):
        """Test parsing a Terragrunt file."""
        components = self.parser.parse_terragrunt_file(self.test_file)
        
        # Check that we found one component
        self.assertEqual(len(components), 1)
        
        # Check the component details
        component = components[0]
        self.assertEqual(component.type, "terragrunt_module")
        self.assertEqual(component.name, "alb")
        self.assertEqual(component.version, ["8.7.0"])
        self.assertEqual(component.source, ["terraform-aws-modules/alb/aws"])
        self.assertTrue(str(self.test_file.relative_to(Path.cwd())) in component.file)

    def test_extract_module_info(self):
        """Test extracting module information from source strings."""
        # Test tfr:/// format
        name, version, source = self.parser._extract_module_info("tfr:///terraform-aws-modules/alb/aws?version=8.7.0")
        self.assertEqual(name, "aws")
        self.assertEqual(version, "8.7.0")
        self.assertEqual(source, "terraform-aws-modules/alb/aws")
        
        # Test GitHub format
        name, version, source = self.parser._extract_module_info("git::https://github.com/terraform-aws-modules/terraform-aws-vpc.git?ref=v3.14.0")
        self.assertEqual(name, "terraform-aws-vpc")
        self.assertEqual(version, "v3.14.0")
        self.assertEqual(source, "terraform-aws-modules/terraform-aws-vpc")
        
        # Test local module
        name, version, source = self.parser._extract_module_info("../modules/my-module")
        self.assertEqual(name, "my-module")
        self.assertEqual(version, "local")
        self.assertEqual(source, "../modules/my-module")


if __name__ == "__main__":
    unittest.main()
