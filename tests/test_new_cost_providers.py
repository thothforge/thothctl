"""Unit tests for new cost analysis pricing providers."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from thothctl.services.check.project.cost.pricing.providers.eip_pricing import (
    EIPPricingProvider,
)
from thothctl.services.check.project.cost.pricing.providers.free_resources_pricing import (
    FreeResourcesPricingProvider,
)
from thothctl.services.check.project.cost.pricing.providers.kms_pricing import (
    KMSPricingProvider,
)


class TestKMSPricingProvider:
    """Test KMS pricing provider."""

    @pytest.fixture
    def pricing_client(self):
        return Mock()

    @pytest.fixture
    def provider(self, pricing_client):
        return KMSPricingProvider(pricing_client)

    def test_supported_resources(self, provider):
        """Test KMS supported resources."""
        resources = provider.get_supported_resources()
        assert "aws_kms_key" in resources
        assert "aws_kms_alias" in resources

    def test_kms_key_cost(self, provider):
        """Test KMS key cost calculation."""
        resource_change = {
            "address": "aws_kms_key.test",
            "type": "aws_kms_key",
            "change": {
                "actions": ["create"],
                "after": {"key_usage": "ENCRYPT_DECRYPT"},
            },
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.service_name == "KMS"
        assert result.monthly_cost == 1.0  # $1/month per key
        assert result.confidence_level == "high"

    def test_kms_alias_is_free(self, provider):
        """Test KMS alias has no cost."""
        resource_change = {
            "address": "aws_kms_alias.test",
            "type": "aws_kms_alias",
            "change": {"actions": ["create"], "after": {}},
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.monthly_cost == 0.0
        assert "free" in result.pricing_details["note"].lower()


class TestEIPPricingProvider:
    """Test EIP pricing provider."""

    @pytest.fixture
    def pricing_client(self):
        return Mock()

    @pytest.fixture
    def provider(self, pricing_client):
        return EIPPricingProvider(pricing_client)

    def test_supported_resources(self, provider):
        """Test EIP supported resources."""
        resources = provider.get_supported_resources()
        assert "aws_eip" in resources

    def test_eip_attached_is_free(self, provider):
        """Test attached EIP has no cost."""
        resource_change = {
            "address": "aws_eip.test",
            "type": "aws_eip",
            "change": {
                "actions": ["create"],
                "after": {"instance": "i-1234567890abcdef0"},
            },
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.monthly_cost == 0.0
        assert "free" in result.pricing_details["note"].lower()

    def test_eip_idle_has_cost(self, provider):
        """Test idle EIP has hourly cost."""
        resource_change = {
            "address": "aws_eip.test",
            "type": "aws_eip",
            "change": {"actions": ["create"], "after": {}},
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.hourly_cost == 0.005
        assert result.monthly_cost > 0
        assert "idle" in result.pricing_details["note"].lower()


class TestFreeResourcesPricingProvider:
    """Test free resources pricing provider."""

    @pytest.fixture
    def pricing_client(self):
        return Mock()

    @pytest.fixture
    def provider(self, pricing_client):
        return FreeResourcesPricingProvider(pricing_client)

    def test_supported_resources(self, provider):
        """Test free resources are supported."""
        resources = provider.get_supported_resources()

        # IAM resources
        assert "aws_iam_role" in resources
        assert "aws_iam_policy" in resources

        # VPC resources
        assert "aws_route_table" in resources
        assert "aws_subnet" in resources
        assert "aws_security_group" in resources

        # Other free resources
        assert "aws_resourcegroups_group" in resources
        assert "aws_ebs_encryption_by_default" in resources

    def test_iam_role_is_free(self, provider):
        """Test IAM role has no cost."""
        resource_change = {
            "address": "aws_iam_role.test",
            "type": "aws_iam_role",
            "change": {"actions": ["create"], "after": {}},
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.service_name == "IAM"
        assert result.monthly_cost == 0.0
        assert result.confidence_level == "high"

    def test_vpc_resources_are_free(self, provider):
        """Test VPC resources have no cost."""
        vpc_resources = ["aws_route_table", "aws_subnet", "aws_security_group"]

        for resource_type in vpc_resources:
            resource_change = {
                "address": f"{resource_type}.test",
                "type": resource_type,
                "change": {"actions": ["create"], "after": {}},
            }

            result = provider.get_offline_estimate(resource_change, "us-east-1")

            assert result is not None
            assert result.service_name == "VPC"
            assert result.monthly_cost == 0.0


class TestLambdaCostWarnings:
    """Test Lambda cost estimation warnings."""

    def test_lambda_has_low_confidence(self):
        """Test Lambda estimates have low confidence."""
        from thothctl.services.check.project.cost.pricing.providers.lambda_pricing import (
            LambdaPricingProvider,
        )

        pricing_client = Mock()
        pricing_client.is_available.return_value = False
        provider = LambdaPricingProvider(pricing_client)

        resource_change = {
            "address": "aws_lambda_function.test",
            "type": "aws_lambda_function",
            "change": {
                "actions": ["create"],
                "after": {"memory_size": 128, "timeout": 3},
            },
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.confidence_level == "low"
        assert "invocations/month" in result.pricing_details.get("note", "")

    def test_lambda_uses_moderate_invocations(self):
        """Test Lambda uses 100K (not 1M) invocations as default."""
        from thothctl.services.check.project.cost.pricing.providers.lambda_pricing import (
            LambdaPricingProvider,
        )

        pricing_client = Mock()
        pricing_client.is_available.return_value = False
        provider = LambdaPricingProvider(pricing_client)

        resource_change = {
            "address": "aws_lambda_function.test",
            "type": "aws_lambda_function",
            "change": {
                "actions": ["create"],
                "after": {"memory_size": 128, "timeout": 3},
            },
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        # With 100K invocations at 128MB and 1.5s avg (50% of 3s timeout):
        # GB-seconds = (128/1024) * 1.5 * 100000 = 18750
        # Cost = 18750 * 0.0000166667 + 100000 * 0.0000002 = $0.3125 + $0.02 = ~$0.33/month
        assert result.monthly_cost < 1.0  # Should be well under $1/month
        assert "100,000" in result.pricing_details.get("note", "")
        assert "not defined in IaC" in result.pricing_details.get("note", "")

    def test_lambda_uses_half_timeout_as_duration(self):
        """Test Lambda uses 50% of timeout as estimated avg duration."""
        from thothctl.services.check.project.cost.pricing.providers.lambda_pricing import (
            LambdaPricingProvider,
        )

        pricing_client = Mock()
        pricing_client.is_available.return_value = False
        provider = LambdaPricingProvider(pricing_client)

        resource_change = {
            "address": "aws_lambda_function.test",
            "type": "aws_lambda_function",
            "change": {
                "actions": ["create"],
                "after": {"memory_size": 256, "timeout": 60},
            },
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        # Note should show 30.0s (50% of 60s timeout)
        assert "30.0s" in result.pricing_details.get("note", "")

    def test_lambda_online_uses_moderate_defaults(self):
        """Test Lambda online estimate also uses moderate defaults."""
        from thothctl.services.check.project.cost.pricing.providers.lambda_pricing import (
            LambdaPricingProvider,
        )

        pricing_client = Mock()
        pricing_client.is_available.return_value = True
        provider = LambdaPricingProvider(pricing_client)

        resource_change = {
            "address": "aws_lambda_function.test",
            "type": "aws_lambda_function",
            "change": {
                "actions": ["create"],
                "after": {"memory_size": 128, "timeout": 3},
            },
        }

        result = provider.calculate_cost(resource_change, "us-east-1")

        assert result is not None
        assert result.confidence_level == "low"
        assert "usage-dependent" in result.pricing_details.get("note", "").lower()

    def test_lambda_marks_cost_type_usage_dependent(self):
        """Test Lambda pricing includes cost_type: usage-dependent."""
        from thothctl.services.check.project.cost.pricing.providers.lambda_pricing import (
            LambdaPricingProvider,
        )

        pricing_client = Mock()
        pricing_client.is_available.return_value = False
        provider = LambdaPricingProvider(pricing_client)

        resource_change = {
            "address": "aws_lambda_function.test",
            "type": "aws_lambda_function",
            "change": {
                "actions": ["create"],
                "after": {"memory_size": 128, "timeout": 3},
            },
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.pricing_details.get("cost_type") == "usage-dependent"


class TestECRPricingProvider:
    """Test ECR repository pricing provider."""

    @pytest.fixture
    def pricing_client(self):
        return Mock()

    @pytest.fixture
    def provider(self, pricing_client):
        from thothctl.services.check.project.cost.pricing.providers.ecr_pricing import (
            ECRPricingProvider,
        )

        return ECRPricingProvider(pricing_client)

    def test_supported_resources(self, provider):
        """Test ECR supported resources."""
        resources = provider.get_supported_resources()
        assert "aws_ecr_repository" in resources

    def test_ecr_repository_cost(self, provider):
        """Test ECR repository cost estimation."""
        resource_change = {
            "address": "aws_ecr_repository.app",
            "type": "aws_ecr_repository",
            "change": {
                "actions": ["create"],
                "after": {"image_tag_mutability": "IMMUTABLE"},
            },
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.service_name == "ECR"
        # 5GB * $0.10/GB = $0.50/month
        assert result.monthly_cost == pytest.approx(0.50, abs=0.01)
        assert result.confidence_level == "low"

    def test_ecr_marks_usage_dependent(self, provider):
        """Test ECR pricing is marked as usage-dependent."""
        resource_change = {
            "address": "aws_ecr_repository.app",
            "type": "aws_ecr_repository",
            "change": {
                "actions": ["create"],
                "after": {},
            },
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.pricing_details.get("cost_type") == "usage-dependent"
        assert "not defined in IaC" in result.pricing_details.get("note", "")

    def test_ecr_shows_storage_estimate_in_note(self, provider):
        """Test ECR note explains the storage estimate."""
        resource_change = {
            "address": "aws_ecr_repository.app",
            "type": "aws_ecr_repository",
            "change": {
                "actions": ["create"],
                "after": {"image_tag_mutability": "MUTABLE"},
            },
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert "5GB" in result.pricing_details.get("note", "")
        assert "$0.1/GB" in result.pricing_details.get("note", "")


class TestCloudFormationMapper:
    """Test CloudFormation to Terraform resource mapper."""

    @pytest.fixture
    def mapper(self):
        from thothctl.services.check.project.cost.models.cloudformation_mapper import (
            CloudFormationResourceMapper,
        )

        return CloudFormationResourceMapper()

    def test_kms_key_mapping(self, mapper):
        """Test AWS::KMS::Key maps to aws_kms_key."""
        assert mapper.get_terraform_equivalent("AWS::KMS::Key") == "aws_kms_key"
        assert mapper.is_supported("AWS::KMS::Key")

    def test_kms_alias_mapping(self, mapper):
        """Test AWS::KMS::Alias maps to aws_kms_alias."""
        assert mapper.get_terraform_equivalent("AWS::KMS::Alias") == "aws_kms_alias"
        assert mapper.is_supported("AWS::KMS::Alias")

    def test_iam_role_mapping(self, mapper):
        """Test AWS::IAM::Role maps to aws_iam_role."""
        assert mapper.get_terraform_equivalent("AWS::IAM::Role") == "aws_iam_role"
        assert mapper.is_supported("AWS::IAM::Role")

    def test_iam_policy_mapping(self, mapper):
        """Test AWS::IAM::Policy maps to aws_iam_policy."""
        assert mapper.get_terraform_equivalent("AWS::IAM::Policy") == "aws_iam_policy"
        assert mapper.is_supported("AWS::IAM::Policy")

    def test_iam_managed_policy_mapping(self, mapper):
        """Test AWS::IAM::ManagedPolicy maps to aws_iam_policy."""
        assert (
            mapper.get_terraform_equivalent("AWS::IAM::ManagedPolicy")
            == "aws_iam_policy"
        )
        assert mapper.is_supported("AWS::IAM::ManagedPolicy")

    def test_ecr_repository_mapping(self, mapper):
        """Test AWS::ECR::Repository maps to aws_ecr_repository."""
        assert (
            mapper.get_terraform_equivalent("AWS::ECR::Repository")
            == "aws_ecr_repository"
        )
        assert mapper.is_supported("AWS::ECR::Repository")

    def test_ssm_parameter_mapping(self, mapper):
        """Test AWS::SSM::Parameter maps to aws_ssm_parameter."""
        assert (
            mapper.get_terraform_equivalent("AWS::SSM::Parameter")
            == "aws_ssm_parameter"
        )
        assert mapper.is_supported("AWS::SSM::Parameter")

    def test_s3_bucket_policy_mapping(self, mapper):
        """Test AWS::S3::BucketPolicy maps to aws_s3_bucket_policy."""
        assert (
            mapper.get_terraform_equivalent("AWS::S3::BucketPolicy")
            == "aws_s3_bucket_policy"
        )
        assert mapper.is_supported("AWS::S3::BucketPolicy")

    def test_unsupported_resource_returns_none(self, mapper):
        """Test unsupported resource type returns None."""
        assert mapper.get_terraform_equivalent("AWS::Custom::Unknown") is None
        assert not mapper.is_supported("AWS::Custom::Unknown")

    def test_all_previously_unsupported_now_mapped(self, mapper):
        """Test all resources from the reported warnings are now supported."""
        previously_unsupported = [
            "AWS::KMS::Key",
            "AWS::KMS::Alias",
            "AWS::S3::BucketPolicy",
            "AWS::ECR::Repository",
            "AWS::IAM::Role",
            "AWS::IAM::Policy",
            "AWS::IAM::ManagedPolicy",
            "AWS::SSM::Parameter",
        ]

        for resource_type in previously_unsupported:
            assert mapper.is_supported(resource_type), (
                f"{resource_type} should be supported"
            )


class TestExpandedFreeResources:
    """Test newly added free resources."""

    @pytest.fixture
    def pricing_client(self):
        return Mock()

    @pytest.fixture
    def provider(self, pricing_client):
        return FreeResourcesPricingProvider(pricing_client)

    def test_s3_bucket_policy_is_free(self, provider):
        """Test S3 bucket policy has no cost."""
        resource_change = {
            "address": "aws_s3_bucket_policy.test",
            "type": "aws_s3_bucket_policy",
            "change": {"actions": ["create"], "after": {}},
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.service_name == "S3"
        assert result.monthly_cost == 0.0

    def test_ssm_parameter_is_free(self, provider):
        """Test SSM parameter (standard tier) has no cost."""
        resource_change = {
            "address": "aws_ssm_parameter.test",
            "type": "aws_ssm_parameter",
            "change": {"actions": ["create"], "after": {}},
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.service_name == "SSM"
        assert result.monthly_cost == 0.0

    def test_ecr_lifecycle_policy_is_free(self, provider):
        """Test ECR lifecycle policy has no cost."""
        resource_change = {
            "address": "aws_ecr_lifecycle_policy.test",
            "type": "aws_ecr_lifecycle_policy",
            "change": {"actions": ["create"], "after": {}},
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.service_name == "ECR"
        assert result.monthly_cost == 0.0

    def test_iam_role_policy_attachment_is_free(self, provider):
        """Test IAM role policy attachment has no cost."""
        resource_change = {
            "address": "aws_iam_role_policy_attachment.test",
            "type": "aws_iam_role_policy_attachment",
            "change": {"actions": ["create"], "after": {}},
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.service_name == "IAM"
        assert result.monthly_cost == 0.0

    def test_s3_encryption_config_is_free(self, provider):
        """Test S3 encryption configuration has no cost."""
        resource_change = {
            "address": "aws_s3_bucket_server_side_encryption_configuration.test",
            "type": "aws_s3_bucket_server_side_encryption_configuration",
            "change": {"actions": ["create"], "after": {}},
        }

        result = provider.get_offline_estimate(resource_change, "us-east-1")

        assert result is not None
        assert result.service_name == "S3"
        assert result.monthly_cost == 0.0

    def test_vpc_security_group_rule_is_free(self, provider):
        """Test VPC security group ingress/egress rules are free."""
        for resource_type in [
            "aws_vpc_security_group_ingress_rule",
            "aws_vpc_security_group_egress_rule",
        ]:
            resource_change = {
                "address": f"{resource_type}.test",
                "type": resource_type,
                "change": {"actions": ["create"], "after": {}},
            }

            result = provider.get_offline_estimate(resource_change, "us-east-1")

            assert result is not None, f"{resource_type} should be supported"
            assert result.service_name == "VPC"
            assert result.monthly_cost == 0.0


class TestUnifiedCostReport:
    """Test unified cost report generator."""

    def test_unified_report_creation(self):
        """Test unified report can be created."""
        from thothctl.services.check.project.cost.models.cost_models import CostAnalysis
        from thothctl.services.check.project.cost.unified_cost_report import (
            UnifiedCostReportGenerator,
        )

        generator = UnifiedCostReportGenerator()

        # Mock analysis
        analysis = Mock(spec=CostAnalysis)
        analysis.total_monthly_cost = 100.0
        analysis.total_annual_cost = 1200.0

        # Add stack report
        generator.add_stack_report("test-stack", analysis, Path("/tmp/test.html"))

        assert len(generator.reports) == 1
        assert generator.reports[0]["stack_name"] == "test-stack"
        assert generator.reports[0]["monthly_cost"] == 100.0

    def test_unified_index_generation(self, tmp_path):
        """Test unified index HTML generation."""
        from thothctl.services.check.project.cost.models.cost_models import CostAnalysis
        from thothctl.services.check.project.cost.unified_cost_report import (
            UnifiedCostReportGenerator,
        )

        generator = UnifiedCostReportGenerator()

        # Add multiple stacks
        for i in range(3):
            analysis = Mock(spec=CostAnalysis)
            analysis.total_monthly_cost = 100.0 * (i + 1)
            analysis.total_annual_cost = 1200.0 * (i + 1)
            generator.add_stack_report(
                f"stack-{i}", analysis, tmp_path / f"stack-{i}.html"
            )

        # Generate index
        index_path = generator.generate_unified_index(tmp_path, "Test Project")

        assert index_path.exists()

        # Verify HTML content
        content = index_path.read_text()
        assert "Test Project" in content
        assert "stack-0" in content
        assert "stack-1" in content
        assert "stack-2" in content
        assert "$600.00" in content  # Total monthly (100 + 200 + 300)


class TestRecommendationsEngine:
    """Test cost recommendations engine."""

    def test_recommendations_always_present(self):
        """Test recommendations are never empty."""
        from thothctl.services.check.project.cost.cost_analyzer import CostAnalyzer
        from thothctl.services.check.project.cost.models.cost_models import (
            CostAction,
            ResourceCost,
        )

        analyzer = CostAnalyzer()

        # Test with minimal cost
        costs = [
            ResourceCost(
                resource_address="test",
                resource_type="aws_instance",
                service_name="EC2",
                region="us-east-1",
                action=CostAction.CREATE,
                hourly_cost=0.01,
                monthly_cost=7.2,
                annual_cost=86.4,
                pricing_details={},
                confidence_level="medium",
            )
        ]

        recommendations = analyzer._generate_recommendations(7.2, costs)

        assert len(recommendations) > 0
        assert any("Review this cost estimate" in r for r in recommendations)

    def test_lambda_warning_in_recommendations(self):
        """Test Lambda cost warning appears in recommendations."""
        from thothctl.services.check.project.cost.cost_analyzer import CostAnalyzer
        from thothctl.services.check.project.cost.models.cost_models import (
            CostAction,
            ResourceCost,
        )

        analyzer = CostAnalyzer()

        costs = [
            ResourceCost(
                resource_address="aws_lambda_function.test",
                resource_type="aws_lambda_function",
                service_name="Lambda",
                region="us-east-1",
                action=CostAction.CREATE,
                hourly_cost=0.001,
                monthly_cost=0.72,
                annual_cost=8.64,
                pricing_details={"note": "Estimated at 1000 executions/month"},
                confidence_level="low",
            )
        ]

        recommendations = analyzer._generate_recommendations(0.72, costs)

        assert any("Lambda costs are estimated" in r for r in recommendations)
        assert any("Actual Lambda costs depend" in r for r in recommendations)

    def test_high_cost_recommendations(self):
        """Test high cost triggers appropriate recommendations."""
        from thothctl.services.check.project.cost.cost_analyzer import CostAnalyzer
        from thothctl.services.check.project.cost.models.cost_models import (
            CostAction,
            ResourceCost,
        )

        analyzer = CostAnalyzer()

        costs = [
            ResourceCost(
                resource_address="test",
                resource_type="aws_instance",
                service_name="EC2",
                region="us-east-1",
                action=CostAction.CREATE,
                hourly_cost=1.5,
                monthly_cost=1080.0,
                annual_cost=12960.0,
                pricing_details={},
                confidence_level="medium",
            )
        ]

        recommendations = analyzer._generate_recommendations(1080.0, costs)

        assert any(
            "Reserved Instances" in r or "Savings Plans" in r for r in recommendations
        )
        assert any("Cost Explorer" in r for r in recommendations)


class TestChangelogParser:
    """Test provider changelog parser."""

    def test_changelog_url_generation(self):
        """Test CHANGELOG URL generation for known providers."""
        from thothctl.services.inventory.changelog_parser import ProviderChangelogParser

        parser = ProviderChangelogParser()

        # Test known providers
        aws_url = parser.get_changelog_url("aws")
        assert "hashicorp/terraform-provider-aws" in aws_url
        assert "CHANGELOG.md" in aws_url

        azure_url = parser.get_changelog_url("azurerm")
        assert "hashicorp/terraform-provider-azurerm" in azure_url

    def test_upgrade_guide_url(self):
        """Test upgrade guide URL generation."""
        from thothctl.services.inventory.changelog_parser import ProviderChangelogParser

        parser = ProviderChangelogParser()

        url = parser.get_upgrade_guide_url("aws", "5")
        assert "registry.terraform.io" in url
        assert "version-5-upgrade" in url

    def test_version_parsing(self):
        """Test version string parsing."""
        from thothctl.services.inventory.changelog_parser import ProviderChangelogParser

        parser = ProviderChangelogParser()

        # Test version comparison
        assert parser._parse_version("5.30.0") == (5, 30, 0)
        assert parser._parse_version("v5.30.0") == (5, 30, 0)
        assert parser._version_less_than("5.0.0", "5.30.0")
        assert not parser._version_less_than("5.30.0", "5.0.0")

    def test_version_range_check(self):
        """Test version range checking."""
        from thothctl.services.inventory.changelog_parser import ProviderChangelogParser

        parser = ProviderChangelogParser()

        # Version in range
        assert parser._is_version_in_range("5.15.0", "5.0.0", "5.30.0")

        # Version outside range
        assert not parser._is_version_in_range("4.67.0", "5.0.0", "5.30.0")
        assert not parser._is_version_in_range("6.0.0", "5.0.0", "5.30.0")

    def test_changelog_entry_parsing(self):
        """Test parsing of changelog entries."""
        from thothctl.services.inventory.changelog_parser import ProviderChangelogParser

        parser = ProviderChangelogParser()

        sample_section = [
            "BREAKING CHANGES:",
            "* resource/aws_instance: Removed `network_interface_id` attribute",
            "",
            "DEPRECATIONS:",
            "* resource/aws_db_instance: The `name` attribute is deprecated",
            "",
            "FEATURES:",
            "* **New Resource:** `aws_bedrock_agent`",
        ]

        entries = parser._parse_version_section("5.15.0", sample_section)

        # Should have entries
        assert len(entries) > 0

        # Check breaking change
        breaking = [e for e in entries if e.type == "breaking"]
        assert len(breaking) > 0
        assert (
            "aws_instance" in breaking[0].resource_name
            or "network_interface" in breaking[0].description
        )

        # Check deprecation
        deprecated = [e for e in entries if e.type == "deprecated"]
        assert len(deprecated) > 0
