"""Windsurf-style terminal widget with sessions, controls, and proper layout."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QProcess, QSize
from PySide6.QtGui import QIcon, QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QToolButton,
    QSizePolicy,
    QStyle,
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
    Complete Windsurf-style terminal widget with compact toolbar and slim sidebar.
    """

    def __init__(self, workspace_manager: WorkspaceManager, parent=None) -> None:
        super().__init__(parent)
        self.workspace_manager = workspace_manager
        self.sessions: list[TerminalSession] = []
        self.current_session_index = 0
        self._metrics = self._build_metrics()
        self._session_icon = QIcon.fromTheme("utilities-terminal")
        if self._session_icon.isNull():
            self._session_icon = self.style().standardIcon(QStyle.SP_ComputerIcon)

        self.setObjectName("windsurfTerminal")
        self._setup_ui()
        self._create_initial_session()

    def _setup_ui(self) -> None:
        """Setup the complete UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        toolbar_widget = self._create_toolbar()
        main_layout.addWidget(toolbar_widget)

        # Main content area: terminal + session list
        content_splitter = QSplitter(Qt.Horizontal, self)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setHandleWidth(1)

        # Left side: terminal viewport
        self.terminal_stack = QWidget(self)
        self.terminal_layout = QVBoxLayout(self.terminal_stack)
        self.terminal_layout.setContentsMargins(0, 0, 0, 0)
        self.terminal_layout.setSpacing(0)
        self.terminal_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content_splitter.addWidget(self.terminal_stack)

        # Right side: session list
        self.session_list = QListWidget(self)
        self.session_list.setObjectName("terminalSessionList")
        self.session_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.session_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.session_list.setUniformItemSizes(True)
        self.session_list.setIconSize(QSize(14, 14))
        self.session_list.setSpacing(0)
        self.session_list.setFixedWidth(self._metrics["sidebar_width"])
        self.session_list.currentRowChanged.connect(self._on_session_changed)
        content_splitter.addWidget(self.session_list)

        # Set splitter proportions (terminal gets most space)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 0)
        content_splitter.setSizes([900, self._metrics["sidebar_width"]])

        main_layout.addWidget(content_splitter, stretch=1)

    def _build_metrics(self) -> dict[str, int]:
        """Derive compact sizing from font metrics to mimic Windsurf proportions."""
        fm = QFontMetrics(self.font())
        base = fm.height()
        return {
            "toolbar_height": max(28, base + 10),
            "toolbar_padding": 6,
            "sidebar_width": max(120, fm.horizontalAdvance("Terminal 000") + 18),
            "sidebar_row_height": max(24, base + 6),
        }

    def _create_toolbar(self) -> QWidget:
        """Create compact toolbar that mirrors Windsurf's terminal strip."""
        toolbar = QWidget(self)
        toolbar.setObjectName("terminalToolbar")
        toolbar.setFixedHeight(self._metrics["toolbar_height"])

        layout = QHBoxLayout(toolbar)
        pad = self._metrics["toolbar_padding"]
        layout.setContentsMargins(pad, 2, pad, 2)
        layout.setSpacing(6)

        working_dir = self.workspace_manager.current_workspace or Path.cwd()
        self.cwd_label = QLabel(self)
        self.cwd_label.setObjectName("terminalStatusLabel")
        self.cwd_label.setText(f"bash — {working_dir}")
        self.cwd_label.setToolTip(f"Working directory: {working_dir}")
        self.cwd_label.setMinimumWidth(80)
        self.cwd_label.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.cwd_label)

        layout.addStretch()

        self.profile_combo = QComboBox(self)
        self.profile_combo.setObjectName("terminalProfileCombo")
        self.profile_combo.addItem("bash")
        if shutil.which("zsh"):
            self.profile_combo.addItem("zsh")
        if shutil.which("fish"):
            self.profile_combo.addItem("fish")
        self.profile_combo.setFixedWidth(96)
        layout.addWidget(self.profile_combo)

        self.new_terminal_btn = QToolButton(self)
        self.new_terminal_btn.setObjectName("terminalNewBtn")
        self.new_terminal_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.new_terminal_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        self.new_terminal_btn.setToolTip("New Terminal")
        self.new_terminal_btn.clicked.connect(self._create_new_session)
        layout.addWidget(self.new_terminal_btn)

        self.terminal_selector = QComboBox(self)
        self.terminal_selector.setObjectName("terminalSelector")
        self.terminal_selector.currentIndexChanged.connect(self._on_selector_changed)
        self.terminal_selector.setFixedWidth(130)
        layout.addWidget(self.terminal_selector)

        self.split_btn = QToolButton(self)
        self.split_btn.setObjectName("terminalSplitBtn")
        self.split_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.split_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarShadeButton))
        self.split_btn.setToolTip("Split Terminal (coming soon)")
        self.split_btn.setEnabled(False)
        layout.addWidget(self.split_btn)

        self.kill_btn = QToolButton(self)
        self.kill_btn.setObjectName("terminalKillBtn")
        self.kill_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.kill_btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.kill_btn.setToolTip("Kill Terminal")
        self.kill_btn.clicked.connect(self._kill_current_session)
        layout.addWidget(self.kill_btn)

        self.external_terminal_btn = QToolButton(self)
        self.external_terminal_btn.setObjectName("openExternalTerminalBtn")
        self.external_terminal_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.external_terminal_btn.setIcon(self.style().standardIcon(QStyle.SP_DesktopIcon))
        self.external_terminal_btn.setToolTip("Open External Terminal")
        self.external_terminal_btn.clicked.connect(self._open_external_terminal)
        layout.addWidget(self.external_terminal_btn)

        self.menu_btn = QToolButton(self)
        self.menu_btn.setObjectName("terminalMenuBtn")
        self.menu_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.menu_btn.setIcon(self.style().standardIcon(QStyle.SP_ToolBarHorizontalExtensionButton))
        self.menu_btn.setToolTip("More actions")
        layout.addWidget(self.menu_btn)

        return toolbar

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
        item = QListWidgetItem(self._session_icon, session_name)
        item.setSizeHint(QSize(item.sizeHint().width(), self._metrics["sidebar_row_height"]))
        self.session_list.addItem(item)
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
            self._update_status_label(current_dir)

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

    def _kill_current_session(self) -> None:
        """Terminate the current terminal session without removing UI context."""
        if not self.sessions:
            return
        session = self.sessions[self.current_session_index]
        session.terminal.write_input("exit\n")

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
            self._update_status_label(working_dir)
            # Update current session's working directory
            if self.sessions:
                current_session = self.sessions[self.current_session_index]
                current_session.terminal.write_input(f"cd {working_dir}\n")

    def _update_status_label(self, working_dir: Path) -> None:
        path = Path(working_dir)
        short_text = f"bash — {path}"
        self.cwd_label.setText(short_text)
        self.cwd_label.setToolTip(f"Working directory: {path}")
