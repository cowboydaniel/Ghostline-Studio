"""Lightweight embedded terminal widget."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget, QPlainTextEdit, QLineEdit

from ghostline.workspace.workspace_manager import WorkspaceManager


class TerminalWidget(QWidget):
    def __init__(self, workspace_manager: WorkspaceManager, parent=None) -> None:
        super().__init__(parent)
        self.workspace_manager = workspace_manager
        self.shell = "cmd.exe" if sys.platform.startswith("win") else "/bin/bash"
        self.current_directory = Path(self.workspace_manager.current_workspace or Path.cwd())

        notice = QLabel("Embedded terminal is running your workspace shell.", self)
        notice.setWordWrap(True)
        self.cwd_label = QLabel(f"Working directory: {self.current_directory}", self)

        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.input = QLineEdit(self)
        self.input.returnPressed.connect(self._send_command)
        self.launch_button = QPushButton("Open External Terminal", self)
        self.launch_button.clicked.connect(self._open_external_terminal)

        layout = QVBoxLayout(self)
        layout.addWidget(notice)
        layout.addWidget(self.cwd_label)
        layout.addWidget(self.output)
        layout.addWidget(self.input)
        layout.addWidget(self.launch_button)

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._append_output)
        self.process.readyReadStandardError.connect(self._append_output)
        self._start_shell()

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
        cwd = Path(self.workspace_manager.current_workspace or Path.home())
        self._launch_external_terminal(cwd)

    # ------------------------------------------------------------------
    def _start_shell(self) -> None:
        self.process.setWorkingDirectory(str(self.current_directory))
        self.process.start(self.shell)
        if self.process.waitForStarted(1000):
            self._send_initial_cd()
        else:
            self.output.appendPlainText("Failed to start embedded terminal process.")

    def _send_initial_cd(self) -> None:
        if self.current_directory:
            self.process.write((f"cd {self.current_directory}\n").encode())
            self.cwd_label.setText(f"Working directory: {self.current_directory}")

    def set_workspace(self, workspace: Path | None) -> None:
        """Update the terminal working directory to the active workspace."""

        target = Path(workspace) if workspace else Path.home()
        if target == self.current_directory:
            return
        self.current_directory = target
        if self.process.state() == QProcess.Running:
            self.process.write((f"cd {self.current_directory}\n").encode())
        else:
            self._start_shell()
        self.cwd_label.setText(f"Working directory: {self.current_directory}")

    def _launch_external_terminal(self, cwd: Path) -> None:
        candidates = [
            ["x-terminal-emulator"],
            ["gnome-terminal"],
            ["konsole"],
            ["mate-terminal"],
            ["xfce4-terminal"],
            ["alacritty"],
            ["cmd.exe"],
            ["powershell.exe"],
        ]
        for candidate in candidates:
            if shutil.which(candidate[0]):
                QProcess.startDetached(candidate[0], candidate[1:], str(cwd))
                return
        # Fallback to the shell itself if no terminal emulator is found
        QProcess.startDetached(self.shell, [], str(cwd))
