"""Workspace indexing orchestration."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ghostline.core.threads import BackgroundWorkers


class IndexManager:
    """Coordinates indexing and search tasks in the background."""

    def __init__(self, workspace_provider, workers: BackgroundWorkers | None = None) -> None:
        self.workspace_provider = workspace_provider
        self.workers = workers or BackgroundWorkers()
        self._observers: list[callable[[Path], None]] = []

    def register_observer(self, callback) -> None:
        self._observers.append(callback)

    def _notify(self, path: Path) -> None:
        for callback in self._observers:
            callback(path)

    def reindex(self, paths: Iterable[str] | None = None) -> None:
        workspace = self.workspace_provider()
        roots = [Path(p) for p in paths] if paths else [Path(workspace)] if workspace else []
        for root in roots:
            self.workers.submit(f"index:{root}", self._index_path, root)

    def _index_path(self, path: Path) -> None:
        self._notify(path)

    def shutdown(self) -> None:
        self.workers.shutdown()
