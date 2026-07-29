"""CDK construct library parsers for inventory management.

Supports TypeScript (npm) and Python (pip/poetry) CDK projects.
Detects construct dependencies, checks for latest versions, and
produces CycloneDX-compatible component data.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class ConstructDependency:
    """A CDK construct library dependency."""

    name: str
    version: str
    latest_version: Optional[str] = None
    registry: str = ""  # npm, pypi
    scope: str = ""  # @myorg, aws-cdk-lib, etc.
    is_cdk_related: bool = True
    is_outdated: bool = False
    days_since_update: Optional[int] = None
    integrity_hash: Optional[str] = None
    source_file: str = ""
    purl: str = ""  # Package URL


@dataclass
class CDKInventoryResult:
    """Result of CDK inventory scan."""

    language: str
    project_name: str
    dependencies: List[ConstructDependency] = field(default_factory=list)
    total_constructs: int = 0
    outdated_count: int = 0
    up_to_date_count: int = 0
    internal_count: int = 0


class LanguageParser(ABC):
    """Base class for language-specific CDK dependency parsers."""

    @abstractmethod
    def detect(self, directory: Path) -> bool:
        """Detect if this parser applies to the given directory."""
        ...

    @abstractmethod
    def parse_dependencies(self, directory: Path) -> List[ConstructDependency]:
        """Parse CDK construct dependencies from project files."""
        ...

    @abstractmethod
    def check_latest_versions(
        self, deps: List[ConstructDependency]
    ) -> List[ConstructDependency]:
        """Check registry for latest versions of each dependency."""
        ...


# ── CDK Construct Patterns ─────────────────────────────────────────────────

# Patterns that indicate a package is CDK-related
CDK_PATTERNS = [
    r"^aws-cdk-lib$",
    r"^@aws-cdk/",
    r"^@aws-cdk-containers/",
    r"^cdk-",
    r"^constructs$",
    r"^cdk-nag$",
    r"^@cdklabs/",
    r"^@aws-solutions-constructs/",
]

# Patterns for internal/org packages (always CDK-related in a CDK project)
INTERNAL_PATTERNS = [
    r"^@[a-z][a-z0-9-]*/cdk-",  # @myorg/cdk-*
    r"^@[a-z][a-z0-9-]*/constructs-",  # @myorg/constructs-*
]


def is_cdk_package(name: str) -> bool:
    """Check if a package name is CDK-related."""
    for pattern in CDK_PATTERNS + INTERNAL_PATTERNS:
        if re.match(pattern, name):
            return True
    return False


def is_internal_package(name: str) -> bool:
    """Check if a package is from an internal org (scoped @org/)."""
    # Scoped packages not from aws/cdklabs are likely internal
    if name.startswith("@"):
        scope = name.split("/")[0]
        if scope not in (
            "@aws-cdk",
            "@aws-cdk-containers",
            "@cdklabs",
            "@aws-solutions-constructs",
            "@types",
        ):
            return True
    return False


# ── TypeScript/npm Parser ──────────────────────────────────────────────────


class TypeScriptParser(LanguageParser):
    """Parse CDK construct dependencies from npm/TypeScript projects."""

    NPM_REGISTRY = "https://registry.npmjs.org"

    def detect(self, directory: Path) -> bool:
        """Detect TypeScript CDK project."""
        return (directory / "package.json").exists() and (
            directory / "cdk.json"
        ).exists()

    def parse_dependencies(self, directory: Path) -> List[ConstructDependency]:
        """Parse package.json and package-lock.json for CDK constructs."""
        deps = []
        package_json = directory / "package.json"
        lock_file = directory / "package-lock.json"

        if not package_json.exists():
            return deps

        try:
            pkg_data = json.loads(package_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to parse package.json: {e}")
            return deps

        # Load lock file for resolved versions and integrity hashes
        lock_data = {}
        if lock_file.exists():
            try:
                lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("Could not parse package-lock.json")

        # Collect dependencies and devDependencies
        all_deps = {}
        all_deps.update(pkg_data.get("dependencies", {}))
        all_deps.update(pkg_data.get("devDependencies", {}))

        for name, version_constraint in all_deps.items():
            if not is_cdk_package(name):
                continue

            # Resolve actual version from lock file
            resolved_version = self._resolve_from_lock(name, lock_data)
            declared_version = version_constraint.lstrip("^~>=")
            version = resolved_version or declared_version

            # Get integrity hash from lock file
            integrity = self._get_integrity(name, lock_data)

            scope = name.split("/")[0] if "/" in name else ""

            deps.append(
                ConstructDependency(
                    name=name,
                    version=version,
                    registry="npm",
                    scope=scope,
                    is_cdk_related=True,
                    integrity_hash=integrity,
                    source_file="package.json",
                    purl=f"pkg:npm/{name}@{version}",
                )
            )

        return deps

    def check_latest_versions(
        self, deps: List[ConstructDependency]
    ) -> List[ConstructDependency]:
        """Check npm registry for latest versions."""
        for dep in deps:
            if is_internal_package(dep.name):
                dep.latest_version = dep.version  # Can't check private registry
                dep.is_outdated = False
                continue

            try:
                # URL-encode scoped packages
                pkg_name = dep.name.replace("/", "%2F")
                resp = requests.get(
                    f"{self.NPM_REGISTRY}/{pkg_name}/latest",
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    dep.latest_version = data.get("version", dep.version)
                    dep.is_outdated = dep.version != dep.latest_version
                else:
                    dep.latest_version = dep.version
            except requests.RequestException:
                dep.latest_version = dep.version
                logger.debug(f"Failed to check npm for {dep.name}")

        return deps

    def _resolve_from_lock(self, name: str, lock_data: Dict) -> Optional[str]:
        """Resolve actual installed version from package-lock.json."""
        # npm lockfile v2/v3 format
        packages = lock_data.get("packages", {})
        key = f"node_modules/{name}"
        if key in packages:
            return packages[key].get("version")

        # npm lockfile v1 format
        dependencies = lock_data.get("dependencies", {})
        if name in dependencies:
            return dependencies[name].get("version")

        return None

    def _get_integrity(self, name: str, lock_data: Dict) -> Optional[str]:
        """Get integrity hash from lock file."""
        packages = lock_data.get("packages", {})
        key = f"node_modules/{name}"
        if key in packages:
            return packages[key].get("integrity")

        dependencies = lock_data.get("dependencies", {})
        if name in dependencies:
            return dependencies[name].get("integrity")

        return None


# ── Python Parser ──────────────────────────────────────────────────────────


class PythonParser(LanguageParser):
    """Parse CDK construct dependencies from Python projects."""

    PYPI_API = "https://pypi.org/pypi"

    # Python CDK package patterns
    PYTHON_CDK_PATTERNS = [
        r"^aws-cdk-lib$",
        r"^aws-cdk\.",
        r"^cdk-",
        r"^constructs$",
        r"^cdk-nag$",
        r"^cdklabs\.",
    ]

    def detect(self, directory: Path) -> bool:
        """Detect Python CDK project."""
        has_cdk = (directory / "cdk.json").exists()
        has_python = (
            (directory / "requirements.txt").exists()
            or (directory / "pyproject.toml").exists()
            or (directory / "setup.py").exists()
        )
        return has_cdk and has_python

    def parse_dependencies(self, directory: Path) -> List[ConstructDependency]:
        """Parse Python dependencies from requirements.txt or pyproject.toml."""
        deps = []

        # Try pyproject.toml first (modern Python)
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            deps.extend(self._parse_pyproject(pyproject))

        # Fallback to requirements.txt
        if not deps:
            requirements = directory / "requirements.txt"
            if requirements.exists():
                deps.extend(self._parse_requirements(requirements))

        # Also check requirements-dev.txt
        req_dev = directory / "requirements-dev.txt"
        if req_dev.exists():
            deps.extend(self._parse_requirements(req_dev))

        return deps

    def check_latest_versions(
        self, deps: List[ConstructDependency]
    ) -> List[ConstructDependency]:
        """Check PyPI for latest versions."""
        for dep in deps:
            if is_internal_package(dep.name):
                dep.latest_version = dep.version
                dep.is_outdated = False
                continue

            try:
                resp = requests.get(
                    f"{self.PYPI_API}/{dep.name}/json",
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    dep.latest_version = data.get("info", {}).get(
                        "version", dep.version
                    )
                    dep.is_outdated = dep.version != dep.latest_version
                else:
                    dep.latest_version = dep.version
            except requests.RequestException:
                dep.latest_version = dep.version
                logger.debug(f"Failed to check PyPI for {dep.name}")

        return deps

    def _is_python_cdk_package(self, name: str) -> bool:
        """Check if a Python package is CDK-related."""
        normalized = name.lower().replace("-", "-")
        for pattern in self.PYTHON_CDK_PATTERNS:
            if re.match(pattern, normalized):
                return True
        # Internal packages (custom namespaces)
        if "." in name and not name.startswith("aws"):
            return True  # e.g., myorg.cdk_constructs
        return False

    def _parse_requirements(self, filepath: Path) -> List[ConstructDependency]:
        """Parse requirements.txt format."""
        deps = []
        try:
            lines = filepath.read_text(encoding="utf-8").splitlines()
        except OSError:
            return deps

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Parse: package==version, package>=version, package~=version
            match = re.match(r"^([a-zA-Z0-9_.-]+)\s*([><=~!]+)\s*([\d.]+)", line)
            if match:
                name = match.group(1)
                version = match.group(3)

                if not self._is_python_cdk_package(name):
                    continue

                deps.append(
                    ConstructDependency(
                        name=name,
                        version=version,
                        registry="pypi",
                        is_cdk_related=True,
                        source_file=filepath.name,
                        purl=f"pkg:pypi/{name}@{version}",
                    )
                )

        return deps

    def _parse_pyproject(self, filepath: Path) -> List[ConstructDependency]:
        """Parse pyproject.toml for CDK dependencies."""
        deps = []
        try:
            import toml

            data = toml.load(filepath)
        except Exception:
            return deps

        # Check [project.dependencies] (PEP 621)
        project_deps = data.get("project", {}).get("dependencies", [])

        # Check [tool.poetry.dependencies] (Poetry)
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})

        # Process PEP 621 format: ["aws-cdk-lib>=2.100.0"]
        for dep_str in project_deps:
            match = re.match(r"^([a-zA-Z0-9_.-]+)\s*([><=~!]+)\s*([\d.]+)", dep_str)
            if match:
                name = match.group(1)
                version = match.group(3)
                if self._is_python_cdk_package(name):
                    deps.append(
                        ConstructDependency(
                            name=name,
                            version=version,
                            registry="pypi",
                            is_cdk_related=True,
                            source_file="pyproject.toml",
                            purl=f"pkg:pypi/{name}@{version}",
                        )
                    )

        # Process Poetry format: {package = "^version"}
        for name, version_spec in poetry_deps.items():
            if isinstance(version_spec, str):
                version = version_spec.lstrip("^~>=")
            elif isinstance(version_spec, dict):
                version = version_spec.get("version", "").lstrip("^~>=")
            else:
                continue

            if version and self._is_python_cdk_package(name):
                deps.append(
                    ConstructDependency(
                        name=name,
                        version=version,
                        registry="pypi",
                        is_cdk_related=True,
                        source_file="pyproject.toml",
                        purl=f"pkg:pypi/{name}@{version}",
                    )
                )

        return deps


# ── CDK Project Detector & Orchestrator ────────────────────────────────────

AVAILABLE_PARSERS: List[LanguageParser] = [
    TypeScriptParser(),
    PythonParser(),
]


def detect_cdk_project(directory: Path) -> Optional[LanguageParser]:
    """Detect CDK project type and return appropriate parser."""
    if not (directory / "cdk.json").exists():
        return None

    for parser in AVAILABLE_PARSERS:
        if parser.detect(directory):
            return parser

    return None


def run_cdk_inventory(
    directory: Path, check_versions: bool = True
) -> Optional[CDKInventoryResult]:
    """Run CDK construct inventory for a project.

    Returns None if not a CDK project.
    """
    parser = detect_cdk_project(directory)
    if not parser:
        return None

    language = "typescript" if isinstance(parser, TypeScriptParser) else "python"
    project_name = directory.name

    # Parse dependencies
    deps = parser.parse_dependencies(directory)
    if not deps:
        return CDKInventoryResult(
            language=language,
            project_name=project_name,
        )

    # Check latest versions if requested
    if check_versions:
        deps = parser.check_latest_versions(deps)

    # Build result
    outdated = sum(1 for d in deps if d.is_outdated)
    internal = sum(1 for d in deps if is_internal_package(d.name))

    return CDKInventoryResult(
        language=language,
        project_name=project_name,
        dependencies=deps,
        total_constructs=len(deps),
        outdated_count=outdated,
        up_to_date_count=len(deps) - outdated,
        internal_count=internal,
    )
