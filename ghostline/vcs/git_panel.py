"""UI panel for advanced Git features."""
from __future__ import annotations

from PySide6.QtWidgets import QListWidget, QPushButton, QVBoxLayout, QWidget

from ghostline.vcs.git_service import GitService


class GitPanel(QWidget):
    def __init__(self, service: GitService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        layout = QVBoxLayout(self)
        self.history = QListWidget(self)
        self.refresh_btn = QPushButton("Refresh History", self)
        layout.addWidget(self.refresh_btn)
        layout.addWidget(self.history)
        self.refresh_btn.clicked.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        self.history.clear()
        for line in self.service.history():
            self.history.addItem(line)
