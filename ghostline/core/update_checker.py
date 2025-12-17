"""Update checker for Ghostline Studio using GitHub API."""
from __future__ import annotations

import json
import logging
from typing import Any

from ghostline.core.urls import GITHUB_API_RELEASES, get_app_version

logger = logging.getLogger(__name__)


class UpdateChecker:
    """Checks for new releases from GitHub."""

    def __init__(self) -> None:
        self.current_version = get_app_version()

    def check_for_updates(self) -> dict[str, Any] | None:
        """Check GitHub for the latest release.

        Returns:
            dict with 'update_available', 'current_version', 'latest_version', 'release_url'
            or None if check fails
        """
        try:
            import urllib.request
            import urllib.error

            try:
                with urllib.request.urlopen(GITHUB_API_RELEASES, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))

                    latest_version = data.get("tag_name", "").lstrip("v")
                    if not latest_version:
                        return None

                    current = self._parse_version(self.current_version)
                    latest = self._parse_version(latest_version)

                    update_available = latest > current

                    return {
                        "update_available": update_available,
                        "current_version": self.current_version,
                        "latest_version": latest_version,
                        "release_url": data.get("html_url"),
                        "release_name": data.get("name"),
                        "release_body": data.get("body", ""),
                    }
            except urllib.error.URLError as e:
                logger.warning(f"Network error checking for updates: {e}")
                return None
            except urllib.error.HTTPError as e:
                logger.warning(f"HTTP error checking for updates: {e}")
                return None

        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return None

    def _parse_version(self, version: str) -> tuple[int, ...]:
        """Parse semantic version string to tuple for comparison.

        Args:
            version: Version string like "1.2.3" or "unknown"

        Returns:
            Tuple of integers for comparison (e.g., (1, 2, 3))
        """
        if version == "unknown":
            return (0,)

        try:
            # Handle versions like "1.2.3-beta" by taking only the numeric part
            parts = version.split("-")[0].split(".")
            return tuple(int(p) for p in parts if p.isdigit())
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse version: {version}")
            return (0,)
