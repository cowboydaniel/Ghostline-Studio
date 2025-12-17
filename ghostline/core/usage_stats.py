"""Usage statistics tracking for Ghostline Studio."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from ghostline.core.config import CONFIG_DIR

logger = logging.getLogger(__name__)

STATS_FILE = CONFIG_DIR / "usage_stats.json"


class UsageStatsTracker:
    """Tracks and manages usage statistics for Ghostline."""

    DEFAULT_STATS = {
        "app_launches": 0,
        "total_session_time_seconds": 0,
        "files_opened": 0,
        "ai_requests_count": 0,
        "commands_executed": 0,
        "first_launch_date": None,
        "last_session_start": None,
        "last_session_end": None,
    }

    def __init__(self) -> None:
        self._stats = self._load_stats()
        self._session_start: float | None = None

    def _load_stats(self) -> dict[str, object]:
        """Load stats from persistent storage."""
        if not STATS_FILE.exists():
            return dict(self.DEFAULT_STATS)
        try:
            with STATS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all required fields exist
                for key, value in self.DEFAULT_STATS.items():
                    if key not in data:
                        data[key] = value
                return data
        except Exception as e:
            logger.warning(f"Failed to load usage stats: {e}, using defaults")
            return dict(self.DEFAULT_STATS)

    def save(self) -> None:
        """Save stats to persistent storage."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with STATS_FILE.open("w", encoding="utf-8") as f:
                json.dump(self._stats, f, indent=2)
            logger.debug(f"Usage stats saved to {STATS_FILE}")
        except Exception as e:
            logger.error(f"Failed to save usage stats: {e}")

    def record_app_launch(self) -> None:
        """Record that the app was launched."""
        self._stats["app_launches"] = int(self._stats.get("app_launches", 0)) + 1

        if not self._stats.get("first_launch_date"):
            self._stats["first_launch_date"] = datetime.now().isoformat()

        self._stats["last_session_start"] = datetime.now().isoformat()
        self._session_start = datetime.now().timestamp()
        self.save()

    def record_session_end(self) -> None:
        """Record that a session ended and calculate duration."""
        if self._session_start:
            duration = datetime.now().timestamp() - self._session_start
            current_total = float(self._stats.get("total_session_time_seconds", 0))
            self._stats["total_session_time_seconds"] = current_total + duration

        self._stats["last_session_end"] = datetime.now().isoformat()
        self.save()

    def record_file_opened(self) -> None:
        """Record that a file was opened."""
        self._stats["files_opened"] = int(self._stats.get("files_opened", 0)) + 1
        self.save()

    def record_ai_request(self) -> None:
        """Record an AI request."""
        self._stats["ai_requests_count"] = int(self._stats.get("ai_requests_count", 0)) + 1
        self.save()

    def record_command_executed(self) -> None:
        """Record a command execution."""
        self._stats["commands_executed"] = int(self._stats.get("commands_executed", 0)) + 1
        self.save()

    def reset(self) -> None:
        """Reset all usage statistics."""
        self._stats = dict(self.DEFAULT_STATS)
        self._stats["first_launch_date"] = datetime.now().isoformat()
        self.save()

    def get_stats(self) -> dict[str, object]:
        """Get all statistics."""
        return dict(self._stats)

    def get_formatted_session_time(self) -> str:
        """Get formatted total session time."""
        seconds = int(self._stats.get("total_session_time_seconds", 0))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs}s"
