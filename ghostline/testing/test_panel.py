"""Panel to trigger and observe tests."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget


class TestPanel(QWidget):
    def __init__(self, test_manager, editor_provider, parent=None) -> None:
        super().__init__(parent)
        self.test_manager = test_manager
        self._editor_provider = editor_provider

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.run_all = QPushButton("Run All", self)
        self.run_file = QPushButton("Run Current File", self)
        controls.addWidget(self.run_all)
        controls.addWidget(self.run_file)
        layout.addLayout(controls)

        self.output = QTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Test output will appear here after running tests.")
        layout.addWidget(self.output)

        self.run_all.clicked.connect(self.test_manager.run_all)
        self.run_file.clicked.connect(self._run_current)
        if hasattr(self.test_manager.task_manager, "output"):
            self.test_manager.task_manager.output.connect(self.output.append)

    def _run_current(self) -> None:
        editor = self._editor_provider()
        if editor and getattr(editor, "path", None):
            self.test_manager.run_file(str(editor.path))

