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
            self.info_label.setText("No git repository detected")
            self.refresh_btn.setEnabled(False)
            self.history.setEnabled(False)
            return
        self.refresh_btn.setEnabled(True)
        self.history.setEnabled(True)
        self.info_label.setText("")
        for line in self.service.history():
            self.history.addItem(line)
