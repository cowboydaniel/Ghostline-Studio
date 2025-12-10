"""Panel showing live documentation for open files."""
from __future__ import annotations

from pathlib import Path
import threading

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QTextEdit, QVBoxLayout, QWidget, QDockWidget

from ghostline.ai.doc_generator import DocGenerator


class DocPanel(QDockWidget):
    summary_ready = Signal(str)

    def __init__(self, generator: DocGenerator, parent=None) -> None:
        super().__init__("Documentation", parent)
        self.generator = generator
        self.text = QTextEdit(self)
        self.text.setReadOnly(True)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.text)
        layout.addWidget(self.refresh_button)
        self.setWidget(content)
        self.setMinimumWidth(260)

        self._current_path: Path | None = None

        self.summary_ready.connect(self.text.setPlainText)

    def set_current_file(self, path: Path) -> None:
        self._current_path = path
        self.refresh()

    def refresh(self) -> None:
        if not self._current_path:
            self.text.setPlainText("Open a file to see live documentation")
            return

        self.text.setPlainText("Generating documentation...")

        def worker(path: Path) -> None:
            try:
                summary = self.generator.summarise_module(path)
            except Exception as exc:  # noqa: BLE001
                summary = f"Failed to generate documentation:\n{exc}"
            try:
                self.summary_ready.emit(summary)
            except RuntimeError:
                return

        threading.Thread(target=worker, args=(self._current_path,), daemon=True).start()

