"""Placeholder terminal widget."""
from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from ghostline.workspace.workspace_manager import WorkspaceManager


class TerminalWidget(QWidget):
    def __init__(self, workspace_manager: WorkspaceManager, parent=None) -> None:
        super().__init__(parent)
        self.workspace_manager = workspace_manager

        self.launch_button = QPushButton("Open System Terminal", self)
        self.launch_button.clicked.connect(self._open_terminal)

        layout = QVBoxLayout(self)
        layout.addWidget(self.launch_button)
        layout.addStretch()

    def _open_terminal(self) -> None:
        cwd = Path(self.workspace_manager.current_workspace or Path.cwd())
        subprocess.Popen(["/bin/bash"], cwd=cwd)
