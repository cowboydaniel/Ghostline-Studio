"""Panel showing live documentation for open files."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QPushButton, QTextEdit, QVBoxLayout, QWidget, QDockWidget

from ghostline.ai.doc_generator import DocGenerator


class DocPanel(QDockWidget):
    def __init__(self, generator: DocGenerator, parent=None) -> None:
        super().__init__("Documentation", parent)
        self.generator = generator
        self.text = QTextEdit(self)
        self.text.setReadOnly(True)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.addWidget(self.text)
        layout.addWidget(self.refresh_button)
        self.setWidget(content)

        self._current_path: Path | None = None

    def set_current_file(self, path: Path) -> None:
        self._current_path = path
        self.refresh()

    def refresh(self) -> None:
        if not self._current_path:
            self.text.setPlainText("Open a file to see live documentation")
            return
        summary = self.generator.summarise_module(self._current_path)
        self.text.setPlainText(summary)

