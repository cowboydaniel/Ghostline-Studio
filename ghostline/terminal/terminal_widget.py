"""Lightweight embedded terminal widget."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget, QPlainTextEdit, QLineEdit

from ghostline.workspace.workspace_manager import WorkspaceManager


class TerminalWidget(QWidget):
    def __init__(self, workspace_manager: WorkspaceManager, parent=None) -> None:
        super().__init__(parent)
        self.workspace_manager = workspace_manager

        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.input = QLineEdit(self)
        self.input.returnPressed.connect(self._send_command)
        self.launch_button = QPushButton("Open External Terminal", self)
        self.launch_button.clicked.connect(self._open_external_terminal)

        layout = QVBoxLayout(self)
        layout.addWidget(self.output)
        layout.addWidget(self.input)
        layout.addWidget(self.launch_button)

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._append_output)
        self.process.readyReadStandardError.connect(self._append_output)
        cwd = Path(self.workspace_manager.current_workspace or Path.cwd())
        self.process.setWorkingDirectory(str(cwd))
        self.process.start("/bin/bash")

    def _append_output(self) -> None:
        text = self.process.readAllStandardOutput().data().decode()
        text += self.process.readAllStandardError().data().decode()
        if text:
            self.output.appendPlainText(text)

    def _send_command(self) -> None:
        command = self.input.text()
        if command:
            self.process.write((command + "\n").encode())
            self.input.clear()

    def _open_external_terminal(self) -> None:
        cwd = Path(self.workspace_manager.current_workspace or Path.cwd())
        QProcess.startDetached("/bin/bash", [], str(cwd))
