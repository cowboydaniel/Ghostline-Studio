"""File system model scoped to the current workspace."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir
from PySide6.QtWidgets import QFileSystemModel


class ProjectModel(QFileSystemModel):
    """A thin wrapper around QFileSystemModel with simple filtering."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files)
        self._hidden = {".git", "__pycache__"}

    def set_workspace_root(self, path: str | None):
        if path:
            return self.setRootPath(path)
        return None

    # Qt protected method allows filtering of rows
    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]
        index = self.index(source_row, 0, source_parent)
        if not index.isValid():
            return False
        name = self.fileName(index)
        if name in self._hidden:
            return False
        return super().filterAcceptsRow(source_row, source_parent)

