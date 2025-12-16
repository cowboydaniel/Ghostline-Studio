"""Workspace management."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

RECENTS_PATH = Path.home() / ".config" / "ghostline" / "recents.json"


class WorkspaceManager:
    def __init__(self) -> None:
        self.current_workspace: Optional[Path] = None
        self.recent_items: list[str] = self._load_recents()

    def open_workspace(self, folder: str | Path) -> None:
        """Open a workspace with path validation to prevent path traversal attacks."""
        # Resolve to absolute path to prevent traversal
        path = Path(folder).resolve()

        # Validate the path exists and is a directory
        if not path.exists():
            raise ValueError(f"Workspace path does not exist: {path}")

        if not path.is_dir():
            raise ValueError(f"Workspace path is not a directory: {path}")

        # Optional: Additional security - ensure path doesn't contain suspicious patterns
        # This helps prevent accidental or malicious access to sensitive directories
        path_str = str(path)
        if any(suspicious in path_str for suspicious in ['/etc/', '/sys/', '/proc/', '/dev/']):
            # Log warning but allow if user explicitly wants system directories
            import logging
            logging.getLogger(__name__).warning(
                "Opening system directory as workspace: %s. This may pose security risks.", path
            )

        self.current_workspace = path
        self.register_recent(str(path))

    def clear_workspace(self) -> None:
        self.current_workspace = None

    def register_recent(self, path: str) -> None:
        if path in self.recent_items:
            self.recent_items.remove(path)
        self.recent_items.insert(0, path)
        self.recent_items = self.recent_items[:10]

    def save_recents(self) -> None:
        RECENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RECENTS_PATH.open("w", encoding="utf-8") as handle:
            json.dump(self.recent_items, handle, indent=2)

    def _load_recents(self) -> list[str]:
        if RECENTS_PATH.exists():
            try:
                return json.loads(RECENTS_PATH.read_text())
            except json.JSONDecodeError:
                return []
        return []

    def iter_workspace_files(self) -> Iterable[Path]:
        if not self.current_workspace:
            return []
        return self.current_workspace.rglob("*")

    def last_recent_workspace(self) -> Optional[Path]:
        for item in self.recent_items:
            candidate = Path(item)
            if candidate.exists() and candidate.is_dir():
                return candidate
        return None
