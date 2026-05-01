"""Unit tests for template_url fix in upgrade service and metadata creation."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import toml

from thothctl.services.project.upgrade.upgrade_service import ProjectUpgradeService


@pytest.fixture
def upgrade_service():
    return ProjectUpgradeService()


@pytest.fixture
def project_with_metadata(tmp_path):
    """Create a project dir with .thothcf.toml containing origin_metadata."""
    def _create(metadata: dict):
        toml_path = tmp_path / ".thothcf.toml"
        toml_path.write_text(toml.dumps({"origin_metadata": metadata}))
        return tmp_path
    return _create


class TestUpgradeServiceTemplateUrl:
    """Test that upgrade service resolves template_url from metadata correctly."""

    def test_reads_template_url_when_present(self, upgrade_service, project_with_metadata):
        """upgrade should use template_url if it exists."""
        project_path = project_with_metadata({
            "repo_name": "my-template",
            "repo_url": "https://dev.azure.com/org/proj/_git/my-template",
            "template_url": "https://dev.azure.com/org/proj/_git/my-template",
            "commit": "abc123",
            "tag": "v1.0.0",
        })

        with patch.object(upgrade_service, '_clone_template', side_effect=Exception("stop")):
            result = upgrade_service.upgrade_project(project_path)

        # It should have attempted to clone (meaning template_url was found)
        assert result["error"] != "No template_url found in project metadata"

    def test_falls_back_to_repo_url(self, upgrade_service, project_with_metadata):
        """upgrade should fall back to repo_url when template_url is missing."""
        project_path = project_with_metadata({
            "repo_name": "terraform_azdo_mangement_blueprint",
            "repo_url": "https://dev.azure.com/GFT-SE/KE-054129-001/_git/terraform_azdo_mangement_blueprint",
            "commit": "cb29795b95f4ac476baf3955561ab1999b1eb4ae",
            "tag": "",
        })

        with patch.object(upgrade_service, '_clone_template', side_effect=Exception("stop")):
            result = upgrade_service.upgrade_project(project_path)

        # Should NOT fail with "No template_url found"
        assert "No template_url found" not in result.get("error", "")

    def test_fails_when_neither_url_present(self, upgrade_service, project_with_metadata):
        """upgrade should fail if neither template_url nor repo_url exists."""
        project_path = project_with_metadata({
            "repo_name": "some-repo",
            "commit": "abc123",
            "tag": "",
        })

        result = upgrade_service.upgrade_project(project_path)

        assert result["success"] is False
        assert "No template_url found" in result["error"]

    def test_no_metadata_file(self, upgrade_service, tmp_path):
        """upgrade should fail gracefully if .thothcf.toml doesn't exist."""
        result = upgrade_service.upgrade_project(tmp_path)

        assert result["success"] is False
        assert "No project metadata found" in result["error"]


class TestRepoMetaIncludesTemplateUrl:
    """Test that init paths include template_url in repo_meta."""

    def test_azure_clone_repo_includes_template_url(self):
        """clone_repo in get_azure_devops should include template_url."""
        from unittest.mock import patch, MagicMock
        import thothctl.core.integrations.azure_devops.get_azure_devops as azdo

        mock_repo = MagicMock()
        mock_repo.tags = []
        mock_repo.rev_parse.return_value = MagicMock(hexsha="abc123")

        fake_repos = [{"Name": "my-template", "RemoteUrl": "https://dev.azure.com/org/proj/_git/my-template"}]

        with patch.object(azdo, 'get_repos_patterns', return_value=fake_repos), \
             patch.object(azdo.inquirer, 'prompt', return_value={"repository": "my-template"}), \
             patch.object(azdo.git.Repo, 'clone_from', return_value=mock_repo), \
             patch.object(azdo.git.Repo, 'init'), \
             patch.object(azdo.shutil, 'rmtree'), \
             patch.object(azdo.os.path, 'join', return_value="/tmp/.git"):

            result = azdo.clone_repo(
                git_client=MagicMock(),
                project_name="proj",
                path="/tmp/test",
            )

        assert "template_url" in result
        assert result["template_url"] == result["repo_url"]
