"""Unit tests for new cost analysis pricing providers."""
import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path

from thothctl.services.check.project.cost.pricing.providers.kms_pricing import KMSPricingProvider
from thothctl.services.check.project.cost.pricing.providers.eip_pricing import EIPPricingProvider
from thothctl.services.check.project.cost.pricing.providers.free_resources_pricing import FreeResourcesPricingProvider
from thothctl.services.check.project.cost.models.cost_models import CostAction


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
        assert 'aws_kms_key' in resources
        assert 'aws_kms_alias' in resources
    
    def test_kms_key_cost(self, provider):
        """Test KMS key cost calculation."""
        resource_change = {
            'address': 'aws_kms_key.test',
            'type': 'aws_kms_key',
            'change': {
                'actions': ['create'],
                'after': {
                    'key_usage': 'ENCRYPT_DECRYPT'
                }
            }
        }
        
        result = provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert result is not None
        assert result.service_name == 'KMS'
        assert result.monthly_cost == 1.0  # $1/month per key
        assert result.confidence_level == 'high'
    
    def test_kms_alias_is_free(self, provider):
        """Test KMS alias has no cost."""
        resource_change = {
            'address': 'aws_kms_alias.test',
            'type': 'aws_kms_alias',
            'change': {
                'actions': ['create'],
                'after': {}
            }
        }
        
        result = provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert result is not None
        assert result.monthly_cost == 0.0
        assert 'free' in result.pricing_details['note'].lower()


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
        assert 'aws_eip' in resources
    
    def test_eip_attached_is_free(self, provider):
        """Test attached EIP has no cost."""
        resource_change = {
            'address': 'aws_eip.test',
            'type': 'aws_eip',
            'change': {
                'actions': ['create'],
                'after': {
                    'instance': 'i-1234567890abcdef0'
                }
            }
        }
        
        result = provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert result is not None
        assert result.monthly_cost == 0.0
        assert 'free' in result.pricing_details['note'].lower()
    
    def test_eip_idle_has_cost(self, provider):
        """Test idle EIP has hourly cost."""
        resource_change = {
            'address': 'aws_eip.test',
            'type': 'aws_eip',
            'change': {
                'actions': ['create'],
                'after': {}
            }
        }
        
        result = provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert result is not None
        assert result.hourly_cost == 0.005
        assert result.monthly_cost > 0
        assert 'idle' in result.pricing_details['note'].lower()


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
        assert 'aws_iam_role' in resources
        assert 'aws_iam_policy' in resources
        
        # VPC resources
        assert 'aws_route_table' in resources
        assert 'aws_subnet' in resources
        assert 'aws_security_group' in resources
        
        # Other free resources
        assert 'aws_resourcegroups_group' in resources
        assert 'aws_ebs_encryption_by_default' in resources
    
    def test_iam_role_is_free(self, provider):
        """Test IAM role has no cost."""
        resource_change = {
            'address': 'aws_iam_role.test',
            'type': 'aws_iam_role',
            'change': {
                'actions': ['create'],
                'after': {}
            }
        }
        
        result = provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert result is not None
        assert result.service_name == 'IAM'
        assert result.monthly_cost == 0.0
        assert result.confidence_level == 'high'
    
    def test_vpc_resources_are_free(self, provider):
        """Test VPC resources have no cost."""
        vpc_resources = ['aws_route_table', 'aws_subnet', 'aws_security_group']
        
        for resource_type in vpc_resources:
            resource_change = {
                'address': f'{resource_type}.test',
                'type': resource_type,
                'change': {
                    'actions': ['create'],
                    'after': {}
                }
            }
            
            result = provider.get_offline_estimate(resource_change, 'us-east-1')
            
            assert result is not None
            assert result.service_name == 'VPC'
            assert result.monthly_cost == 0.0


class TestLambdaCostWarnings:
    """Test Lambda cost estimation warnings."""
    
    def test_lambda_has_low_confidence(self):
        """Test Lambda estimates have low confidence."""
        from thothctl.services.check.project.cost.pricing.providers.lambda_pricing import LambdaPricingProvider
        
        pricing_client = Mock()
        pricing_client.is_available.return_value = False
        provider = LambdaPricingProvider(pricing_client)
        
        resource_change = {
            'address': 'aws_lambda_function.test',
            'type': 'aws_lambda_function',
            'change': {
                'actions': ['create'],
                'after': {
                    'memory_size': 128,
                    'timeout': 3
                }
            }
        }
        
        result = provider.get_offline_estimate(resource_change, 'us-east-1')
        
        assert result is not None
        assert result.confidence_level == 'low'
        assert 'executions/month' in result.pricing_details.get('note', '')


class TestUnifiedCostReport:
    """Test unified cost report generator."""
    
    def test_unified_report_creation(self):
        """Test unified report can be created."""
        from thothctl.services.check.project.cost.unified_cost_report import UnifiedCostReportGenerator
        from thothctl.services.check.project.cost.models.cost_models import CostAnalysis
        
        generator = UnifiedCostReportGenerator()
        
        # Mock analysis
        analysis = Mock(spec=CostAnalysis)
        analysis.total_monthly_cost = 100.0
        analysis.total_annual_cost = 1200.0
        
        # Add stack report
        generator.add_stack_report('test-stack', analysis, Path('/tmp/test.html'))
        
        assert len(generator.reports) == 1
        assert generator.reports[0]['stack_name'] == 'test-stack'
        assert generator.reports[0]['monthly_cost'] == 100.0
    
    def test_unified_index_generation(self, tmp_path):
        """Test unified index HTML generation."""
        from thothctl.services.check.project.cost.unified_cost_report import UnifiedCostReportGenerator
        from thothctl.services.check.project.cost.models.cost_models import CostAnalysis
        
        generator = UnifiedCostReportGenerator()
        
        # Add multiple stacks
        for i in range(3):
            analysis = Mock(spec=CostAnalysis)
            analysis.total_monthly_cost = 100.0 * (i + 1)
            analysis.total_annual_cost = 1200.0 * (i + 1)
            generator.add_stack_report(f'stack-{i}', analysis, tmp_path / f'stack-{i}.html')
        
        # Generate index
        index_path = generator.generate_unified_index(tmp_path, 'Test Project')
        
        assert index_path.exists()
        
        # Verify HTML content
        content = index_path.read_text()
        assert 'Test Project' in content
        assert 'stack-0' in content
        assert 'stack-1' in content
        assert 'stack-2' in content
        assert '$600.00' in content  # Total monthly (100 + 200 + 300)


class TestRecommendationsEngine:
    """Test cost recommendations engine."""
    
    def test_recommendations_always_present(self):
        """Test recommendations are never empty."""
        from thothctl.services.check.project.cost.cost_analyzer import CostAnalyzer
        from thothctl.services.check.project.cost.models.cost_models import ResourceCost, CostAction
        
        analyzer = CostAnalyzer()
        
        # Test with minimal cost
        costs = [
            ResourceCost(
                resource_address='test',
                resource_type='aws_instance',
                service_name='EC2',
                region='us-east-1',
                action=CostAction.CREATE,
                hourly_cost=0.01,
                monthly_cost=7.2,
                annual_cost=86.4,
                pricing_details={},
                confidence_level='medium'
            )
        ]
        
        recommendations = analyzer._generate_recommendations(7.2, costs)
        
        assert len(recommendations) > 0
        assert any('Review this cost estimate' in r for r in recommendations)
    
    def test_lambda_warning_in_recommendations(self):
        """Test Lambda cost warning appears in recommendations."""
        from thothctl.services.check.project.cost.cost_analyzer import CostAnalyzer
        from thothctl.services.check.project.cost.models.cost_models import ResourceCost, CostAction
        
        analyzer = CostAnalyzer()
        
        costs = [
            ResourceCost(
                resource_address='aws_lambda_function.test',
                resource_type='aws_lambda_function',
                service_name='Lambda',
                region='us-east-1',
                action=CostAction.CREATE,
                hourly_cost=0.001,
                monthly_cost=0.72,
                annual_cost=8.64,
                pricing_details={'note': 'Estimated at 1000 executions/month'},
                confidence_level='low'
            )
        ]
        
        recommendations = analyzer._generate_recommendations(0.72, costs)
        
        assert any('Lambda costs are estimated' in r for r in recommendations)
        assert any('Actual Lambda costs depend' in r for r in recommendations)
    
    def test_high_cost_recommendations(self):
        """Test high cost triggers appropriate recommendations."""
        from thothctl.services.check.project.cost.cost_analyzer import CostAnalyzer
        from thothctl.services.check.project.cost.models.cost_models import ResourceCost, CostAction
        
        analyzer = CostAnalyzer()
        
        costs = [
            ResourceCost(
                resource_address='test',
                resource_type='aws_instance',
                service_name='EC2',
                region='us-east-1',
                action=CostAction.CREATE,
                hourly_cost=1.5,
                monthly_cost=1080.0,
                annual_cost=12960.0,
                pricing_details={},
                confidence_level='medium'
            )
        ]
        
        recommendations = analyzer._generate_recommendations(1080.0, costs)
        
        assert any('Reserved Instances' in r or 'Savings Plans' in r for r in recommendations)
        assert any('Cost Explorer' in r for r in recommendations)


class TestChangelogParser:
    """Test provider changelog parser."""
    
    def test_changelog_url_generation(self):
        """Test CHANGELOG URL generation for known providers."""
        from thothctl.services.inventory.changelog_parser import ProviderChangelogParser
        
        parser = ProviderChangelogParser()
        
        # Test known providers
        aws_url = parser.get_changelog_url('aws')
        assert 'hashicorp/terraform-provider-aws' in aws_url
        assert 'CHANGELOG.md' in aws_url
        
        azure_url = parser.get_changelog_url('azurerm')
        assert 'hashicorp/terraform-provider-azurerm' in azure_url
    
    def test_upgrade_guide_url(self):
        """Test upgrade guide URL generation."""
        from thothctl.services.inventory.changelog_parser import ProviderChangelogParser
        
        parser = ProviderChangelogParser()
        
        url = parser.get_upgrade_guide_url('aws', '5')
        assert 'registry.terraform.io' in url
        assert 'version-5-upgrade' in url
    
    def test_version_parsing(self):
        """Test version string parsing."""
        from thothctl.services.inventory.changelog_parser import ProviderChangelogParser
        
        parser = ProviderChangelogParser()
        
        # Test version comparison
        assert parser._parse_version('5.30.0') == (5, 30, 0)
        assert parser._parse_version('v5.30.0') == (5, 30, 0)
        assert parser._version_less_than('5.0.0', '5.30.0')
        assert not parser._version_less_than('5.30.0', '5.0.0')
    
    def test_version_range_check(self):
        """Test version range checking."""
        from thothctl.services.inventory.changelog_parser import ProviderChangelogParser
        
        parser = ProviderChangelogParser()
        
        # Version in range
        assert parser._is_version_in_range('5.15.0', '5.0.0', '5.30.0')
        
        # Version outside range
        assert not parser._is_version_in_range('4.67.0', '5.0.0', '5.30.0')
        assert not parser._is_version_in_range('6.0.0', '5.0.0', '5.30.0')
    
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
            "* **New Resource:** `aws_bedrock_agent`"
        ]
        
        entries = parser._parse_version_section('5.15.0', sample_section)
        
        # Should have entries
        assert len(entries) > 0
        
        # Check breaking change
        breaking = [e for e in entries if e.type == 'breaking']
        assert len(breaking) > 0
        assert 'aws_instance' in breaking[0].resource_name or 'network_interface' in breaking[0].description
        
        # Check deprecation
        deprecated = [e for e in entries if e.type == 'deprecated']
        assert len(deprecated) > 0
