"""Workspace management with recents, metadata and file watching."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import QObject, QFileSystemWatcher, Signal

from ghostline.workspace.templates import WorkspaceTemplateManager

RECENTS_PATH = Path.home() / ".config" / "ghostline" / "recents.json"
WORKSPACE_META = ".ghostline/workspace.json"


class WorkspaceManager(QObject):
    """Track the active workspace, metadata and filesystem changes."""

    workspaceChanged = Signal(Path)
    fileChanged = Signal(str)
    fileAdded = Signal(str)
    fileRemoved = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.current_workspace: Optional[Path] = None
        self.workspace_file: Optional[Path] = None
        self.workspace_folders: list[Path] = []
        self.recent_items: list[str] = self._load_recents()
        self._metadata: dict[str, dict] = {}
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._handle_directory_change)
        self._watcher.fileChanged.connect(self._handle_file_change)
        self.templates = WorkspaceTemplateManager()

    # Workspace lifecycle -------------------------------------------------
    def open_workspace(self, folder: str | Path) -> None:
        """Open a workspace with validation and start watching changes."""

        path = Path(folder).resolve()
        if not path.exists():
            raise ValueError(f"Workspace path does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Workspace path is not a directory: {path}")

        path_str = str(path)
        if any(suspicious in path_str for suspicious in ["/etc/", "/sys/", "/proc/", "/dev/"]):
            import logging

            logging.getLogger(__name__).warning(
                "Opening system directory as workspace: %s. This may pose security risks.", path
            )

        self.current_workspace = path
        self.workspace_file = None
        self.workspace_folders = [path]
        self.register_recent(str(path))
        self._metadata[path_str] = self._load_workspace_metadata(path)
        self._start_watching(path)
        self.workspaceChanged.emit(path)

    def load_workspace_file(self, workspace_file: str | Path) -> None:
        """Load a multi-folder workspace from a .ghostline-workspace file."""

        file_path = Path(workspace_file).resolve()
        if not file_path.exists():
            raise FileNotFoundError(file_path)

        data = json.loads(file_path.read_text()) if file_path.read_text().strip() else {}
        folders = [Path(p) for p in data.get("folders", [])]
        if not folders:
            raise ValueError("Workspace file contains no folders")

        self.workspace_file = file_path
        self.workspace_folders = folders
        self.open_workspace(folders[0])

    def save_workspace_file(self, target: str | Path | None = None) -> Path:
        """Persist the current workspace folders to a .ghostline-workspace file."""

        if not self.workspace_folders and self.current_workspace:
            self.workspace_folders = [self.current_workspace]

        destination = Path(target) if target else None
        if destination is None:
            if self.workspace_file:
                destination = self.workspace_file
            elif self.current_workspace:
                destination = self.current_workspace / ".ghostline-workspace"
            else:
                raise ValueError("No workspace available to save")

        payload = {"folders": [str(folder) for folder in self.workspace_folders]}
        destination.write_text(json.dumps(payload, indent=2))
        self.workspace_file = destination
        self.register_recent(str(destination))
        return destination

    def duplicate_workspace_file(self, source: str | Path, destination: str | Path) -> Path:
        """Copy a workspace definition to a new location."""

        data = json.loads(Path(source).read_text())
        Path(destination).write_text(json.dumps(data, indent=2))
        self.register_recent(str(destination))
        return Path(destination)

    def add_folder_to_workspace(self, folder: str | Path) -> None:
        path = Path(folder).resolve()
        if path not in self.workspace_folders:
            self.workspace_folders.append(path)
        self.register_recent(str(path))
        if path.exists():
            paths = [str(path)] + [str(p) for p in path.rglob("*") if p.is_dir()]
            self._watcher.addPaths(paths)

    def clear_workspace(self) -> None:
        self._stop_watching()
        self.current_workspace = None
        self.workspace_file = None
        self.workspace_folders = []

    # Metadata -----------------------------------------------------------
    def _metadata_path(self, workspace: Path) -> Path:
        return workspace / WORKSPACE_META

    def _load_workspace_metadata(self, workspace: Path) -> dict:
        meta_path = self._metadata_path(workspace)
        if meta_path.exists():
            try:
                return json.loads(meta_path.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_workspace_metadata(self, workspace: Path) -> None:
        meta_path = self._metadata_path(workspace)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta = self._metadata.get(str(workspace), {})
        meta_path.write_text(json.dumps(meta, indent=2))

    def record_recent_file(self, file_path: str) -> None:
        """Add a file to the current workspace's recent list."""

        if not self.current_workspace:
            return
        workspace_key = str(self.current_workspace)
        meta = self._metadata.setdefault(workspace_key, {})
        files: list[str] = meta.setdefault("recent_files", [])
        if file_path in files:
            files.remove(file_path)
        files.insert(0, file_path)
        meta["recent_files"] = files[:15]
        self._save_workspace_metadata(self.current_workspace)

    def get_recent_files(self, workspace: Optional[Path] = None) -> list[str]:
        workspace = workspace or self.current_workspace
        if not workspace:
            return []
        return self._metadata.get(str(workspace), {}).get("recent_files", [])

    # Recents ------------------------------------------------------------
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

    # Workspace helpers --------------------------------------------------
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

    # File watching ------------------------------------------------------
    def _start_watching(self, workspace: Path) -> None:
        self._stop_watching()
        paths = [str(workspace)] + [str(p) for p in workspace.rglob("*") if p.is_dir()]
        if paths:
            self._watcher.addPaths(paths)

    def _stop_watching(self) -> None:
        watched_files = self._watcher.files()
        watched_dirs = self._watcher.directories()
        if watched_files:
            self._watcher.removePaths(watched_files)
        if watched_dirs:
            self._watcher.removePaths(watched_dirs)

    def _handle_directory_change(self, path: str) -> None:
        directory = Path(path)
        if not directory.exists():
            self.fileRemoved.emit(path)
            return
        for entry in directory.iterdir():
            if entry.is_dir():
                monitored = set(self._watcher.directories())
                if str(entry) not in monitored:
                    self._watcher.addPath(str(entry))
        self.fileChanged.emit(path)

    def _handle_file_change(self, path: str) -> None:
        target = Path(path)
        if target.exists():
            self.fileAdded.emit(path)
        else:
            self.fileRemoved.emit(path)
