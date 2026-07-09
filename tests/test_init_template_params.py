"""Unit tests for template parameter loading from .thothcf.toml."""
import pytest

from thothctl.services.project.convert.get_project_data import get_simple_project_props


class TestGetSimpleProjectPropsBatchMode:
    """Test get_simple_project_props in batch mode with template_value defaults."""

    def test_uses_template_value_for_cloud_provider(self):
        """cloud_provider should get its value from template_value."""
        input_parameters = {
            "cloud_provider": {
                "template_value": "aws",
                "condition": "(aws|azure|oci|gcp)",
                "description": "Cloud provider",
            }
        }
        result = get_simple_project_props(
            input_parameters=input_parameters,
            project_properties={},
            project_name="my-project",
            batch_mode=True,
        )
        assert result["cloud_provider"] == "aws"

    def test_uses_template_value_for_deployment_profile(self):
        """deployment_profile should use template_value 'default'."""
        input_parameters = {
            "deployment_profile": {
                "template_value": "default",
                "condition": "^[a-zA-Z0-9_.-]+$",
                "description": "AWS CLI profile",
            }
        }
        result = get_simple_project_props(
            input_parameters=input_parameters,
            project_properties={},
            project_name="test",
            batch_mode=True,
        )
        assert result["deployment_profile"] == "default"

    def test_uses_template_value_for_deployment_region(self):
        """deployment_region should use template_value."""
        input_parameters = {
            "deployment_region": {
                "template_value": "us-east-2",
                "condition": "^[a-z]{2}-[a-z]+-\\d$",
                "description": "Region",
            }
        }
        result = get_simple_project_props(
            input_parameters=input_parameters,
            project_properties={},
            project_name="test",
            batch_mode=True,
        )
        assert result["deployment_region"] == "us-east-2"

    def test_skips_placeholder_template_value(self):
        """If template_value is a #{placeholder}#, don't use it as default."""
        input_parameters = {
            "project_name": {
                "template_value": "#{project_name}#",
                "condition": ".*",
                "description": "Project name",
            }
        }
        result = get_simple_project_props(
            input_parameters=input_parameters,
            project_properties={},
            project_name="my-project",
            batch_mode=True,
        )
        # Should use project_name, not the placeholder pattern
        assert result["project_name"] == "my-project"

    def test_hardcoded_defaults_still_work(self):
        """Known parameters like 'region' still use hardcoded defaults."""
        input_parameters = {
            "region": {
                "template_value": "#{region}#",
                "condition": ".*",
                "description": "Region",
            }
        }
        result = get_simple_project_props(
            input_parameters=input_parameters,
            project_properties={},
            project_name="test",
            batch_mode=True,
        )
        assert result["region"] == "us-east-2"

    def test_full_template_parameters(self):
        """Simulate the full .thothcf.toml from a terragrunt scaffold template."""
        input_parameters = {
            "project_name": {"template_value": "test-wrapper", "condition": ".*", "description": "Project Name"},
            "deployment_region": {"template_value": "us-east-2", "condition": ".*", "description": "Region"},
            "backend_bucket": {"template_value": "test-wrapper-tfstate", "condition": ".*", "description": "Bucket"},
            "cloud_provider": {"template_value": "aws", "condition": "(aws|azure)", "description": "Cloud"},
            "deployment_profile": {"template_value": "default", "condition": ".*", "description": "Profile"},
            "environment": {"template_value": "dev", "condition": ".*", "description": "Env"},
            "owner": {"template_value": "thothctl", "condition": ".*", "description": "Owner"},
            "client": {"template_value": "thothctl", "condition": ".*", "description": "Client"},
        }
        result = get_simple_project_props(
            input_parameters=input_parameters,
            project_properties={},
            project_name="my-infra",
            batch_mode=True,
        )
        assert result["cloud_provider"] == "aws"
        assert result["deployment_profile"] == "default"
        assert result["deployment_region"] == "us-east-2"
        assert result["environment"] == "dev"
        assert result["owner"] == "thothctl"
        assert result["client"] == "thothctl"
        # project_name uses project_name param, not template_value
        assert result["project_name"] == "my-infra"

    def test_empty_input_parameters(self):
        """Empty input_parameters should return empty project_properties."""
        result = get_simple_project_props(
            input_parameters={},
            project_properties={},
            project_name="test",
            batch_mode=True,
        )
        assert result == {}

    def test_simple_string_dict_batch(self):
        """Simple dict (all values are strings) should use values directly."""
        input_parameters = {
            "project": "my-project",
            "region": "eu-west-1",
        }
        result = get_simple_project_props(
            input_parameters=input_parameters,
            project_properties={},
            project_name="test",
            batch_mode=True,
        )
        # For simple dicts, batch mode uses default_values or derives
        assert "project" in result
        assert "region" in result
