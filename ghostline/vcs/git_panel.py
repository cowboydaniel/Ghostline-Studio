"""UI panel for advanced Git features."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from ghostline.vcs.git_service import GitService


class GitPanel(QWidget):
    def __init__(self, service: GitService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.info_label = QLabel("", self)
        self.history = QListWidget(self)
        self.refresh_btn = QPushButton("Refresh History", self)
        layout.addWidget(self.info_label)
        layout.addWidget(self.refresh_btn)
        layout.addWidget(self.history)
        self.refresh_btn.clicked.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        self.history.clear()
        if not self.service.workspace or not self.service.is_repo():
            self.set_empty_state(True)
            return
        self.set_empty_state(False)
        for line in self.service.history():
            self.history.addItem(line)

    def set_empty_state(self, missing_repo: bool) -> None:
        if missing_repo:
            self.info_label.setText("No Git repository detected. Initialize or open a repo to use Git tools.")
            self.info_label.setWordWrap(True)
            self.refresh_btn.setEnabled(False)
            self.history.setEnabled(False)
        else:
            self.info_label.setText("")
            self.refresh_btn.setEnabled(True)
            self.history.setEnabled(True)

    def has_repository(self) -> bool:
        return bool(self.service.workspace and self.service.is_repo())
