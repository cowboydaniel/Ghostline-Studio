"""Windsurf-style terminal widget with sessions, controls, and proper layout."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QProcess
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QListWidget,
    QSplitter,
    QFrame,
)

from ghostline.terminal.pty_terminal import PTYTerminal
from ghostline.workspace.workspace_manager import WorkspaceManager


class TerminalSession:
    """Represents a single terminal session."""

    def __init__(self, name: str, terminal: PTYTerminal, working_dir: Path) -> None:
        self.name = name
        self.terminal = terminal
        self.working_dir = working_dir
        self.session_id = id(self)


class WindsurfTerminalWidget(QWidget):
    """
    Complete Windsurf-style terminal widget.

    Layout:
    - Header area: "Terminal" title, description, working directory
    - Main area: Terminal viewport + session list (splitter)
    - Controls: Profile indicator, +, dropdown, etc.
    - Bottom: "Open External Terminal" button
    """

    def __init__(self, workspace_manager: WorkspaceManager, parent=None) -> None:
        super().__init__(parent)
        self.workspace_manager = workspace_manager
        self.sessions: list[TerminalSession] = []
        self.current_session_index = 0

        self.setObjectName("windsurfTerminal")
        self._setup_ui()
        self._create_initial_session()

    def _setup_ui(self) -> None:
        """Setup the complete UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header area
        header_widget = self._create_header()
        main_layout.addWidget(header_widget)

        # Separator
        sep1 = QFrame(self)
        sep1.setObjectName("terminalSeparator")
        sep1.setFrameShape(QFrame.HLine)
        sep1.setFixedHeight(1)
        main_layout.addWidget(sep1)

        # Main content area: terminal + session list
        content_splitter = QSplitter(Qt.Horizontal, self)
        content_splitter.setChildrenCollapsible(False)

        # Left side: terminal viewport
        self.terminal_stack = QWidget(self)
        self.terminal_layout = QVBoxLayout(self.terminal_stack)
        self.terminal_layout.setContentsMargins(0, 0, 0, 0)
        self.terminal_layout.setSpacing(0)

        content_splitter.addWidget(self.terminal_stack)

        # Right side: session list
        self.session_list = QListWidget(self)
        self.session_list.setObjectName("terminalSessionList")
        self.session_list.setMaximumWidth(200)
        self.session_list.currentRowChanged.connect(self._on_session_changed)
        content_splitter.addWidget(self.session_list)

        # Set splitter proportions (terminal gets most space)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 0)
        content_splitter.setSizes([800, 200])

        main_layout.addWidget(content_splitter, stretch=1)

        # Separator
        sep2 = QFrame(self)
        sep2.setObjectName("terminalSeparator")
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFixedHeight(1)
        main_layout.addWidget(sep2)

        # Bottom: "Open External Terminal" button
        self.external_terminal_btn = QPushButton("Open External Terminal", self)
        self.external_terminal_btn.setObjectName("openExternalTerminalBtn")
        self.external_terminal_btn.clicked.connect(self._open_external_terminal)
        self.external_terminal_btn.setMinimumHeight(32)
        main_layout.addWidget(self.external_terminal_btn)

    def _create_header(self) -> QWidget:
        """Create the header area with title, description, and controls."""
        header = QWidget(self)
        header.setObjectName("terminalHeader")
        header.setMinimumHeight(80)

        layout = QVBoxLayout(header)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Top row: Title + controls
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # Title
        title_label = QLabel("Terminal", self)
        title_label.setObjectName("terminalTitle")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        top_row.addWidget(title_label)

        top_row.addStretch()

        # Terminal controls (right side)
        # Profile indicator
        self.profile_combo = QComboBox(self)
        self.profile_combo.setObjectName("terminalProfileCombo")
        self.profile_combo.addItem("bash")
        if shutil.which("zsh"):
            self.profile_combo.addItem("zsh")
        if shutil.which("fish"):
            self.profile_combo.addItem("fish")
        self.profile_combo.setMaximumWidth(100)
        top_row.addWidget(self.profile_combo)

        # Add new terminal button
        self.new_terminal_btn = QPushButton("+", self)
        self.new_terminal_btn.setObjectName("terminalNewBtn")
        self.new_terminal_btn.setFixedSize(24, 24)
        self.new_terminal_btn.setToolTip("New Terminal")
        self.new_terminal_btn.clicked.connect(self._create_new_session)
        top_row.addWidget(self.new_terminal_btn)

        # Terminal selector dropdown
        self.terminal_selector = QComboBox(self)
        self.terminal_selector.setObjectName("terminalSelector")
        self.terminal_selector.currentIndexChanged.connect(self._on_selector_changed)
        self.terminal_selector.setMaximumWidth(150)
        top_row.addWidget(self.terminal_selector)

        layout.addLayout(top_row)

        # Description
        desc_label = QLabel("Embedded terminal is running your workspace shell.", self)
        desc_label.setObjectName("terminalDescription")
        desc_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(desc_label)

        # Working directory
        working_dir = self.workspace_manager.current_workspace or Path.cwd()
        self.cwd_label = QLabel(f"Working directory: {working_dir}", self)
        self.cwd_label.setObjectName("terminalWorkingDir")
        self.cwd_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(self.cwd_label)

        return header

    def _create_initial_session(self) -> None:
        """Create the first terminal session."""
        self._create_new_session()

    def _create_new_session(self) -> None:
        """Create a new terminal session."""
        # Determine working directory
        working_dir = Path(self.workspace_manager.current_workspace or Path.cwd())

        # Create terminal
        terminal = PTYTerminal(self)
        terminal.start_shell(working_dir)

        # Create session
        session_name = f"Terminal {len(self.sessions) + 1}"
        session = TerminalSession(session_name, terminal, working_dir)
        self.sessions.append(session)

        # Add to UI
        self.terminal_layout.addWidget(terminal)
        self.session_list.addItem(session_name)
        self.terminal_selector.addItem(session_name)

        # Switch to new session
        self._switch_to_session(len(self.sessions) - 1)

    def _switch_to_session(self, index: int) -> None:
        """Switch to a specific terminal session."""
        if 0 <= index < len(self.sessions):
            # Hide all terminals
            for i, session in enumerate(self.sessions):
                session.terminal.setVisible(i == index)

            # Update current session
            self.current_session_index = index
            self.session_list.setCurrentRow(index)
            self.terminal_selector.setCurrentIndex(index)

            # Update working directory label
            current_session = self.sessions[index]
            current_dir = current_session.terminal.get_working_directory()
            self.cwd_label.setText(f"Working directory: {current_dir}")

    def _on_session_changed(self, index: int) -> None:
        """Handle session list selection change."""
        if index >= 0:
            self._switch_to_session(index)

    def _on_selector_changed(self, index: int) -> None:
        """Handle terminal selector change."""
        if index >= 0:
            self._switch_to_session(index)

    def _open_external_terminal(self) -> None:
        """Open external terminal in workspace directory."""
        working_dir = self.workspace_manager.current_workspace or Path.cwd()
        self._launch_external_terminal(working_dir)

    def _launch_external_terminal(self, cwd: Path) -> None:
        """Launch system terminal emulator."""
        # Terminal candidates with their launch commands
        candidates = [
            ["gnome-terminal", "--working-directory", str(cwd)],
            ["konsole", "--workdir", str(cwd)],
            ["xfce4-terminal", "--working-directory", str(cwd)],
            ["mate-terminal", "--working-directory", str(cwd)],
            ["kitty", "--directory", str(cwd)],
            ["alacritty", "--working-directory", str(cwd)],
            ["x-terminal-emulator"],
        ]

        for candidate in candidates:
            if shutil.which(candidate[0]):
                # Launch terminal
                try:
                    if len(candidate) > 1:
                        QProcess.startDetached(candidate[0], candidate[1:])
                    else:
                        QProcess.startDetached(candidate[0], [], str(cwd))
                    return
                except Exception:
                    continue

        # Fallback: try to launch shell directly (won't open window but won't crash)
        shell = sys.platform.startswith("win") and "cmd.exe" or "/bin/bash"
        QProcess.startDetached(shell, [], str(cwd))

    def run_command(self, command: str) -> None:
        """Run a command in the current terminal session."""
        if self.sessions:
            current_session = self.sessions[self.current_session_index]
            current_session.terminal.write_input(f"{command}\n")

    def set_workspace(self, workspace: Optional[Path]) -> None:
        """Update working directory when workspace changes."""
        if workspace:
            working_dir = Path(workspace)
            self.cwd_label.setText(f"Working directory: {working_dir}")
            # Update current session's working directory
            if self.sessions:
                current_session = self.sessions[self.current_session_index]
                current_session.terminal.write_input(f"cd {working_dir}\n")
