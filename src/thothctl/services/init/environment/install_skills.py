"""Dynamic installation of AI agent skills from upstream Git repositories.

Skills are reusable knowledge packages that live under ``.kiro/skills/<name>/``.
Historically they were baked into every scaffold template, which caused drift
between a scaffold's embedded copy and the canonical upstream repository.

This module installs skills *dynamically* at ``init`` time from their upstream
GitHub repositories (mirroring ``install_aidlc_rules``), so the canonical repo
is the single source of truth.

Only skills that have a known upstream repository are dynamically installable.
Skills authored by third parties or carrying scaffold-local modifications
(e.g. ``terraform-skill``) are intentionally NOT in the registry — they stay
bundled in the scaffold and are never overwritten by this installer.
"""

import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import requests
from colorama import Fore

# ---------------------------------------------------------------------------
# Skill registry
# ---------------------------------------------------------------------------
# Maps a skill name to its upstream source. Add an entry here when a skill gets
# a canonical GitHub repository so it can be installed dynamically.
#
#   repo       : "owner/name" GitHub repository slug.
#   ref        : git ref (branch/tag) to download when no release is published.
#   use_release: if True, prefer the latest GitHub release asset/zipball,
#                falling back to ``ref`` when there is no release.
#   subdir     : path *inside* the downloaded archive that contains the skill
#                payload (SKILL.md + references/). "" means the archive root.
#
# NOTE ON INTENTIONAL OMISSIONS:
#   - terraform-skill        → third-party (Anton Babenko), scaffold-local mods; DO NOT auto-install.
#   - thothctl-framework     → no upstream repo yet; scaffold-bundled.
#   - iac-versioning-commits → no upstream repo yet; scaffold-bundled.
SKILL_REGISTRY: Dict[str, Dict] = {
    "devsecops": {
        "repo": "thothforge/thothctl-devsecops-skill",
        "ref": "main",
        "use_release": True,
        "subdir": "",
    },
}


def available_skills() -> List[str]:
    """Return the names of skills that can be installed dynamically."""
    return sorted(SKILL_REGISTRY.keys())


def _resolve_zip_url(repo: str, ref: str, use_release: bool) -> Optional[str]:
    """Resolve a downloadable zip URL for a repo.

    Prefers the latest release when ``use_release`` is set and a release exists;
    otherwise falls back to the branch/tag zipball.
    """
    if use_release:
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            resp = requests.get(api_url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith(".zip"):
                        return asset["browser_download_url"]
                if data.get("zipball_url"):
                    return data["zipball_url"]
        except requests.RequestException:
            # Fall through to branch zipball.
            pass

    # Branch/tag zipball (works even without any published release).
    return f"https://api.github.com/repos/{repo}/zipball/{ref}"


def _find_skill_payload(extract_root: Path, subdir: str) -> Optional[Path]:
    """Locate the directory holding SKILL.md inside an extracted archive.

    GitHub zipballs wrap everything in a single top-level ``<owner>-<repo>-<sha>/``
    directory, so we search for SKILL.md rather than assuming a fixed depth.
    """
    # Enter the single wrapper directory produced by GitHub zipballs, if present.
    entries = [p for p in extract_root.iterdir() if p.is_dir()]
    search_root = entries[0] if len(entries) == 1 else extract_root

    if subdir:
        candidate = search_root / subdir
        return candidate if (candidate / "SKILL.md").exists() else None

    # subdir == "" → the skill payload is at the archive root.
    if (search_root / "SKILL.md").exists():
        return search_root

    # Fallback: first directory that directly contains a SKILL.md.
    for skill_md in search_root.rglob("SKILL.md"):
        return skill_md.parent
    return None


def install_skill(skill_name: str, target_dir: str = ".") -> bool:
    """Install a single skill from its upstream repo into ``.kiro/skills/<name>/``.

    :param skill_name: Registry key (see ``SKILL_REGISTRY``).
    :param target_dir: Project root directory (where ``.kiro/`` lives).
    :return: True on success, False otherwise.
    """
    entry = SKILL_REGISTRY.get(skill_name)
    if not entry:
        print(
            f"{Fore.YELLOW}⚠️  Skill '{skill_name}' has no upstream repository; "
            f"skipping dynamic install (it is bundled in the scaffold).{Fore.RESET}"
        )
        return False

    repo = entry["repo"]
    ref = entry.get("ref", "main")
    use_release = entry.get("use_release", False)
    subdir = entry.get("subdir", "")

    print(f"{Fore.MAGENTA}Installing skill '{skill_name}' from {repo}...{Fore.RESET}")

    zip_url = _resolve_zip_url(repo, ref, use_release)
    if not zip_url:
        print(f"{Fore.RED}❌ Could not resolve a download URL for {repo}{Fore.RESET}")
        return False

    try:
        zip_response = requests.get(zip_url, timeout=60, allow_redirects=True)
        zip_response.raise_for_status()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
                zf.extractall(tmp_path)

            payload = _find_skill_payload(tmp_path, subdir)
            if not payload:
                print(
                    f"{Fore.RED}❌ Could not find SKILL.md in {repo} "
                    f"(subdir='{subdir or '<root>'}'){Fore.RESET}"
                )
                return False

            dst = Path(target_dir) / ".kiro" / "skills" / skill_name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.rmtree(dst)
            # Copy payload contents into .kiro/skills/<skill_name>/
            shutil.copytree(payload, dst)
            # Drop any VCS metadata that may have ridden along.
            for junk in (".git", ".github"):
                junk_path = dst / junk
                if junk_path.exists():
                    shutil.rmtree(junk_path, ignore_errors=True)

        print(
            f"{Fore.GREEN}  ✅ Installed skill '{skill_name}' → "
            f".kiro/skills/{skill_name}/{Fore.RESET}"
        )
        return True

    except requests.RequestException as e:
        print(f"{Fore.RED}❌ Failed to download skill '{skill_name}': {e}{Fore.RESET}")
        return False
    except (zipfile.BadZipFile, OSError) as e:
        print(f"{Fore.RED}❌ Failed to extract skill '{skill_name}': {e}{Fore.RESET}")
        return False


def install_skills(skill_names: List[str], target_dir: str = ".") -> Dict[str, bool]:
    """Install multiple skills. Returns a map of skill_name → success."""
    results: Dict[str, bool] = {}
    for name in skill_names:
        results[name] = install_skill(name, target_dir=target_dir)
    return results


def resolve_requested_skills(requested: str) -> List[str]:
    """Translate a CLI ``--with-skills`` value into concrete registry names.

    Accepts:
      - "all"                   → every skill in the registry
      - "none"/"false"/"off"/"" → nothing (opt-out)
      - "devsecops,foo"         → comma-separated explicit list
    Unknown names are warned about and dropped.
    """
    if not requested:
        return []
    normalized = requested.strip().lower()
    if normalized in ("none", "false", "off", "no"):
        return []
    if normalized == "all":
        return available_skills()

    names = [n.strip() for n in requested.split(",") if n.strip()]
    valid, unknown = [], []
    for n in names:
        (valid if n in SKILL_REGISTRY else unknown).append(n)
    if unknown:
        print(
            f"{Fore.YELLOW}⚠️  Unknown/undistributable skill(s): {', '.join(unknown)}. "
            f"Available: {', '.join(available_skills())}{Fore.RESET}"
        )
    return valid
