"""UI panel for controlling the debugger."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from ghostline.debugger.debugger_manager import DebuggerManager


class DebuggerPanel(QWidget):
    def __init__(self, manager: DebuggerManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager

        self.console = QTextEdit(self)
        self.console.setReadOnly(True)
        self.variables = QListWidget(self)
        self.stack = QListWidget(self)

        self.button_run = QPushButton("Run", self)
        self.button_pause = QPushButton("Pause", self)
        self.button_stop = QPushButton("Stop", self)

        self.button_run.clicked.connect(self._choose_and_run)
        self.button_pause.clicked.connect(self.manager.pause)
        self.button_stop.clicked.connect(self.manager.stop)

        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        buttons.addWidget(self.button_run)
        buttons.addWidget(self.button_pause)
        buttons.addWidget(self.button_stop)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Call Stack"))
        layout.addWidget(self.stack)
        layout.addWidget(QLabel("Variables"))
        layout.addWidget(self.variables)
        layout.addWidget(QLabel("Console"))
        layout.addWidget(self.console)

        self.manager.output.connect(self._append_output)
        self.manager.state_changed.connect(self._show_state)

    def _append_output(self, text: str) -> None:
        self.console.append(text)

    def _show_state(self, state: str) -> None:
        self.console.append(f"State: {state}")

    def _choose_and_run(self) -> None:
        script, _ = QFileDialog.getOpenFileName(self, "Select Python file", filter="Python Files (*.py)")
        if script:
            self.manager.launch(script)
