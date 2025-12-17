"""URLs and version constants for Ghostline Studio."""
from __future__ import annotations

import importlib.metadata as importlib_metadata

# Repository and community links
REPO_URL = "https://github.com/ghostline-studio/Ghostline-Studio"
DOCS_URL = f"{REPO_URL}#readme"
FEATURE_REQUEST_URL = f"{REPO_URL}/issues/new/choose"
COMMUNITY_URL = f"{REPO_URL}/discussions"
RELEASES_URL = f"{REPO_URL}/releases"
CHANGELOG_URL = RELEASES_URL

# API endpoints
GITHUB_API_RELEASES = "https://api.github.com/repos/ghostline-studio/Ghostline-Studio/releases/latest"


def get_app_version() -> str:
    """Get the current application version."""
    try:
        return importlib_metadata.version("ghostline")
    except Exception:
        return "unknown"
