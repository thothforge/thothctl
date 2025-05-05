import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Final, Optional

import os

from ....common.common import create_info_project
from ....core.integrations.azure_devops.get_azure_devops import get_pattern_from_azure
from ....services.generate.create_template.create_template import create_project
from ...project.convert.get_project_data import (
    get_project_props,
    walk_folder_replace,
)
from ...project.convert.set_project_parameters import set_project_conf


class ProjectService:
    AZURE_DEVOPS_URL: Final = "https://dev.azure.com"
    DEFAULT_CLOUD_PROVIDER: Final = "aws"
    DEFAULT_VCS_SERVICE: Final = "azure_repos"

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def initialize_project(
        self, project_name: str, project_type: str = "terraform", reuse=False
    ) -> None:
        """Initialize the basic project structure"""
        self.logger.info(f"Initializing project: {project_name}")
        create_info_project(project_name=project_name)
        self.logger.info(f"Project {project_name} initialized successfully")

        if not reuse:
            create_project(project_name=project_name, project_type=project_type)

    def setup_project_config(self, project_name: str, space: Optional[str] = None) -> None:
        """Setup project configuration"""
        project_props = get_project_props(
            project_name=project_name,
            cloud_provider=self.DEFAULT_CLOUD_PROVIDER,
            remote_bkd_cloud_provider=self.DEFAULT_CLOUD_PROVIDER,
        )
        set_project_conf(
            project_name=project_name,
            project_properties=project_props,
            space=space,
        )

    def setup_azure_repos(
        self,
        project_name: str,
        project_path: Path,
        az_org_name: str,
        r_list: bool,
        pat: str,
        space: Optional[str] = None,
    ) -> None:
        """Setup Azure Repos configuration"""
        org_url = f"{self.AZURE_DEVOPS_URL}/{az_org_name}/"
        action = "list" if r_list else "reuse"

        repo_meta = get_pattern_from_azure(
            pat=pat,
            org_url=org_url,
            directory=project_name,
            action=action,
        )

        project_props = get_project_props(
            project_name=project_name,
            cloud_provider=self.DEFAULT_CLOUD_PROVIDER,
            remote_bkd_cloud_provider=self.DEFAULT_CLOUD_PROVIDER,
            directory=project_path,
        )

        with self._change_directory(project_path):
            walk_folder_replace(
                directory=Path("."),
                project_properties=project_props,
                project_name=project_name,
            )

            set_project_conf(
                project_properties=project_props,
                project_name=project_name,
                directory=Path("."),
                repo_metadata=repo_meta,
                space=space,
            )

    @staticmethod
    @contextmanager
    def _change_directory(path: Path):
        """Safely change directory and return to original"""
        original_dir = Path.cwd()
        try:
            os.chdir(path)
            yield
        finally:
            os.chdir(original_dir)
