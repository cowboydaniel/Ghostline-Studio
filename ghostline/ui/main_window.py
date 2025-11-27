"""Main window for Ghostline Studio."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAction,
    QFileDialog,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from ghostline.core.config import ConfigManager
from ghostline.core.theme import ThemeManager
from ghostline.editor.code_editor import CodeEditor
from ghostline.ui.command_palette import CommandPalette
from ghostline.ui.status_bar import StudioStatusBar
from ghostline.ui.tabs import EditorTabs
from ghostline.workspace.workspace_manager import WorkspaceManager
from ghostline.terminal.terminal_widget import TerminalWidget
from ghostline.vcs.git_integration import GitIntegration

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Hosts docks, tabs, and menus."""

    def __init__(
        self, config: ConfigManager, theme: ThemeManager, workspace_manager: WorkspaceManager
    ) -> None:
        super().__init__()
        self.config = config
        self.theme = theme
        self.workspace_manager = workspace_manager
        self.git = GitIntegration()

        self.setWindowTitle("Ghostline Studio")
        self.resize(1200, 800)

        self.editor_tabs = EditorTabs(self)
        self.setCentralWidget(self.editor_tabs)

        self.status = StudioStatusBar(self.git)
        self.setStatusBar(self.status)

        self.command_palette = CommandPalette(self)
        self._create_actions()
        self._create_menus()
        self._create_terminal_dock()

    def _create_actions(self) -> None:
        self.action_open_file = QAction("Open File", self)
        self.action_open_file.triggered.connect(self._prompt_open_file)

        self.action_open_folder = QAction("Open Folder", self)
        self.action_open_folder.triggered.connect(self._prompt_open_folder)

        self.action_command_palette = QAction("Command Palette", self)
        self.action_command_palette.setShortcut("Ctrl+P")
        self.action_command_palette.triggered.connect(self.show_command_palette)

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.action_open_file)
        file_menu.addAction(self.action_open_folder)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.action_command_palette)

    def _create_terminal_dock(self) -> None:
        dock = QDockWidget("Terminal", self)
        dock.setObjectName("terminalDock")
        dock.setWidget(TerminalWidget(self.workspace_manager))
        dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

    def show_command_palette(self) -> None:
        self.command_palette.set_commands(
            {
                "Open File": self._prompt_open_file,
                "Open Folder": self._prompt_open_folder,
                "Save All": self.save_all,
            }
        )
        self.command_palette.open_palette()

    def open_file(self, path: str) -> None:
        editor = self.editor_tabs.add_editor_for_file(Path(path))
        self.status.show_path(path)
        self.workspace_manager.register_recent(path)
        self.status.update_git(self.workspace_manager.current_workspace)
        logger.info("Opened file: %s", path)

    def open_folder(self, folder: str) -> None:
        self.workspace_manager.open_workspace(folder)
        self.status.update_git(folder)
        self.status.show_message(f"Opened workspace: {folder}")

    def save_all(self) -> None:
        for editor in self.editor_tabs.iter_editors():
            editor.save()
        self.status.show_message("Saved all files")

    def get_current_editor(self) -> CodeEditor | None:
        return self.editor_tabs.current_editor()

    def register_dock(self, identifier: str, widget: QDockWidget) -> None:
        widget.setObjectName(identifier)
        self.addDockWidget(Qt.RightDockWidgetArea, widget)

    def execute_command(self, command_id: str, **kwargs) -> None:
        commands = {
            "file.save_all": self.save_all,
        }
        if command_id in commands:
            commands[command_id](**kwargs)

    def _prompt_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open File")
        if path:
            self.open_file(path)

    def _prompt_open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder:
            self.open_folder(folder)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.workspace_manager.save_recents()
        super().closeEvent(event)
