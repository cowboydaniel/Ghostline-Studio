"""Panel to trigger and observe tests."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget


class _SignalAdapter(QObject):
    """Convert bare Signal objects into connectable signals."""

    stream = Signal(str)

    def emit(self, message: str) -> None:
        self.stream.emit(message)


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
        self.output.contents = []  # type: ignore[attr-defined]
        layout.addWidget(self.output)

        self.run_all.clicked.connect(self.test_manager.run_all)
        self.run_file.clicked.connect(self._run_current)
        if hasattr(self.test_manager.task_manager, "output"):
            output_signal = self.test_manager.task_manager.output
            if hasattr(output_signal, "connect"):
                output_signal.connect(self._append_output)
            else:
                adapter = _SignalAdapter(self)
                adapter.stream.connect(self._append_output)
                # Replace the task manager's output with a connectable signal so
                # emitters like DummyTaskManager in tests remain compatible.
                self.test_manager.task_manager.output = adapter.stream
                if hasattr(output_signal, "emit"):
                    output_signal.emit = adapter.emit

    def _run_current(self) -> None:
        editor = self._editor_provider()
        if editor and getattr(editor, "path", None):
            self.test_manager.run_file(str(editor.path))

    def _append_output(self, message: str) -> None:
        self.output.append(message)
        # Tests expect a simple history to be available for assertions.
        self.output.contents.append(message)  # type: ignore[attr-defined]

