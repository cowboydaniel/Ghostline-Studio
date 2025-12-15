"""File system model scoped to the current workspace."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir, QModelIndex, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileIconProvider, QFileSystemModel, QStyle

from ghostline.core.resources import load_file_icon, load_icon


class ProjectModel(QFileSystemModel):
    """A thin wrapper around QFileSystemModel with simple filtering."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files)
        self._workspace_root: Path | None = None
        self._hidden = {".git", "__pycache__"}

        # Load folder icon from resources or fallback to system
        style = QApplication.style()
        folder_icon = load_icon("folders/folder.svg")
        if folder_icon.isNull():
            folder_icon = style.standardIcon(QStyle.SP_DirIcon)

        self._folder_icon = folder_icon

        provider = QFileIconProvider()
        provider.setOptions(QFileIconProvider.DontUseCustomDirectoryIcons)
        self.setIconProvider(provider)

    def set_workspace_root(self, path: str | None):
        self._workspace_root = Path(path) if path else None
        if path:
            return self.setRootPath(path)
        return None

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if role == Qt.DecorationRole:
            path = Path(self.filePath(index))
            if path.is_dir():
                return self._folder_icon
            # Use the new icon system that supports all file types
            return load_file_icon(path.name)
        if role == Qt.DisplayRole:
            # Show folder/file names without size or type columns.
            return Path(self.filePath(index)).name
        return super().data(index, role)

    def _is_within_workspace(self, path: Path) -> bool:
        if not self._workspace_root:
            return True
        try:
            path.relative_to(self._workspace_root)
            return True
        except ValueError:
            return False

    # Qt protected method allows filtering of rows
    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]
        index = self.index(source_row, 0, source_parent)
        if not index.isValid():
            return False
        path = Path(self.filePath(index))
        if self._workspace_root:
            if not source_parent.isValid():
                if path != self._workspace_root:
                    return False
            else:
                parent_path = Path(self.filePath(source_parent))
                if not self._is_within_workspace(parent_path):
                    return False
                if not self._is_within_workspace(path):
                    return False
        name = self.fileName(index)
        if name in self._hidden:
            return False
        return super().filterAcceptsRow(source_row, source_parent)

