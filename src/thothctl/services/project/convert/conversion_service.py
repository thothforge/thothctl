import logging

from ..create_terramate.manage_terramate_stacks import TerramateStackManager
from .project_converter import (
    ProjectConversionConfig,
    ProjectConverter,
    ProjectTemplateConverter,
    TerramateConverter,
)


class ProjectConversionService:
    """Service for handling project conversions."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def convert_project(self, config: ProjectConversionConfig) -> None:
        """
        Convert project based on configuration.

        Args:
            config: Project conversion configuration
        """
        try:
            converter = self._get_converter(config)
            converter.convert()
        except Exception as e:
            self.logger.error(f"Project conversion failed: {e}")
            raise

    def _get_converter(self, config: ProjectConversionConfig) -> ProjectConverter:
        """Get appropriate converter based on configuration."""

        if config.make_project or config.make_template:
            return ProjectTemplateConverter(config)
        elif config.make_terramate:
            return TerramateConverter(config, TerramateStackManager())
        else:
            raise ValueError("Invalid conversion configuration")
