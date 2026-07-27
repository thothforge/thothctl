"""Unit tests for scan command and ReportConfig."""

from dataclasses import asdict

import pytest

from thothctl.utils.common.create_compliance_html_reports import (
    ComplianceReportGenerator,
    ReportConfig,
)


class TestReportConfig:
    """Test ReportConfig dataclass."""

    def test_default_values(self):
        """Test ReportConfig with default values."""
        config = ReportConfig()
        assert config.encoding == "UTF-8"
        assert config.page_size == "A4"
        assert config.orientation == "Portrait"

    def test_custom_values(self):
        """Test ReportConfig with custom values."""
        config = ReportConfig(
            encoding="UTF-16", page_size="A0", orientation="Landscape"
        )
        assert config.encoding == "UTF-16"
        assert config.page_size == "A0"
        assert config.orientation == "Landscape"

    def test_partial_custom_values(self):
        """Test ReportConfig with partial custom values."""
        config = ReportConfig(page_size="A3")
        assert config.encoding == "UTF-8"
        assert config.page_size == "A3"
        assert config.orientation == "Portrait"

    def test_dataclass_fields(self):
        """Test that ReportConfig is a proper dataclass."""
        config = ReportConfig(page_size="A0", orientation="Landscape")
        config_dict = asdict(config)
        assert "encoding" in config_dict
        assert "page_size" in config_dict
        assert "orientation" in config_dict


class TestComplianceReportGenerator:
    """Test ComplianceReportGenerator initialization."""

    def test_generator_with_default_config(self):
        """Test generator initialization with default config."""
        generator = ComplianceReportGenerator(output_dir="/tmp/reports")
        assert generator.output_dir == "/tmp/reports"
        assert generator.config.encoding == "UTF-8"
        assert generator.config.page_size == "A4"
        assert generator.config.orientation == "Portrait"

    def test_generator_with_custom_config(self):
        """Test generator initialization with custom config."""
        config = ReportConfig(page_size="A0", orientation="Landscape")
        generator = ComplianceReportGenerator(output_dir="/tmp/reports", config=config)
        assert generator.config.page_size == "A0"
        assert generator.config.orientation == "Landscape"

    def test_generator_without_config(self):
        """Test generator creates default config when none provided."""
        generator = ComplianceReportGenerator(output_dir="/tmp/reports")
        assert isinstance(generator.config, ReportConfig)
        assert generator.config.encoding == "UTF-8"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
