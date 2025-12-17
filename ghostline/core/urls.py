"""URLs and version constants for Ghostline Studio."""
from __future__ import annotations

import importlib.metadata as importlib_metadata
from pathlib import Path

# Repository and community links
REPO_URL = "https://github.com/cowboydaniel/Ghostline-Studio"
DOCS_URL = f"{REPO_URL}#readme"
FEATURE_REQUEST_URL = f"{REPO_URL}/issues/new/choose"
COMMUNITY_URL = f"{REPO_URL}/discussions"
RELEASES_URL = f"{REPO_URL}/releases"
CHANGELOG_URL = RELEASES_URL

# API endpoints
GITHUB_API_RELEASES = "https://api.github.com/repos/cowboydaniel/Ghostline-Studio/releases/latest"


def get_app_version() -> str:
    """Get the current application version."""
    # Try to read from pyproject.toml first (works after updates)
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        pyproject_path = project_root / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            for line in content.split("\n"):
                if line.strip().startswith("version"):
                    # Extract version from "version = "0.1.0""
                    version = line.split("=", 1)[1].strip().strip('"\'')
                    if version:
                        return version
    except Exception:
        pass

    # Fallback to importlib metadata (for pip-installed packages)
    try:
        return importlib_metadata.version("ghostline")
    except Exception:
        return "unknown"
