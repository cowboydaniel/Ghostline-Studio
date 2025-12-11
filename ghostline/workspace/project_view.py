"""Tree view for browsing workspace files."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QInputDialog,
    QMenu,
    QMessageBox,
    QTreeView,
)

from ghostline.workspace.project_model import ProjectModel


class ProjectView(QTreeView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setEditTriggers(QTreeView.NoEditTriggers)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setSelectionMode(QTreeView.SingleSelection)
        self.clicked.connect(self._on_item_clicked)
        self.doubleClicked.connect(self._on_item_double_clicked)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Match Windsurf-style explorer tree: tight rows, subtle hover,
        # full-width selection, and slightly reduced indentation.
        self.setIndentation(14)
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)

        self.setStyleSheet(
            """
            QTreeView {
                font-size: 11px;
                show-decoration-selected: 1;
                background: #101113;
                border: none;
                alternate-background-color: #15171a;
            }
            QTreeView::item {
                padding: 2px 8px;
            }
            QTreeView::item:selected:active,
            QTreeView::item:selected:!active {
                background-color: rgba(255, 255, 255, 0.06);
            }
            QTreeView::item:hover {
                background-color: rgba(255, 255, 255, 0.03);
            }
            """
        )

    def set_model(self, model: ProjectModel) -> None:
        self.setModel(model)
        self._model = model
        for column in range(1, model.columnCount()):
            self.setColumnHidden(column, True)

    def _on_item_clicked(self, index) -> None:
        if index.isValid():
            path = self._model.filePath(index)
            if Path(path).is_file() and hasattr(self.window(), "open_file"):
                self.window().open_file(path, preview=True)

    def _on_item_double_clicked(self, index) -> None:
        if index.isValid():
            path = self._model.filePath(index)
            if Path(path).is_file() and hasattr(self.window(), "open_file"):
                self.window().open_file(path, preview=False)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        index = self.indexAt(event.pos())
        if index.isValid():
            path = self._model.filePath(index)
            if Path(path).is_dir():  # Only handle double-click for folders
                super().mouseDoubleClickEvent(event)
        else:
            super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, pos) -> None:
        index = self.indexAt(pos)
        menu = QMenu(self)
        create_file = menu.addAction("New File")
        create_folder = menu.addAction("New Folder")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        action = menu.exec_(self.viewport().mapToGlobal(pos))
        target_dir = Path(self._model.filePath(index)) if index.isValid() else Path(self._model.rootPath())
        if action == create_file:
            self._create_item(target_dir, is_dir=False)
        elif action == create_folder:
            self._create_item(target_dir, is_dir=True)
        elif action == rename_action and index.isValid():
            self._rename_item(Path(self._model.filePath(index)))
        elif action == delete_action and index.isValid():
            self._delete_item(Path(self._model.filePath(index)))

    def _create_item(self, base: Path, is_dir: bool) -> None:
        name, ok = QInputDialog.getText(self, "Create", "Name:")
        if not ok or not name:
            return
        target = base / name if base.is_dir() else base.parent / name
        if is_dir:
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch(exist_ok=True)

    def _rename_item(self, path: Path) -> None:
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=path.name)
        if not ok or not name:
            return
        target = path.parent / name
        path.rename(target)

    def _delete_item(self, path: Path) -> None:
        confirm = QMessageBox.question(
            self,
            "Delete",
            f"Delete {path.name}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            if path.is_dir():
                for child in path.rglob("*"):
                    if child.is_file():
                        child.unlink()
                path.rmdir()
            else:
                path.unlink(missing_ok=True)

