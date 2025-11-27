"""Project-aware dashboard shown when no file is open."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget


class WorkspaceDashboard(QWidget):
    """Show contextual actions for an open workspace."""

    def __init__(
        self,
        *,
        open_file: Callable[[str], None],
        open_palette: Callable[[], None],
    ) -> None:
        super().__init__()
        self._open_file = open_file
        self._open_palette = open_palette
        self._workspace: Path | None = None

        self.title = QLabel("Workspace Ready", self)
        self.title.setAlignment(Qt.AlignCenter)
        self.subtitle = QLabel("Open a file to start editing.", self)
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setWordWrap(True)

        self.recents = QListWidget(self)
        self.recents.setSpacing(4)
        self.recents.itemActivated.connect(self._activate_recent)

        self.palette_button = QPushButton("Command Palette…", self)
        self.palette_button.clicked.connect(self._open_palette)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 32)
        layout.setSpacing(12)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(QLabel("Recent Files", self))
        layout.addWidget(self.recents)
        layout.addWidget(self.palette_button)
        layout.addStretch(1)

    def set_workspace(self, workspace: Path | None, recent_files: Iterable[str]) -> None:
        self._workspace = workspace
        name = workspace.name if workspace else "Workspace"
        self.title.setText(f"{name} Dashboard")
        self.subtitle.setText("Pick up where you left off or open a file from the Project tree.")
        self._populate_recents(recent_files)

    def _populate_recents(self, files: Iterable[str]) -> None:
        self.recents.clear()
        added = False
        for path in files:
            file_path = Path(path)
            if not file_path.exists():
                continue
            added = True
            item = QListWidgetItem(f"{file_path.name} — {file_path.parent}")
            item.setData(Qt.UserRole, str(file_path))
            self.recents.addItem(item)

        if not added:
            placeholder = QListWidgetItem("No recently opened files. Double-click a file in Project to begin.")
            placeholder.setFlags(Qt.NoItemFlags)
            self.recents.addItem(placeholder)

    def _activate_recent(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self._open_file(str(path))
