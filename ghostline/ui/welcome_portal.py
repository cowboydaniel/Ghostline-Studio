"""Full-window welcome portal."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget


class WelcomePortal(QWidget):
    """Modern welcome screen showing quick starts and templates."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.recent = QListWidget(self)
        self.templates = QListWidget(self)
        self.news = QLabel("Ghostline news & plugins")
        self.start_button = QPushButton("Start with a template")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Recent repositories"))
        layout.addWidget(self.recent)
        layout.addWidget(QLabel("Quick templates"))
        layout.addWidget(self.templates)
        layout.addWidget(self.start_button)
        layout.addWidget(self.news)

    def set_recents(self, items: list[str]) -> None:
        self.recent.clear()
        self.recent.addItems(items)

    def set_templates(self, templates: list[str]) -> None:
        self.templates.clear()
        self.templates.addItems(templates)
