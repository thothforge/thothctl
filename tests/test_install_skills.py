"""Tests for dynamic skill installation (install_skills)."""

import io
import zipfile
from unittest.mock import MagicMock, patch

from thothctl.services.init.environment import install_skills


def _make_github_zipball(files: dict) -> bytes:
    """Build an in-memory zip that mimics a GitHub zipball.

    GitHub wraps everything under a single top-level ``<owner>-<repo>-<sha>/``
    directory. ``files`` maps archive-relative paths (under that wrapper) to
    their text content.
    """
    buf = io.BytesIO()
    wrapper = "thothforge-thothctl-devsecops-skill-abc1234"
    with zipfile.ZipFile(buf, "w") as zf:
        for rel, content in files.items():
            zf.writestr(f"{wrapper}/{rel}", content)
    return buf.getvalue()


def test_resolve_requested_skills_all():
    assert install_skills.resolve_requested_skills("all") == install_skills.available_skills()


def test_resolve_requested_skills_explicit_and_unknown():
    # Known skill kept, unknown dropped.
    result = install_skills.resolve_requested_skills("devsecops,does-not-exist")
    assert result == ["devsecops"]


def test_resolve_requested_skills_empty():
    assert install_skills.resolve_requested_skills("") == []
    assert install_skills.resolve_requested_skills(None) == []


def test_resolve_requested_skills_optout_keywords():
    for word in ("none", "None", "NONE", "false", "off", "no"):
        assert install_skills.resolve_requested_skills(word) == [], word


def test_install_skill_unknown_returns_false(tmp_path):
    assert install_skills.install_skill("terraform-skill", target_dir=str(tmp_path)) is False
    # Nothing should have been written.
    assert not (tmp_path / ".kiro").exists()


def test_install_skill_devsecops_from_zipball(tmp_path):
    """install_skill downloads, finds SKILL.md, and copies into .kiro/skills/<name>/."""
    zip_bytes = _make_github_zipball(
        {
            "SKILL.md": "# DevSecOps Skill\n",
            "references/sdlc_phases.md": "phases\n",
            "references/command_reference.md": "commands\n",
            # Simulate VCS junk that must be stripped.
            ".github/workflows/ci.yml": "ci\n",
        }
    )

    fake_release = MagicMock()
    fake_release.status_code = 404  # force zipball fallback (no release)

    fake_zip = MagicMock()
    fake_zip.content = zip_bytes
    fake_zip.raise_for_status = MagicMock()

    def fake_get(url, *args, **kwargs):
        if "releases/latest" in url:
            return fake_release
        return fake_zip

    with patch.object(install_skills.requests, "get", side_effect=fake_get):
        ok = install_skills.install_skill("devsecops", target_dir=str(tmp_path))

    assert ok is True
    dst = tmp_path / ".kiro" / "skills" / "devsecops"
    assert (dst / "SKILL.md").exists()
    assert (dst / "references" / "sdlc_phases.md").exists()
    assert (dst / "references" / "command_reference.md").exists()
    # VCS junk stripped.
    assert not (dst / ".github").exists()


def test_install_skill_overwrites_existing(tmp_path):
    """Re-installing replaces a stale copy rather than merging into it."""
    dst = tmp_path / ".kiro" / "skills" / "devsecops"
    dst.mkdir(parents=True)
    (dst / "STALE.md").write_text("old")

    zip_bytes = _make_github_zipball({"SKILL.md": "# fresh\n"})
    fake_release = MagicMock()
    fake_release.status_code = 404
    fake_zip = MagicMock()
    fake_zip.content = zip_bytes
    fake_zip.raise_for_status = MagicMock()

    with patch.object(
        install_skills.requests,
        "get",
        side_effect=lambda url, *a, **k: fake_release if "releases/latest" in url else fake_zip,
    ):
        ok = install_skills.install_skill("devsecops", target_dir=str(tmp_path))

    assert ok is True
    assert (dst / "SKILL.md").exists()
    # Stale file from the previous copy must be gone.
    assert not (dst / "STALE.md").exists()
