"""Unit tests for IaC command cost analysis integration."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from thothctl.commands.check.commands.iac import CheckIaCCommand
from thothctl.services.check.project.cost.models.cost_models import CostAnalysis, ResourceCost, CostAction


class TestIaCCostAnalysisIntegration:
    """Test cost analysis integration in IaC command"""
    
    @pytest.fixture
    def mock_iac_command(self):
        """Mock IaC command instance"""
        command = CheckIaCCommand()
        command.ui = Mock()
        command.logger = Mock()
        command.console = Mock()
        return command
    
    @pytest.fixture
    def sample_cost_analysis(self):
        """Sample cost analysis result"""
        resource_cost = ResourceCost(
            resource_address="aws_instance.test",
            resource_type="aws_instance",
            service_name="EC2",
            region="us-east-1",
            action=CostAction.CREATE,
            hourly_cost=0.10,
            monthly_cost=72.0,
            annual_cost=864.0,
            pricing_details={"instance_type": "t3.micro"},
            confidence_level="high"
        )
        
        return CostAnalysis(
            total_monthly_cost=72.0,
            total_annual_cost=864.0,
            resource_costs=[resource_cost],
            cost_breakdown_by_service={"EC2": 72.0},
            cost_breakdown_by_action={"create": 72.0},
            recommendations=["Consider Reserved Instances"],
            warnings=[],
            analysis_metadata={"region": "us-east-1", "api_available": True}
        )
    
    def test_cost_analysis_check_type_supported(self, mock_iac_command):
        """Test that cost-analysis is in supported check types"""
        assert "cost-analysis" in mock_iac_command.supported_check_types
    
    @patch('thothctl.commands.check.commands.iac.CheckIaCCommand._find_tfplan_files')
    @patch('thothctl.services.check.project.cost.cost_analyzer.CostAnalyzer')
    def test_run_cost_analysis_success(self, mock_analyzer_class, mock_find_files, 
                                     mock_iac_command, sample_cost_analysis):
        """Test successful cost analysis execution"""
        # Setup mocks
        mock_find_files.return_value = ['tfplan.json']
        mock_analyzer = Mock()
        mock_analyzer.analyze_terraform_plan.return_value = sample_cost_analysis
        mock_analyzer_class.return_value = mock_analyzer
        
        # Execute
        result = mock_iac_command._run_cost_analysis('/test/dir', recursive=True)
        
        # Verify
        assert result is True
        mock_find_files.assert_called_once_with('/test/dir', True)
        mock_analyzer.analyze_terraform_plan.assert_called_once_with('tfplan.json')
        mock_iac_command.ui.print_warning.assert_not_called()
    
    @patch('thothctl.commands.check.commands.iac.CheckIaCCommand._find_tfplan_files')
    def test_run_cost_analysis_no_tfplan_files(self, mock_find_files, mock_iac_command):
        """Test cost analysis when no tfplan files found"""
        # Setup mocks
        mock_find_files.return_value = []
        
        # Execute
        result = mock_iac_command._run_cost_analysis('/test/dir')
        
        # Verify
        assert result is False
        mock_iac_command.ui.print_warning.assert_called_once()
    
    @patch('thothctl.commands.check.commands.iac.CheckIaCCommand._find_tfplan_files')
    @patch('thothctl.services.check.project.cost.cost_analyzer.CostAnalyzer')
    def test_run_cost_analysis_exception(self, mock_analyzer_class, mock_find_files, 
                                       mock_iac_command):
        """Test cost analysis with exception"""
        # Setup mocks
        mock_find_files.return_value = ['tfplan.json']
        mock_analyzer = Mock()
        mock_analyzer.analyze_terraform_plan.side_effect = Exception("Test error")
        mock_analyzer_class.return_value = mock_analyzer
        
        # Execute
        result = mock_iac_command._run_cost_analysis('/test/dir')
        
        # Verify
        assert result is False
        mock_iac_command.logger.error.assert_called_once()
        mock_iac_command.ui.print_error.assert_called_once()
    
    def test_display_cost_analysis(self, mock_iac_command, sample_cost_analysis):
        """Test cost analysis display"""
        # Execute
        mock_iac_command._display_cost_analysis(sample_cost_analysis)
        
        # Verify console.print was called multiple times for different sections
        assert mock_iac_command.console.print.call_count > 5
        
        # Check that key information is displayed
        print_calls = [call.args[0] for call in mock_iac_command.console.print.call_calls]
        print_text = ' '.join(str(call) for call in print_calls)
        
        assert '$72.00' in print_text  # Monthly cost
        assert 'EC2' in print_text     # Service name
        assert 'create' in print_text  # Action type
