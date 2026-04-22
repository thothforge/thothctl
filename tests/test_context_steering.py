"""Unit tests for --context flag: copy spec/architecture files into .kiro/steering."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from thothctl.services.init.project.project import ProjectService


@pytest.fixture
def svc():
    s = ProjectService()
    s.ui = MagicMock()
    return s


class TestCopyContextToSteering:
    """Test copy_context_to_steering method."""

    def test_single_md_file(self, svc, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        src = tmp_path / "infra.md"
        src.write_text("# My infra requirements")

        svc.copy_context_to_steering(project, str(src))

        dest = project / ".kiro" / "steering" / "infra.md"
        assert dest.exists()
        assert dest.read_text() == "# My infra requirements"
        svc.ui.print_success.assert_called_once()

    def test_folder_with_multiple_files(self, svc, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        specs = tmp_path / "specs"
        specs.mkdir()
        (specs / "arch.md").write_text("# Architecture")
        (specs / "api.yaml").write_text("openapi: 3.0.0")
        (specs / "notes.txt").write_text("notes")
        (specs / "image.png").write_bytes(b"\x89PNG")  # should be skipped

        svc.copy_context_to_steering(project, str(specs))

        steering = project / ".kiro" / "steering"
        assert (steering / "arch.md").exists()
        assert (steering / "api.yaml").exists()
        assert (steering / "notes.txt").exists()
        assert not (steering / "image.png").exists()

    def test_creates_steering_dir_if_missing(self, svc, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        src = tmp_path / "spec.md"
        src.write_text("spec")

        svc.copy_context_to_steering(project, str(src))

        assert (project / ".kiro" / "steering").is_dir()

    def test_preserves_existing_steering_files(self, svc, tmp_path):
        project = tmp_path / "my-project"
        steering = project / ".kiro" / "steering"
        steering.mkdir(parents=True)
        (steering / "product.md").write_text("# Existing product doc")

        src = tmp_path / "custom.md"
        src.write_text("# Custom spec")

        svc.copy_context_to_steering(project, str(src))

        assert (steering / "product.md").read_text() == "# Existing product doc"
        assert (steering / "custom.md").read_text() == "# Custom spec"

    def test_nonexistent_path_prints_error(self, svc, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()

        svc.copy_context_to_steering(project, "/does/not/exist")

        svc.ui.print_error.assert_called_once()
        assert not (project / ".kiro" / "steering").exists()

    def test_empty_folder_copies_nothing(self, svc, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        empty = tmp_path / "empty"
        empty.mkdir()

        svc.copy_context_to_steering(project, str(empty))

        steering = project / ".kiro" / "steering"
        assert steering.is_dir()
        assert list(steering.iterdir()) == []

    def test_yml_extension_supported(self, svc, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        specs = tmp_path / "specs"
        specs.mkdir()
        (specs / "config.yml").write_text("key: value")

        svc.copy_context_to_steering(project, str(specs))

        assert (project / ".kiro" / "steering" / "config.yml").exists()
