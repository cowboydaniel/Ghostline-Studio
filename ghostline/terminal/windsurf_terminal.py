"""Windsurf-style terminal widget with sessions, controls, and proper layout."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QProcess, QSize
from PySide6.QtGui import QFontMetrics, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSplitter,
    QToolButton,
    QSizePolicy,
    QStyle,
)

from ghostline.core.resources import load_icon
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

    def __init__(self, workspace_manager: WorkspaceManager, parent=None, use_external_toolbar: bool = True) -> None:
        super().__init__(parent)
        self.workspace_manager = workspace_manager
        self.sessions: list[TerminalSession] = []
        self.current_session_index = 0
        self._metrics = self._build_metrics()
        self._session_icon = QIcon.fromTheme("utilities-terminal")
        if self._session_icon.isNull():
            self._session_icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.use_external_toolbar = use_external_toolbar

        self.profile_commands = self._detect_profiles()
        self.active_profile = next(iter(self.profile_commands.keys()), "Python")
        self.cwd_label = QLabel(self)

        self.setObjectName("windsurfTerminal")
        self._setup_ui()
        self._create_initial_session()

    def _setup_ui(self) -> None:
        """Setup the complete UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.toolbar_widget = self._create_toolbar()
        if not self.use_external_toolbar:
            main_layout.addWidget(self.toolbar_widget)

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
            "toolbar_height": max(30, base + 10),
            "toolbar_padding": 6,
            "sidebar_width": max(120, fm.horizontalAdvance("Terminal 000") + 18),
            "sidebar_row_height": max(24, base + 6),
        }

    def _detect_profiles(self) -> dict[str, str]:
        """Build a small set of terminal profiles with a Windsurf-style default."""
        profiles: dict[str, str] = {}

        # Prefer the user's configured shell if available
        shell_env = os.environ.get("SHELL")
        if shell_env:
            profiles[Path(shell_env).name.capitalize()] = shell_env

        # Add common shells, without overriding an explicitly configured shell
        for shell_name in ("bash", "zsh", "fish"):
            shell_path = shutil.which(shell_name)
            if shell_path:
                profiles.setdefault(shell_name.capitalize(), shell_path)

        # Offer Python as an optional profile, but not as the default
        if sys.executable:
            profiles.setdefault("Python", sys.executable)

        if not profiles:
            profiles["Python"] = sys.executable or "/bin/bash"

        return profiles

    def _create_toolbar(self) -> QWidget:
        """Create compact toolbar that mirrors Windsurf's terminal strip."""
        toolbar = QWidget(self)
        toolbar.setObjectName("terminalToolbar")
        toolbar.setFixedHeight(self._metrics["toolbar_height"])

        layout = QHBoxLayout(toolbar)
        pad = self._metrics["toolbar_padding"]
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.profile_button = self._build_icon_button(
            "terminalProfileButton",
            load_icon("terminal_bar/terminal.svg"),
            "Terminal Profile",
            with_text=True,
        )
        self.profile_button.setPopupMode(QToolButton.InstantPopup)
        self.profile_menu = QMenu(self.profile_button)
        self.profile_button.setMenu(self.profile_menu)
        self._refresh_profile_menu()
        layout.addWidget(self.profile_button)

        layout.addSpacing(pad // 2)

        self.new_terminal_btn = self._build_icon_button(
            "terminalNewBtn", load_icon("terminal_bar/plus.svg"), "New Terminal"
        )
        self.new_terminal_btn.clicked.connect(self._create_new_session)
        layout.addWidget(self.new_terminal_btn)

        self.session_dropdown_btn = self._build_icon_button(
            "terminalDropdownBtn", load_icon("terminal_bar/chevron-down.svg"), "Switch Terminal"
        )
        self.session_dropdown_btn.setPopupMode(QToolButton.InstantPopup)
        self.session_dropdown_menu = QMenu(self.session_dropdown_btn)
        self.session_dropdown_btn.setMenu(self.session_dropdown_menu)
        layout.addWidget(self.session_dropdown_btn)

        self.split_btn = self._build_icon_button(
            "terminalSplitBtn", load_icon("terminal_bar/split.svg"), "Split Terminal (coming soon)"
        )
        self.split_btn.setEnabled(False)
        layout.addWidget(self.split_btn)

        self.kill_btn = self._build_icon_button(
            "terminalKillBtn", load_icon("terminal_bar/trash.svg"), "Kill Terminal"
        )
        self.kill_btn.clicked.connect(self._kill_current_session)
        layout.addWidget(self.kill_btn)

        self.menu_btn = self._build_icon_button(
            "terminalMenuBtn", load_icon("terminal_bar/ellipsis.svg"), "More actions"
        )
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.overflow_menu = QMenu(self.menu_btn)
        self.overflow_menu.addAction("Open External Terminal", self._open_external_terminal)
        self.overflow_menu.addSeparator()
        self.overflow_menu.addAction("Terminal Settings (stub)")
        self.menu_btn.setMenu(self.overflow_menu)
        layout.addWidget(self.menu_btn)

        return toolbar

    def _build_icon_button(
        self, object_name: str, icon: QIcon, tooltip: str, with_text: bool = False
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(object_name)
        button.setAutoRaise(True)
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon if with_text else Qt.ToolButtonIconOnly)
        button.setCursor(Qt.PointingHandCursor)
        button.setIcon(icon)
        button.setText(self.active_profile if with_text else "")
        button.setToolTip(tooltip)
        button.setProperty("category", "panelBar")
        return button

    def _refresh_profile_menu(self) -> None:
        self.profile_menu.clear()
        for name, command in self.profile_commands.items():
            action = self.profile_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == self.active_profile)
            action.triggered.connect(lambda checked, n=name, c=command: self._set_active_profile(n, c))

    def _set_active_profile(self, name: str, command: str | None = None) -> None:
        self.active_profile = name
        if command:
            self.profile_commands[name] = command
        self.profile_button.setText(name)
        self._refresh_profile_menu()

    def _rebuild_session_menu(self) -> None:
        self.session_dropdown_menu.clear()
        for index, session in enumerate(self.sessions):
            action = self.session_dropdown_menu.addAction(session.name)
            action.setCheckable(True)
            action.setChecked(index == self.current_session_index)
            action.triggered.connect(lambda checked, i=index: self._switch_to_session(i))

    def _create_initial_session(self) -> None:
        """Create the first terminal session."""
        self._create_new_session()

    def _create_new_session(self) -> None:
        """Create a new terminal session."""
        # Determine working directory
        working_dir = Path(self.workspace_manager.current_workspace or Path.cwd())

        # Create terminal
        terminal = PTYTerminal(self)
        shell_command = self.profile_commands.get(self.active_profile)
        if shell_command:
            terminal.shell = shell_command
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

        self._rebuild_session_menu()
        self.session_dropdown_btn.setToolTip(session_name)

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
            self.session_dropdown_btn.setToolTip(self.sessions[index].name)
            self._rebuild_session_menu()

            # Update working directory label
            current_session = self.sessions[index]
            current_dir = current_session.terminal.get_working_directory()
            self._update_status_label(current_dir)

    def _on_session_changed(self, index: int) -> None:
        """Handle session list selection change."""
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
        session.terminal.send_interrupt()
        session.terminal.clear_output()

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
