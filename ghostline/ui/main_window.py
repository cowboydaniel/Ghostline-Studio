"""Main window for Ghostline Studio."""
from __future__ import annotations

import importlib.metadata as importlib_metadata
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from urllib import request
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QTimer, QByteArray, QUrl, QPoint, QEvent, QModelIndex, QSize
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QIcon, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMenuBar,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QWidgetAction,
    QWidget,
    QTableView,
    QInputDialog,
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QSplitter,
    QStackedLayout,
    QStackedWidget,
    QLineEdit,
    QMessageBox,
    QMenu,
    QStyle,
)

from ghostline.core.config import CONFIG_DIR, USER_SETTINGS_PATH, ConfigManager
from ghostline.core.events import CommandDescriptor, CommandRegistry
from ghostline.core.logging import LOG_DIR, LOG_FILE
from ghostline.core.resources import icon_path, load_icon
from ghostline.core.theme import ThemeManager
from ghostline.lang.diagnostics import DiagnosticsModel
from ghostline.lang.lsp_manager import LSPManager
from ghostline.agents.agent_manager import AgentManager
from ghostline.ai.ai_client import AIClient
from ghostline.ai.ai_chat_panel import AIChatPanel
from ghostline.ai.command_adapter import AICommandAdapter
from ghostline.ai.context_engine import ContextEngine
from ghostline.ai.ai_commands import ai_code_actions, explain_selection, refactor_selection
from ghostline.ai.analysis_service import AnalysisService
from ghostline.ai.architecture_assistant import ArchitectureAssistant
from ghostline.ai.doc_generator import DocGenerator
from ghostline.ai.navigation_assistant import NavigationAssistant
from ghostline.ai.workspace_memory import WorkspaceMemory
from ghostline.semantic.index_manager import SemanticIndexManager
from ghostline.semantic.query import SemanticQueryEngine
from ghostline.build.build_manager import BuildManager
from ghostline.editor.code_editor import CodeEditor
from ghostline.formatter.formatter_manager import FormatterManager
from ghostline.runtime.inspector import RuntimeInspector
from ghostline.indexer.index_manager import IndexManager
from ghostline.indexer.workspace_indexer import WorkspaceIndexer
from ghostline.search.symbol_search import SymbolSearcher
from ghostline.plugins.loader import PluginLoader
from ghostline.ui.docks.search_panel import SearchPanel
from ghostline.ui.dialogs.settings_dialog import SettingsDialog
from ghostline.ui.dialogs.plugin_manager_dialog import PluginManagerDialog
from ghostline.ui.dialogs.setup_wizard import SetupWizardDialog
from ghostline.ui.dialogs.ai_settings_dialog import AISettingsDialog
from ghostline.ui.dialogs.developer_tools import DeveloperToolsDialog, ProcessExplorerDialog, optional_psutil
from ghostline.ui.dialogs.playground_dialog import EditorPlaygroundDialog, WalkthroughDialog
from ghostline.ui.command_palette import CommandPalette
from ghostline.ui.commands.registry import CommandActionDefinition, CommandActionRegistry
from ghostline.ui.activity_bar import ActivityBar
from ghostline.ui.status_bar import StudioStatusBar
from ghostline.ui.layout_manager import LayoutManager
from ghostline.ui.editor.split_area import SplitEditorArea
from ghostline.ui.workspace_dashboard import WorkspaceDashboard
from ghostline.ui.welcome_portal import WelcomePortal
from ghostline.ui.widgets.ghost_terminal import GhostTerminalWidget
from ghostline.visual3d.architecture_dock import ArchitectureDock
from ghostline.ui.docks.build_panel import BuildPanel
from ghostline.ui.docks.agent_console import AgentConsole
from ghostline.ui.docks.collab_panel import CollabPanel
from ghostline.ui.docks.doc_panel import DocPanel
from ghostline.ui.docks.pipeline_panel import PipelinePanel
from ghostline.ui.docks.runtime_panel import RuntimePanel
from ghostline.ui.docks.bottom_panel import BottomPanel
from ghostline.ui.docks.panel_widgets import (
    ProblemsPanel,
    OutputPanel,
    DebugConsolePanel,
    PortsPanel,
)
from ghostline.workspace.workspace_manager import WorkspaceManager
from ghostline.workspace.project_model import ProjectModel
from ghostline.workspace.project_view import ProjectView
from ghostline.terminal.windsurf_terminal import WindsurfTerminalWidget
from ghostline.vcs.git_integration import GitIntegration
from ghostline.vcs.git_panel import GitPanel
from ghostline.vcs.git_service import GitService
from ghostline.debugger.debugger_manager import DebuggerManager
from ghostline.debugger.debugger_panel import DebuggerPanel
from ghostline.tasks.task_manager import TaskManager
from ghostline.tasks.task_panel import TaskPanel
from ghostline.testing.test_manager import TestManager
from ghostline.testing.test_panel import TestPanel
from ghostline.testing.coverage_panel import CoveragePanel
from ghostline.workflows.pipeline_manager import PipelineManager
from ghostline.collab.session_manager import SessionManager
from ghostline.collab.crdt_engine import CRDTEngine
from ghostline.collab.transport import WebSocketTransport

logger = logging.getLogger(__name__)


TITLE_MENU_STYLE = """
QMenu#TitleSettingsMenu {
    background: palette(window);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 6px;
}
QMenu#TitleSettingsMenu::item {
    padding: 6px 14px;
    border-radius: 6px;
    color: palette(text);
}
QMenu#TitleSettingsMenu::item:selected {
    background: rgba(255, 255, 255, 0.08);
}
QMenu#TitleSettingsMenu::separator {
    height: 1px;
    margin: 6px 4px;
    background: rgba(255, 255, 255, 0.08);
}
"""

DOCS_URL = QUrl("https://github.com/ghostline-studio/Ghostline-Studio#readme")
FEATURE_REQUEST_URL = QUrl("https://github.com/ghostline-studio/Ghostline-Studio/issues/new/choose")
COMMUNITY_URL = QUrl("https://github.com/ghostline-studio/Ghostline-Studio/discussions")
CHANGELOG_URL = QUrl("https://github.com/ghostline-studio/Ghostline-Studio/releases")


class TitleContextLineEdit(QLineEdit):
    """Line edit that shows project/file context while remaining searchable."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context_text: str = ""
        self._user_active = False

    def set_context_text(self, text: str) -> None:
        self._context_text = text
        if not self._user_active and (not self.text() or self.text() == self._context_text or not self.hasFocus()):
            self.setText(text)

    def show_context_if_idle(self) -> None:
        self._user_active = False
        self.setText(self._context_text)

    def focusInEvent(self, event) -> None:  # type: ignore[override]
        self._user_active = True
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        super().focusOutEvent(event)
        self._user_active = False
        if not self.text().strip():
            self.setText(self._context_text)


class GhostlineTitleBar(QWidget):
    """Custom frameless title bar with navigation and context display."""

    HEIGHT = 35
    CONTENT_HEIGHT = 26
    H_MARGIN = 6
    V_MARGIN = 2
    SECTION_SPACING = 4
    ICON_SIZE = QSize(14, 14)
    CONTROL_SIZE = QSize(24, 24)
    BUTTON_SPACING = 4
    MENU_ITEM_H_PADDING = 6
    MENU_ITEM_V_PADDING = 2
    MENU_ITEM_MARGIN = 1
    TOOLBUTTON_H_PADDING = 5
    TOOLBUTTON_V_PADDING = 3
    CONTROL_MARGIN = 1
    PILL_H_PADDING = 9
    PILL_V_PADDING = 3

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self._drag_position: QPoint | None = None

        self.setObjectName("GhostlineTitleBar")
        self.setFixedHeight(self.HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(self.H_MARGIN, self.V_MARGIN, self.H_MARGIN, self.V_MARGIN)
        layout.setSpacing(self.SECTION_SPACING)

        left_container = QWidget(self)
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(self.BUTTON_SPACING)
        left_layout.setAlignment(Qt.AlignVCenter)

        icon_button = QToolButton(left_container)
        icon_button.setObjectName("TitleIconButton")
        icon_button.setIcon(load_icon("ghostline_logo.svg"))
        icon_button.setIconSize(self.ICON_SIZE)
        icon_button.setFixedHeight(self.CONTENT_HEIGHT)
        icon_button.setAutoRaise(True)
        icon_button.setToolTip("Ghostline Studio")
        left_layout.addWidget(icon_button)

        menubar: QMenuBar = self.window.menuBar()
        menubar.setNativeMenuBar(False)
        menubar.setFixedHeight(self.CONTENT_HEIGHT)
        menubar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        left_layout.addWidget(menubar)

        center_container = QWidget(self)
        center_layout = QHBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(self.BUTTON_SPACING - 1)
        center_layout.setAlignment(Qt.AlignVCenter)

        # TODO: Wire navigation buttons to history actions when available.
        self.back_button = QToolButton(center_container)
        self.back_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.back_button.setIconSize(self.ICON_SIZE)
        self.back_button.setFixedHeight(self.CONTENT_HEIGHT)
        self.back_button.setAutoRaise(True)
        self.back_button.setEnabled(False)
        self.back_button.setToolTip("Back (not yet implemented)")
        center_layout.addWidget(self.back_button)

        self.forward_button = QToolButton(center_container)
        self.forward_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.forward_button.setIconSize(self.ICON_SIZE)
        self.forward_button.setFixedHeight(self.CONTENT_HEIGHT)
        self.forward_button.setAutoRaise(True)
        self.forward_button.setEnabled(False)
        self.forward_button.setToolTip("Forward (not yet implemented)")
        center_layout.addWidget(self.forward_button)

        self.command_input = TitleContextLineEdit(center_container)
        self.command_input.setObjectName("CommandSearch")
        self.command_input.setAlignment(Qt.AlignCenter)
        self.command_input.setMinimumWidth(240)
        self.command_input.setMaximumWidth(420)
        self.command_input.setFixedHeight(self.CONTENT_HEIGHT)
        self.command_input.setReadOnly(True)
        self.command_input.setCursor(Qt.ArrowCursor)
        self.command_input.returnPressed.connect(self._emit_command_search)
        center_layout.addWidget(self.command_input)
        center_layout.addStretch(1)

        dock_toggle_bar = getattr(self.window, "dock_toggle_bar", None)

        dock_container = QWidget(self)
        dock_container.setObjectName("DockToggleContainer")
        dock_layout = QHBoxLayout(dock_container)
        dock_layout.setContentsMargins(0, 0, 0, 0)
        dock_layout.setSpacing(0)
        if dock_toggle_bar:
            dock_layout.addWidget(dock_toggle_bar)

        right_container = QWidget(self)
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(self.BUTTON_SPACING - 1)
        right_layout.setAlignment(Qt.AlignVCenter)

        self.settings_button = QToolButton(right_container)
        self.settings_button.setObjectName("TitleBarIcon")
        self.settings_button.setIcon(load_icon("configure.svg"))
        self.settings_button.setIconSize(self.ICON_SIZE)
        self.settings_button.setFixedHeight(self.CONTENT_HEIGHT)
        self.settings_button.setAutoRaise(True)
        self.settings_button.clicked.connect(self._show_settings_menu)
        right_layout.addWidget(self.settings_button)

        self.profile_button = QToolButton(right_container)
        self.profile_button.setObjectName("TitleBarIcon")
        self.profile_button.setIcon(load_icon("creator_ghost.svg"))
        self.profile_button.setIconSize(self.ICON_SIZE)
        self.profile_button.setFixedHeight(self.CONTENT_HEIGHT)
        self.profile_button.setAutoRaise(True)
        self.profile_button.clicked.connect(self._show_profile_menu)
        right_layout.addWidget(self.profile_button)

        self.minimize_button = QToolButton(right_container)
        self.minimize_button.setObjectName("WindowControl")
        self.minimize_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMinButton))
        self.minimize_button.setIconSize(self.ICON_SIZE)
        self.minimize_button.setFixedSize(self.CONTROL_SIZE)
        self.minimize_button.clicked.connect(self.window.showMinimized)
        right_layout.addWidget(self.minimize_button)

        self.maximize_button = QToolButton(right_container)
        self.maximize_button.setObjectName("WindowControl")
        self.maximize_button.setIconSize(self.ICON_SIZE)
        self.maximize_button.setFixedSize(self.CONTROL_SIZE)
        self.maximize_button.clicked.connect(self.window.toggle_maximize_restore)
        right_layout.addWidget(self.maximize_button)

        self.close_button = QToolButton(right_container)
        self.close_button.setObjectName("CloseControl")
        self.close_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.close_button.setIconSize(self.ICON_SIZE)
        self.close_button.setFixedSize(self.CONTROL_SIZE)
        self.close_button.clicked.connect(self.window.close)
        right_layout.addWidget(self.close_button)

        layout.addWidget(left_container)
        layout.addWidget(center_container, 1)
        if dock_toggle_bar:
            layout.addWidget(dock_container, 0, Qt.AlignVCenter)
        layout.addStretch()
        layout.addWidget(right_container)

        self._apply_styles()
        self.update_maximize_icon()

    def _create_title_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setObjectName("TitleSettingsMenu")
        menu.setStyleSheet(TITLE_MENU_STYLE)
        return menu

    def _show_settings_menu(self) -> None:
        menu = self._create_title_menu()

        menu.addAction(self.window.action_editor_settings)
        menu.addAction(self.window.action_ghostline_settings)
        menu.addSeparator()
        menu.addAction(self.window.action_extensions)
        menu.addAction(self.window.action_keyboard_shortcuts)
        menu.addAction(self.window.action_configure_snippets)
        menu.addSeparator()
        menu.addAction(self.window.action_tasks_view)

        pos = self.settings_button.mapToGlobal(QPoint(0, self.settings_button.height()))
        menu.exec(pos)

    def _show_profile_menu(self) -> None:
        user_name, user_email = self.window._current_user_identity()
        menu = self._create_title_menu()

        account_menu = menu.addMenu(f"{user_name} (Ghostline Auth)")
        account_menu.addAction("Sign in...", self.window._trigger_sign_in_placeholder)
        sign_out_action = account_menu.addAction("Sign out", self.window._trigger_sign_out_placeholder)
        sign_out_action.setEnabled(bool(user_email))
        account_menu.addAction("Manage Account...", self.window._trigger_manage_account_placeholder)

        menu.addAction(
            f"Ghostline Account ({user_email if user_email else 'not signed in'})",
            self.window._show_account_details,
        )
        menu.addAction(self.window.action_ghostline_settings)
        menu.addAction("Ghostline Usage", self.window._show_usage_placeholder)
        menu.addAction("Quick Settings Panel", self.window._open_quick_settings_placeholder)
        menu.addSeparator()
        menu.addAction("Check for Updates...", self.window._check_for_updates)
        menu.addSeparator()
        menu.addAction("Docs", self.window._open_docs)
        menu.addAction("Feature Request", self.window._open_feature_request)
        menu.addAction("Join the Community", self.window._open_community)
        menu.addAction("Changelog", self.window._open_changelog)
        menu.addSeparator()
        themes_menu = menu.addMenu("Themes")
        self.window._populate_theme_menu(themes_menu)
        menu.addSeparator()
        menu.addAction("Download Diagnostics", self.window._download_diagnostics)

        pos = self.profile_button.mapToGlobal(QPoint(0, self.profile_button.height()))
        menu.exec(pos)

    def _emit_command_search(self) -> None:
        query = self.command_input.text().strip()
        self.window.show_command_palette(query or None)
        self.command_input.show_context_if_idle()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            #GhostlineTitleBar {{
                background: palette(window);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }}
            #GhostlineTitleBar QWidget {{
                background: transparent;
            }}
            #GhostlineTitleBar QMenuBar {{
                background: transparent;
                border: none;
                padding: 0;
                font-size: 11px;
            }}
            #GhostlineTitleBar QToolBar {{
                background: transparent;
                border: none;
                spacing: 0;
            }}
            #GhostlineTitleBar QMenuBar::item {{
                padding: {self.MENU_ITEM_V_PADDING}px {self.MENU_ITEM_H_PADDING}px;
                margin: 0 {self.MENU_ITEM_MARGIN}px;
                border-radius: 5px;
            }}
            #GhostlineTitleBar QMenuBar::item:selected {{
                background: rgba(255, 255, 255, 0.06);
            }}
            #GhostlineTitleBar QToolButton,
            #GhostlineTitleBar #TitleBarIcon {{
                background: transparent;
                border: none;
                padding: {self.TOOLBUTTON_V_PADDING}px {self.TOOLBUTTON_H_PADDING}px;
                border-radius: 5px;
                color: #c8c8c8;
            }}
            #GhostlineTitleBar QToolButton:hover,
            #GhostlineTitleBar #TitleBarIcon:hover {{
                background: rgba(255, 255, 255, 0.05);
                color: #e0e0e0;
            }}
            #WindowControl {{
                background: transparent;
                border: none;
                padding: {self.TOOLBUTTON_V_PADDING}px {self.TOOLBUTTON_H_PADDING}px;
                margin-left: {self.CONTROL_MARGIN}px;
                border-radius: 5px;
                color: #c8c8c8;
            }}
            #WindowControl:hover {{
                background: rgba(255, 255, 255, 0.05);
                color: #f0f0f0;
            }}
            #CloseControl {{
                background: transparent;
                border: none;
                padding: {self.TOOLBUTTON_V_PADDING}px {self.TOOLBUTTON_H_PADDING}px;
                margin-left: {self.CONTROL_MARGIN}px;
                border-radius: 5px;
                color: #d8d8d8;
            }}
            #CloseControl:hover {{
                background: rgba(232, 89, 89, 0.12);
                color: #ff9a9a;
            }}
            #CommandSearch {{
                border-radius: 8px;
                padding: {self.PILL_V_PADDING}px {self.PILL_H_PADDING}px;
                background: rgba(255, 255, 255, 0.025);
                border: 1px solid rgba(255, 255, 255, 0.04);
                min-height: {self.CONTENT_HEIGHT}px;
                font-size: 11px;
                color: #d0d0d0;
            }}
            #CommandSearch:focus {{
                border: 1px solid rgba(255, 255, 255, 0.04);
                outline: none;
            }}
        """
        )

    def set_context_text(self, text: str) -> None:
        self.command_input.set_context_text(text)

    def update_maximize_icon(self) -> None:
        icon = (
            self.style().standardIcon(QStyle.SP_TitleBarNormalButton)
            if self.window.isMaximized()
            else self.style().standardIcon(QStyle.SP_TitleBarMaxButton)
        )
        self.maximize_button.setIcon(icon)
        self.maximize_button.setToolTip("Restore" if self.window.isMaximized() else "Maximize")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton and not self._is_interactive_child(event.pos()):
            self._drag_position = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_position and event.buttons() & Qt.LeftButton and not self.window.isMaximized():
            self.window.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if not self._is_interactive_child(event.pos()):
            self.window.toggle_maximize_restore()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _is_interactive_child(self, pos) -> bool:
        target = self.childAt(pos)
        return isinstance(target, (QToolButton, QLineEdit, QMenuBar))


class MainWindow(QMainWindow):
    """Hosts docks, tabs, and menus."""

    konami_sequence = [
        Qt.Key_Up,
        Qt.Key_Up,
        Qt.Key_Down,
        Qt.Key_Down,
        Qt.Key_Left,
        Qt.Key_Right,
        Qt.Key_Left,
        Qt.Key_Right,
        Qt.Key_B,
        Qt.Key_A,
    ]

    def __init__(
        self, config: ConfigManager, theme: ThemeManager, workspace_manager: WorkspaceManager
    ) -> None:
        super().__init__(None, Qt.Window)  # Set window type and parent
        # Ensure proper window flags for custom title bar controls
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        # Ensure the window has proper size constraints
        self.setMinimumSize(800, 600)
        self.config = config
        self.theme = theme
        self._theme_actions: dict[str, QAction] = {}
        self._apply_theme_from_config()
        self.workspace_manager = workspace_manager
        self.git = GitIntegration()
        self.lsp_manager = LSPManager(config, workspace_manager)
        self.workspace_manager.workspaceChanged.connect(lambda _=None: self._refresh_recent_views())
        self.workspace_manager.workspaceChanged.connect(lambda _=None: self._update_title_context())
        self.command_registry = CommandRegistry()
        # Register core commands before creating UI components
        self._register_core_commands()
        self.ai_client = AIClient(config)
        self.workspace_indexer = WorkspaceIndexer(lambda: self.workspace_manager.current_workspace)
        self.symbols = SymbolSearcher(self.lsp_manager)
        self.index_manager = IndexManager(lambda: self.workspace_manager.current_workspace)
        self.semantic_index = SemanticIndexManager(lambda: self.workspace_manager.current_workspace)
        self.semantic_query = SemanticQueryEngine(self.semantic_index.graph)
        self.workspace_memory = WorkspaceMemory(self.config.workspace_memory_path)
        self.context_engine = ContextEngine(
            self.workspace_indexer,
            self.semantic_index,
            self.symbols,
            self.workspace_memory,
            max_snippet_chars=self.config.get("ai", {}).get("max_context_chars", 800),
            max_results=self.config.get("ai", {}).get("context_results", 5),
        )
        self.agent_manager = AgentManager(self.workspace_memory, self.semantic_index.graph)
        self.semantic_index.register_observer(self._on_semantic_graph_changed)
        pipeline_config = Path(__file__).resolve().parent.parent / "workflows" / "pipeline.yaml"
        self.pipeline_manager = PipelineManager(pipeline_config, self.agent_manager)
        self.runtime_inspector = RuntimeInspector(self.semantic_index.graph)
        self.architecture_assistant = ArchitectureAssistant(self.ai_client, self.semantic_query)
        self.navigation_assistant = NavigationAssistant(self.ai_client, self.semantic_query)
        self.doc_generator = DocGenerator(self.ai_client, self.semantic_query)
        self.build_manager = BuildManager(lambda: self.workspace_manager.current_workspace)
        self.analysis_service = AnalysisService(self.ai_client)
        self.formatter = FormatterManager(self.lsp_manager)
        self.debugger = DebuggerManager()
        self.debugger.set_runtime_inspector(self.runtime_inspector)
        self.task_manager = TaskManager(lambda: self.workspace_manager.current_workspace)
        self.test_manager = TestManager(
            self.task_manager, lambda: self.workspace_manager.current_workspace, semantic_query=self.semantic_query
        )
        self.session_manager = SessionManager()
        self.crdt_engine = CRDTEngine()
        self.collab_transport = WebSocketTransport()
        self.plugin_loader = PluginLoader(self, self.command_registry, self.menuBar(), self)
        self._psutil = optional_psutil()
        self._developer_tools_dialog: DeveloperToolsDialog | None = None
        self._process_explorer_dialog: ProcessExplorerDialog | None = None
        self._playground_dialog: EditorPlaygroundDialog | None = None
        self._walkthrough_dialog: WalkthroughDialog | None = None
        self.layout_manager = LayoutManager(self)
        self.git_service = GitService(self.workspace_manager.current_workspace)
        self.first_run = not bool(self.config.get("first_run_completed", False))
        self._restored_workspace: str | None = None
        self.left_docks: list[QDockWidget] = []
        self.bottom_docks: list[QDockWidget] = []
        self.right_docks: list[QDockWidget] = []
        self._konami_index = 0
        self._konami_reset_timer = QTimer(self)
        self._konami_reset_timer.setSingleShot(True)
        self._konami_reset_timer.timeout.connect(self._reset_konami_index)
        ui_settings = self.config.get("ui", {}) if self.config else {}
        self.konami_enabled = bool(ui_settings.get("konami_enabled", True))
        self.view_settings = self.config.settings.setdefault("view", {}) if self.config else {}
        self.view_settings.setdefault("bars", {})
        self.view_settings.setdefault("panels", {})
        editor_view_cfg = self.config.settings.setdefault("editor", {}) if self.config else {}
        self._word_wrap_enabled = bool(self.view_settings.get("word_wrap", editor_view_cfg.get("word_wrap", False)))
        self._autosave_enabled = bool(self.config.get("autosave", {}).get("enabled", False))
        autosave_cfg = self.config.get("autosave", {}) if self.config else {}
        self._autosave_interval = int(autosave_cfg.get("interval_seconds", 60))
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._perform_autosave)

        self.setWindowTitle("Ghostline Studio")
        self.resize(1200, 800)

        self.editor_tabs = SplitEditorArea(
            self,
            config=self.config,
            theme=self.theme,
            lsp_manager=self.lsp_manager,
            ai_client=self.ai_client,
            command_registry=self.command_registry,
        )
        self.editor_tabs.countChanged.connect(self._show_welcome_if_empty)
        self.editor_tabs.countChanged.connect(lambda _=None: self._update_title_context())
        self.editor_tabs.currentChanged.connect(lambda _=None: self._update_title_context())

        self.activity_bar = ActivityBar(self)

        self.editor_container = QWidget(self)
        self.editor_container.setObjectName("EditorArea")
        editor_layout = QHBoxLayout(self.editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        editor_layout.addWidget(self.editor_tabs, 1)

        self.welcome_portal = WelcomePortal(self, config=self.config)
        self.welcome_portal.openFolderRequested.connect(self._prompt_open_folder)
        self.welcome_portal.openCommandPaletteRequested.connect(lambda: self.show_command_palette())
        self.welcome_portal.openAIChatRequested.connect(self.toggle_ai_dock)
        self.welcome_portal.openRecentRequested.connect(self._open_recent_item)

        self.workspace_dashboard = WorkspaceDashboard(
            open_file=self.open_file,
            open_palette=lambda: self.show_command_palette(),
        )

        self.central_stack = QStackedWidget(self)
        self.central_stack.addWidget(self.welcome_portal)
        self.central_stack.addWidget(self.workspace_dashboard)
        self.central_stack.addWidget(self.editor_container)

        self.left_region_container = QWidget(self)
        self.left_region_layout = QHBoxLayout(self.left_region_container)
        self.left_region_layout.setContentsMargins(0, 0, 0, 0)
        self.left_region_layout.setSpacing(0)
        self.activity_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.left_region_layout.addWidget(self.activity_bar)
        self.left_dock_container = QWidget(self.left_region_container)
        self.left_dock_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.left_dock_container.setMinimumWidth(180)  # Reduced from 220 for small screens
        left_dock_layout = QVBoxLayout(self.left_dock_container)
        left_dock_layout.setContentsMargins(0, 0, 0, 0)
        left_dock_layout.setSpacing(0)
        self.left_dock_stack = QStackedWidget(self.left_dock_container)
        left_dock_layout.addWidget(self.left_dock_stack)
        self.left_region_layout.addWidget(self.left_dock_container, 1)

        self.central_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.right_region_container = QWidget(self)
        self.right_region_layout = QVBoxLayout(self.right_region_container)
        self.right_region_layout.setContentsMargins(0, 0, 0, 0)
        self.right_region_layout.setSpacing(0)
        self.right_dock_stack = QStackedWidget(self.right_region_container)
        self.right_region_layout.addWidget(self.right_dock_stack)

        self.left_region_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.left_region_container.setMinimumWidth(
            self.left_dock_container.minimumWidth() + self.activity_bar.sizeHint().width()
        )
        self.right_region_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # Reduced minimums for better small-screen support (1366x768)
        self.central_stack.setMinimumWidth(320)  # Reduced from 400
        self.right_region_container.setMinimumWidth(200)  # Reduced from 260

        # Create bottom panel (Windsurf-style with tabs)
        self.bottom_panel = BottomPanel(self)
        self.bottom_panel.setVisible(False)
        self._bottom_panel_previous_sizes: list[int] | None = None
        self._bottom_panel_maximized = False
        self._bottom_panel_collapsed = False

        # Connect close button
        self.bottom_panel.get_close_button().clicked.connect(
            lambda: self._toggle_bottom_region(False)
        )
        self.bottom_panel.tab_bar.panel_close_requested.connect(
            lambda: self._toggle_bottom_region(False)
        )
        self.bottom_panel.tab_bar.panel_maximize_requested.connect(self._toggle_bottom_panel_maximize)
        self.bottom_panel.tab_bar.panel_collapse_requested.connect(self._toggle_bottom_panel_collapse)

        # Create vertical splitter for center region (editor + bottom panel)
        self.center_vertical_splitter = QSplitter(Qt.Vertical, self)
        self.center_vertical_splitter.setChildrenCollapsible(False)
        self.center_vertical_splitter.addWidget(self.central_stack)
        self.center_vertical_splitter.addWidget(self.bottom_panel)
        self.center_vertical_splitter.setStretchFactor(0, 1)  # Editor expands
        self.center_vertical_splitter.setStretchFactor(1, 0)  # Bottom panel fixed height

        # Set initial sizes for center vertical splitter (75% editor, 25% terminal when shown)
        # More generous to editor on small screens
        total_height = self.height() or 800
        self.center_vertical_splitter.setSizes([int(total_height * 0.75), int(total_height * 0.25)])

        self.main_splitter = QSplitter(Qt.Horizontal, self)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.left_region_container)
        self.main_splitter.addWidget(self.center_vertical_splitter)
        self.main_splitter.addWidget(self.right_region_container)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)

        # Better proportions for small screens: 18% left, 60% center, 22% right
        # This gives more room to the editor area
        total_width = self.width() or 1400
        self.main_splitter.setSizes(
            [int(total_width * 0.18), int(total_width * 0.60), int(total_width * 0.22)]
        )

        self.status = StudioStatusBar(self.git)
        self.setStatusBar(self.status)
        self.status.setContentsMargins(4, 0, 12, 0)
        self.analysis_service.suggestions_changed.connect(lambda items: self.status.set_ai_suggestions_available(bool(items)))

        self.setStyleSheet(
            """
            QMainWindow::separator { background: palette(mid); width: 6px; }
            QMainWindow::separator:hover { background: palette(highlight); }
            QDockWidget::title { font-size: 12px; padding: 6px 8px; }
            QTreeView { font-size: 12px; }
            QStatusBar QLabel { font-size: 11px; }
            #ActivityBar {
                background: palette(midlight);
                border-right: 1px solid palette(mid);
            }
            #ActivityBar QToolButton {
                border: none;
                padding: 10px 6px;
                margin: 2px 6px;
                border-radius: 8px;
                color: palette(mid);
            }
            #ActivityBar QToolButton:hover {
                background: palette(button);
                color: palette(text);
            }
            #ActivityBar QToolButton:checked {
                background: palette(highlight);
                color: palette(highlightedText);
                border-left: 3px solid palette(highlightedText);
                padding-left: 4px;
            }
            """
        )

        self._setup_global_search_toolbar()
        self.command_palette = CommandPalette(self)
        self.command_palette.set_registry(self.command_registry)
        self.command_palette.set_navigation_assistant(self.navigation_assistant)
        self.command_palette.set_autoflow_mode("passive")
        self.command_palette.set_file_provider(self._search_workspace_files)
        self.command_palette.set_open_file_handler(self.open_file)
        self.command_palette.set_theme_manager(self.theme)
        self.ai_command_adapter = AICommandAdapter(self.command_registry, self.command_palette)
        self._create_actions()
        self._create_menus()
        self._install_title_bar()
        self._create_terminal_dock()
        self._create_project_dock()
        self._create_search_dock()
        self._create_ai_dock()
        self._create_diagnostics_dock()
        self._create_debugger_dock()
        self._create_task_dock()
        self._create_test_dock()
        self._create_git_dock()
        self._create_coverage_dock()
        self._create_collaboration_dock()
        self._create_architecture_dock()
        self._create_build_dock()
        self._create_doc_dock()
        self._create_agent_console_dock()
        self._create_pipeline_dock()
        self._create_runtime_dock()
        self._connect_activity_bar()

        self.lsp_manager.subscribe_diagnostics(self._handle_diagnostics)
        self.lsp_manager.lsp_error.connect(lambda msg: self.status.show_message(msg))
        self.lsp_manager.lsp_notice.connect(lambda msg: self.status.show_message(msg))
        self.plugin_loader.load_all()
        self.task_manager.load_workspace_tasks()
        self._configure_dock_corners()
        self._apply_initial_layout()
        self._collect_dock_regions()
        self._restore_dock_state()  # Restore saved dock/panel states after collection
        self._apply_view_preferences()
        self._connect_dock_toggles()
        self._update_workspace_state()
        self._show_welcome_if_empty()
        self._update_title_context()

    def _setup_global_search_toolbar(self) -> None:
        icon_dir = Path(__file__).resolve().parent.parent / "resources" / "icons" / "dock_controls"

        def load_icon(name: str) -> QIcon:
            return QIcon(str(icon_dir / f"{name}.svg"))

        left_open_icon = load_icon("left_open")
        left_closed_icon = load_icon("left_closed")
        bottom_open_icon = load_icon("bottom_open")
        bottom_closed_icon = load_icon("bottom_closed")
        right_open_icon = load_icon("right_open")
        right_closed_icon = load_icon("right_closed")

        self.dock_toggle_bar = QToolBar("Dock Visibility", self)
        self.dock_toggle_bar.setMovable(False)
        self.dock_toggle_bar.setFloatable(False)
        self.dock_toggle_bar.setToolButtonStyle(Qt.ToolButtonIconOnly)

        toggle_spacer = QWidget(self.dock_toggle_bar)
        toggle_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toggle_spacer.setStyleSheet("background: transparent;")
        self.dock_toggle_bar.addWidget(toggle_spacer)

        def build_toggle(open_icon: QIcon, closed_icon: QIcon, tooltip: str) -> QAction:
            action = QAction(open_icon, "", self)
            action.setCheckable(True)
            action.setChecked(True)
            action.setToolTip(tooltip)
            action.toggled.connect(lambda checked, a=action, o=open_icon, c=closed_icon: a.setIcon(o if checked else c))
            button = QToolButton(self.dock_toggle_bar)
            button.setDefaultAction(action)
            button.setAutoRaise(True)
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            # Use size hint instead of fixed size for DPI scaling
            button.setMinimumSize(QSize(22, 22))
            button.setMaximumSize(QSize(24, 24))
            button.setIconSize(QSize(14, 14))
            button.setStyleSheet("padding: 0; margin: 0;")
            widget_action = QWidgetAction(self.dock_toggle_bar)
            widget_action.setDefaultWidget(button)
            self.dock_toggle_bar.addAction(widget_action)
            return action

        self.toggle_left_region = build_toggle(left_open_icon, left_closed_icon, "Toggle left docks")
        self.toggle_bottom_region = build_toggle(bottom_open_icon, bottom_closed_icon, "Toggle bottom docks")
        self.toggle_right_region = build_toggle(right_open_icon, right_closed_icon, "Toggle right docks")

    def _install_title_bar(self) -> None:
        self.title_bar = GhostlineTitleBar(self)
        self.setMenuWidget(self.title_bar)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.main_splitter, 1)

        self.setCentralWidget(container)

    def _show_welcome_if_empty(self) -> None:
        """Show welcome screen when no files are open, even if workspace is open."""
        if self.editor_tabs.count() > 0:
            self.central_stack.setCurrentWidget(self.editor_container)
        else:
            workspace = self.workspace_manager.current_workspace
            files = self.workspace_manager.get_recent_files(workspace) if workspace else self.workspace_manager.get_recent_files()
            self.welcome_portal.set_recent_files(files)
            self.central_stack.setCurrentWidget(self.welcome_portal)

    def _refresh_recent_views(self) -> None:
        workspace = self.workspace_manager.current_workspace
        if workspace:
            files = self.workspace_manager.get_recent_files(workspace)
            self.workspace_dashboard.set_workspace(workspace, files)
        self.welcome_portal.set_recent_files(self.workspace_manager.get_recent_files())

    def _restore_workspace_tabs(self, workspace_str: str | None) -> None:
        if not workspace_str:
            return
        if self._restored_workspace == workspace_str:
            return
        workspace_sessions = self.config.settings.get("workspace_sessions", {})
        session_state = workspace_sessions.get(workspace_str)
        if session_state:
            self.editor_tabs.restore_session_state(session_state)
        self._restored_workspace = workspace_str

    def _apply_initial_layout(self) -> None:
        optional_right = [
            getattr(self, name)
            for name in (
                "coverage_dock",
                "collab_dock",
                "pipeline_dock",
                "runtime_dock",
                "doc_dock",
                "agent_console_dock",
                "architecture_dock",
                "git_dock",
            )
            if hasattr(self, name)
        ]
        for dock in optional_right:
            dock.hide()

        bottom_docks = [
            getattr(self, name)
            for name in ("terminal_dock", "diagnostics_dock", "task_dock", "test_dock", "build_dock")
            if hasattr(self, name)
        ]
        for dock in bottom_docks:
            dock.hide()
        if self.bottom_panel:
            self.bottom_panel.setVisible(False)
            if hasattr(self, "toggle_bottom_region"):
                self.toggle_bottom_region.setChecked(False)

        if self.first_run and hasattr(self, "debugger_dock"):
            self._show_and_raise_dock(self.debugger_dock)

        self._enforce_dock_policies()

    def _configure_dock_corners(self) -> None:
        return

    def _enforce_dock_policies(self) -> None:
        self.right_region_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def apply_initial_window_state(self, force_maximize: bool = False) -> None:
        window_cfg = self.config.get("window", {}) if self.config else {}
        geometry_hex = window_cfg.get("geometry")
        if geometry_hex:
            try:
                self.restoreGeometry(QByteArray.fromHex(bytes(geometry_hex, "ascii")))
            except Exception:
                pass
        if force_maximize or window_cfg.get("maximized", True):
            self.showMaximized()

    def _restore_dock_state(self) -> None:
        """Restore dock/panel states and sizes from saved configuration."""
        if not self.config:
            return

        window_cfg = self.config.get("window", {})
        dock_state = window_cfg.get("dock_state", {})

        # Restore main splitter sizes (left/center/right regions)
        if hasattr(self, "main_splitter") and "main_splitter_sizes" in dock_state:
            try:
                self.main_splitter.setSizes(dock_state["main_splitter_sizes"])
            except Exception:
                pass

        # Restore center vertical splitter sizes (editor/bottom panel)
        if hasattr(self, "center_vertical_splitter") and "center_vertical_splitter_sizes" in dock_state:
            try:
                self.center_vertical_splitter.setSizes(dock_state["center_vertical_splitter_sizes"])
            except Exception:
                pass

        # Restore left dock stack current widget
        if hasattr(self, "left_dock_stack") and "left_dock_index" in dock_state:
            try:
                index = dock_state["left_dock_index"]
                if 0 <= index < self.left_dock_stack.count():
                    self.left_dock_stack.setCurrentIndex(index)
                    # Update visibility of left docks
                    for i in range(self.left_dock_stack.count()):
                        widget = self.left_dock_stack.widget(i)
                        if widget:
                            widget.setVisible(i == index)
            except Exception:
                pass

        # Restore right dock stack current widget
        if hasattr(self, "right_dock_stack") and "right_dock_index" in dock_state:
            try:
                index = dock_state["right_dock_index"]
                if 0 <= index < self.right_dock_stack.count():
                    self.right_dock_stack.setCurrentIndex(index)
                    # Update visibility of right docks
                    for i in range(self.right_dock_stack.count()):
                        widget = self.right_dock_stack.widget(i)
                        if widget:
                            widget.setVisible(i == index)
            except Exception:
                pass

        # Restore left region visibility
        if hasattr(self, "left_region_container") and "left_region_visible" in dock_state:
            try:
                visible = dock_state["left_region_visible"]
                self.left_region_container.setVisible(visible)
                if hasattr(self, "toggle_left_region"):
                    self.toggle_left_region.setChecked(visible)
            except Exception:
                pass

        # Restore right region visibility
        if hasattr(self, "right_region_container") and "right_region_visible" in dock_state:
            try:
                visible = dock_state["right_region_visible"]
                self.right_region_container.setVisible(visible)
                if hasattr(self, "toggle_right_region"):
                    self.toggle_right_region.setChecked(visible)
            except Exception:
                pass

        # Restore bottom panel visibility
        if hasattr(self, "bottom_panel") and "bottom_panel_visible" in dock_state:
            try:
                visible = dock_state["bottom_panel_visible"]
                self.bottom_panel.setVisible(visible)
            except Exception:
                pass

        # Restore bottom panel current tab
        if hasattr(self, "bottom_panel") and "bottom_panel_index" in dock_state:
            try:
                index = dock_state["bottom_panel_index"]
                self.bottom_panel.set_current_panel(index)
            except Exception:
                pass

    def _apply_checked_preference(
        self, action: QAction | None, desired: bool | None, apply: Callable[[bool], None]
    ) -> None:
        if action is None or desired is None:
            return
        action.blockSignals(True)
        action.setChecked(bool(desired))
        action.blockSignals(False)
        apply(bool(desired))

    def _apply_view_preferences(self) -> None:
        panel_settings = self.view_settings.get("panels", {}) if self.config else {}
        bar_settings = self.view_settings.get("bars", {}) if self.config else {}

        self._apply_checked_preference(self.action_toggle_project, panel_settings.get("project"), self._toggle_project)
        self._apply_checked_preference(
            self.action_toggle_terminal, panel_settings.get("terminal"), self._toggle_terminal
        )
        self._apply_checked_preference(
            self.action_toggle_architecture_map,
            panel_settings.get("architecture"),
            self._toggle_architecture_map,
        )
        self._apply_checked_preference(self.action_toggle_ai_dock, panel_settings.get("ai"), self._toggle_ai_dock)
        self._apply_checked_preference(
            self.action_toggle_split_editor,
            panel_settings.get("split_editor"),
            self._toggle_split_editor,
        )

        self._apply_checked_preference(
            self.action_toggle_activity_bar, bar_settings.get("activity", True), self._toggle_activity_bar_visible
        )
        self._apply_checked_preference(
            self.action_toggle_status_bar, bar_settings.get("status", True), self._toggle_status_bar_visible
        )
        self._apply_checked_preference(
            self.action_toggle_menu_bar, bar_settings.get("menu", True), self._toggle_menu_bar_visible
        )

        desired_wrap = self.view_settings.get("word_wrap", self._word_wrap_enabled) if self.config else False
        self._apply_checked_preference(self.action_toggle_word_wrap, desired_wrap, self._toggle_word_wrap)

        autosave_cfg = self.config.get("autosave", {}) if self.config else {}
        desired_autosave = autosave_cfg.get("enabled", self._autosave_enabled)
        self._apply_checked_preference(self.action_toggle_autosave, desired_autosave, self._toggle_autosave)

    def _update_workspace_state(self) -> None:
        workspace = self.workspace_manager.current_workspace
        has_workspace = workspace is not None
        self.agent_manager.set_workspace_active(has_workspace)
        if hasattr(self, "project_stack"):
            target = self.project_view if has_workspace else self.project_placeholder
            self.project_stack.setCurrentWidget(target)
            if not has_workspace:
                self.project_model.set_workspace_root(None)
                self.project_view.setRootIndex(QModelIndex())

        ai_widget = getattr(self, "ai_dock", None)
        if ai_widget:
            panel = ai_widget.widget()
            if isinstance(panel, AIChatPanel):
                panel.set_workspace_active(has_workspace)

        if hasattr(self, "agent_console_dock"):
            console = self.agent_console_dock.widget()
            if hasattr(console, "set_workspace_active"):
                console.set_workspace_active(has_workspace)

        if hasattr(self, "git_service"):
            self.git_service.set_workspace(workspace)
        if hasattr(self, "git_panel"):
            self.git_panel.refresh()
            has_repo = self.git_panel.has_repository()
            if hasattr(self, "git_dock"):
                self.git_dock.setVisible(has_repo)
            if not has_repo:
                self.git_panel.set_empty_state(True)

        if hasattr(self, "debugger_panel"):
            config_exists = bool(workspace and (Path(workspace) / ".vscode" / "launch.json").exists())
            self.debugger_panel.set_configured(config_exists)

        self._update_title_context()

    def _collect_dock_regions(self) -> None:
        self.left_docks = [self.left_dock_stack.widget(i) for i in range(self.left_dock_stack.count())]
        self.bottom_docks = []  # No longer using dock stack for bottom panels
        self.right_docks = [self.right_dock_stack.widget(i) for i in range(self.right_dock_stack.count())]

        preferred_left = getattr(self, "project_dock", None)
        primary_left = preferred_left if preferred_left in self.left_docks else (self.left_docks[0] if self.left_docks else None)
        self.primary_left_dock = primary_left
        if primary_left:
            self.left_dock_stack.setCurrentWidget(primary_left)
        for dock in self.left_docks:
            dock.setVisible(dock is self.left_dock_stack.currentWidget())

        if self.right_docks:
            self.right_dock_stack.setCurrentWidget(self.right_docks[0])
        for dock in self.right_docks:
            dock.setVisible(dock is self.right_dock_stack.currentWidget())

        # Bottom panel is now managed separately (Windsurf-style)
        # It's hidden by default and shown when user toggles it

    def _place_left_dock(self, dock: QDockWidget, area: Qt.DockWidgetArea = Qt.LeftDockWidgetArea) -> None:
        dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.left_dock_stack.addWidget(dock)

    def _place_bottom_dock(self, dock: QDockWidget) -> None:
        """Legacy method - bottom panels now use BottomPanel widget directly."""
        pass  # No longer needed with new Windsurf-style bottom panel

    def _place_ai_dock(self, dock: QDockWidget) -> None:
        dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.right_dock_stack.addWidget(dock)

    def _register_dock_action(self, dock: QDockWidget) -> None:
        if hasattr(self, "view_menu"):
            if dock.objectName() in {"projectDock", "terminalDock", "architectureDock", "activityDock", "aiDock"}:
                return
            self.view_menu.addAction(dock.toggleViewAction())

    def _connect_dock_toggles(self) -> None:
        self.toggle_left_region.toggled.connect(self._set_left_docks_visible)
        self.toggle_bottom_region.toggled.connect(self._toggle_bottom_region)
        self.toggle_right_region.toggled.connect(
            lambda visible: self._toggle_region_widget(getattr(self, "right_region_container", None), visible)
        )

    def _toggle_region_widget(self, widget: QWidget | None, visible: bool) -> None:
        if not widget:
            return
        widget.setVisible(visible)
        self._update_view_action_states()

    def _toggle_bottom_region(self, visible: bool) -> None:
        """Toggle the bottom panel region and ensure terminal is shown when opened."""
        if not hasattr(self, "bottom_panel"):
            return

        self.bottom_panel.setVisible(visible)
        self._bottom_panel_maximized = False
        self._bottom_panel_collapsed = False

        if visible and hasattr(self, "terminal_panel_index"):
            # When opening bottom region, show the terminal panel by default
            self.bottom_panel.set_current_panel(self.terminal_panel_index)

        self._update_view_action_states()

    def _toggle_split_editor(self, enabled: bool) -> None:
        if enabled != self.editor_tabs.split_active():
            self.editor_tabs.set_split_active(enabled)
        self.view_settings.setdefault("panels", {})["split_editor"] = bool(enabled)
        self._show_welcome_if_empty()
        self._update_view_action_states()

    def _toggle_bottom_panel_maximize(self) -> None:
        if not hasattr(self, "center_vertical_splitter"):
            return

        sizes = self.center_vertical_splitter.sizes()
        if not self._bottom_panel_maximized:
            self._bottom_panel_previous_sizes = sizes
            total = sum(sizes)
            self.center_vertical_splitter.setSizes([int(total * 0.2), int(total * 0.8)])
            self._bottom_panel_maximized = True
            self._bottom_panel_collapsed = False
        else:
            if self._bottom_panel_previous_sizes:
                self.center_vertical_splitter.setSizes(self._bottom_panel_previous_sizes)
            self._bottom_panel_maximized = False

    def _toggle_bottom_panel_collapse(self) -> None:
        if not hasattr(self, "center_vertical_splitter"):
            return

        if not self.bottom_panel.isVisible():
            self._toggle_bottom_region(True)

        sizes = self.center_vertical_splitter.sizes()
        if not self._bottom_panel_collapsed:
            self._bottom_panel_previous_sizes = sizes
            total = sum(sizes)
            header_height = self.bottom_panel.tab_bar.height() + 4
            self.center_vertical_splitter.setSizes([max(total - header_height, 1), header_height])
            self._bottom_panel_collapsed = True
            self._bottom_panel_maximized = False
        else:
            if self._bottom_panel_previous_sizes:
                self.center_vertical_splitter.setSizes(self._bottom_panel_previous_sizes)
            self._bottom_panel_collapsed = False

    def _set_left_docks_visible(self, visible: bool) -> None:
        if not hasattr(self, "left_dock_container"):
            return

        self.left_dock_container.setVisible(visible)
        activity_bar_width = self.activity_bar.sizeHint().width()
        min_width = (
            self.left_dock_container.minimumWidth() + activity_bar_width if visible else activity_bar_width
        )
        self.left_region_container.setMinimumWidth(min_width)
        self.left_region_container.setMaximumWidth(16777215 if visible else min_width)

        if hasattr(self, "main_splitter"):
            sizes = self.main_splitter.sizes()
            if visible:
                previous = getattr(self, "_left_region_previous_size", None)
                if previous is not None:
                    sizes[0] = previous
            else:
                self._left_region_previous_size = sizes[0]
                sizes[0] = max(min_width, activity_bar_width)
            self.main_splitter.setSizes(sizes)

        if visible:
            current = self.left_dock_stack.currentWidget()
            if current:
                current.show()

        self._update_view_action_states()

    def _update_view_action_states(self) -> None:
        """Synchronise View menu checkboxes with the current dock visibility state."""
        # Explorer / project dock
        if hasattr(self, "action_toggle_project"):
            project_open = False
            if hasattr(self, "project_dock") and hasattr(self, "left_dock_container") and hasattr(self, "left_dock_stack"):
                project_open = (
                    self.left_dock_container.isVisible()
                    and self.left_dock_stack.currentWidget() is self.project_dock
                    and self.project_dock.isVisible()
                )
            self.action_toggle_project.setChecked(project_open)

        if hasattr(self, "action_toggle_split_editor"):
            self.action_toggle_split_editor.setChecked(self.editor_tabs.split_active())

        # Terminal region
        if hasattr(self, "action_toggle_terminal"):
            terminal_open = False
            if hasattr(self, "bottom_panel"):
                terminal_open = self.bottom_panel.isVisible()
            self.action_toggle_terminal.setChecked(terminal_open)

        # 3D Architecture Map
        if hasattr(self, "action_toggle_architecture_map"):
            arch_open = False
            if hasattr(self, "architecture_dock") and hasattr(self, "left_dock_container") and hasattr(self, "left_dock_stack"):
                arch_open = (
                    self.left_dock_container.isVisible()
                    and self.left_dock_stack.currentWidget() is self.architecture_dock
                    and self.architecture_dock.isVisible()
                )
            self.action_toggle_architecture_map.setChecked(arch_open)

        # Ghostline AI dock
        if hasattr(self, "action_toggle_ai_dock"):
            ai_open = False
            if hasattr(self, "ai_dock"):
                ai_open = self.ai_dock.isVisible()
            self.action_toggle_ai_dock.setChecked(ai_open)

    def _collect_view_actions(self) -> list[QAction]:
        actions: list[QAction] = []

        def walk(menu: QMenu) -> None:
            for action in menu.actions():
                if action.menu():
                    walk(action.menu())
                else:
                    actions.append(action)

        if hasattr(self, "view_menu") and self.view_menu:
            walk(self.view_menu)

        for dock in getattr(self, "left_docks", []) + getattr(self, "right_docks", []):
            toggle = dock.toggleViewAction()
            if toggle not in actions:
                actions.append(toggle)

        return [action for action in actions if action.isCheckable()]

    def _open_view_picker(self) -> None:
        dialog = ViewPickerDialog(self._collect_view_actions(), self)
        dialog.resize(360, 420)
        dialog.show()

    def _update_title_context(self) -> None:
        if not hasattr(self, "title_bar"):
            return

        workspace = self.workspace_manager.current_workspace
        project_label = workspace.name if workspace else "No workspace"
        editor = self.get_current_editor()
        file_label = None
        if editor:
            if editor.path:
                file_label = Path(editor.path).name
            else:
                file_label = "Untitled"

        context = project_label if project_label else ""
        if file_label:
            context = f"{project_label} - {file_label}" if project_label else file_label

        self.title_bar.set_context_text(context)

    def _enforce_left_exclusivity(self, dock: QDockWidget, visible: bool) -> None:
        if not visible or self.dockWidgetArea(dock) != Qt.LeftDockWidgetArea or dock.isFloating():
            return
        for other in self.left_docks:
            if other is dock:
                continue
            if other.isVisible() and not other.isFloating() and self.dockWidgetArea(other) == Qt.LeftDockWidgetArea:
                other.hide()

    def _create_actions(self) -> None:
        panel_settings = self.view_settings.setdefault("panels", {})
        bar_settings = self.view_settings.setdefault("bars", {})

        command_definitions = [
            CommandActionDefinition("file.new", "New File", "File", handler=self._create_new_file, shortcut="Ctrl+N"),
            CommandActionDefinition("file.save", "Save", "File", handler=self._save_current_file, shortcut="Ctrl+S"),
            CommandActionDefinition("file.save_as", "Save As...", "File", handler=self._save_current_file_as),
            CommandActionDefinition("file.open", "Open File", "File", handler=self._prompt_open_file),
            CommandActionDefinition("file.open_folder", "Open Folder", "File", handler=self._prompt_open_folder),
            CommandActionDefinition("file.close_folder", "Close Folder", "File", handler=self._close_folder),
            CommandActionDefinition(
                "search.global",
                "Find in Files",
                "Navigate",
                handler=self._trigger_global_search_action,
                shortcut="Ctrl+Shift+F",
            ),
            CommandActionDefinition("navigate.symbol", "Go to Symbol", "Navigate", handler=self._open_symbol_picker),
            CommandActionDefinition("navigate.file", "Go to File", "Navigate", handler=self._open_file_picker),
            CommandActionDefinition(
                "palette.command",
                "Command Palette",
                "View",
                handler=self.show_command_palette,
                shortcut="Ctrl+Shift+P",
            ),
            CommandActionDefinition(
                "view.picker",
                "View Picker",
                "View",
                handler=self._open_view_picker,
                shortcut="Ctrl+Alt+V",
            ),
            CommandActionDefinition(
                "ai.toggle_autoflow",
                "Toggle Autoflow Mode",
                "AI",
                handler=self._toggle_autoflow_mode,
                checkable=True,
                checked=self.command_palette.autoflow_mode == "active",
            ),
            CommandActionDefinition(
                "view.toggle_project",
                "Explorer",
                "View",
                handler=self._toggle_project,
                checkable=True,
                checked=bool(panel_settings.get("project", True)),
            ),
            CommandActionDefinition(
                "view.toggle_split",
                "Split Editor",
                "View",
                handler=self._toggle_split_editor,
                checkable=True,
                checked=self.editor_tabs.split_active(),
            ),
            CommandActionDefinition(
                "view.toggle_terminal",
                "Terminal",
                "View",
                handler=self._toggle_terminal,
                checkable=True,
                checked=bool(panel_settings.get("terminal", False)),
            ),
            CommandActionDefinition(
                "view.toggle_architecture",
                "3D Architecture Map",
                "View",
                handler=self._toggle_architecture_map,
                checkable=True,
                checked=bool(panel_settings.get("architecture", False)),
            ),
            CommandActionDefinition(
                "view.toggle_ai_dock",
                "Ghostline AI",
                "View",
                handler=self._toggle_ai_dock,
                checkable=True,
                checked=bool(panel_settings.get("ai", True)),
            ),
            CommandActionDefinition(
                "view.word_wrap",
                "Word Wrap",
                "View",
                handler=self._toggle_word_wrap,
                checkable=True,
                checked=self._word_wrap_enabled,
            ),
            CommandActionDefinition(
                "view.autosave",
                "Autosave",
                "View",
                handler=self._toggle_autosave,
                checkable=True,
                checked=self._autosave_enabled,
            ),
            CommandActionDefinition(
                "view.activity_bar",
                "Activity Bar",
                "View",
                handler=self._toggle_activity_bar_visible,
                checkable=True,
                checked=bool(bar_settings.get("activity", True)),
            ),
            CommandActionDefinition(
                "view.status_bar",
                "Status Bar",
                "View",
                handler=self._toggle_status_bar_visible,
                checkable=True,
                checked=bool(bar_settings.get("status", True)),
            ),
            CommandActionDefinition(
                "view.menu_bar",
                "Menu Bar",
                "View",
                handler=self._toggle_menu_bar_visible,
                checkable=True,
                checked=bool(bar_settings.get("menu", True)),
            ),
            CommandActionDefinition("settings.editor", "Editor Settings", "Settings", handler=self._open_settings),
            CommandActionDefinition(
                "settings.ghostline",
                "Ghostline Settings",
                "Settings",
                handler=self._open_settings,
                shortcut=QKeySequence("Ctrl+,"),
            ),
            CommandActionDefinition(
                "settings.extensions",
                "Extensions",
                "Settings",
                handler=self._open_extensions,
                shortcut=QKeySequence("Ctrl+Shift+X"),
            ),
            CommandActionDefinition(
                "settings.keyboard",
                "Open Keyboard Shortcuts",
                "Settings",
                handler=self._open_keyboard_shortcuts,
                shortcut=QKeySequence("Ctrl+K, Ctrl+S"),
            ),
            CommandActionDefinition(
                "settings.snippets", "Configure Snippets", "Settings", handler=self._open_snippets
            ),
            CommandActionDefinition("settings.tasks", "Tasks", "Settings", handler=self._open_tasks_panel),
            CommandActionDefinition("ai.settings", "AI Settings…", "AI", handler=self._open_ai_settings),
            CommandActionDefinition("ai.setup", "Re-run Setup Wizard…", "AI", handler=self.show_setup_wizard),
            CommandActionDefinition(
                "ai.explain_selection",
                "Explain Selection",
                "AI",
                handler=lambda: self._run_ai_command(explain_selection),
            ),
            CommandActionDefinition(
                "ai.refactor_selection",
                "Refactor Selection",
                "AI",
                handler=lambda: self._run_ai_command(refactor_selection),
            ),
            CommandActionDefinition(
                "ai.code_actions",
                "AI Code Actions...",
                "AI",
                handler=lambda: self._run_ai_command(ai_code_actions),
            ),
            CommandActionDefinition("ai.panel", "Toggle AI Panel", "AI", handler=self.toggle_ai_dock),
            CommandActionDefinition("plugins.manage", "Plugins", "Plugins", handler=self._open_plugin_manager),
            CommandActionDefinition(
                "tasks.run",
                "Run Task...",
                "Tasks",
                handler=self._run_task_command,
                shortcut="Ctrl+Shift+R",
            ),
            CommandActionDefinition(
                "lsp.restart",
                "Restart Language Server",
                "LSP",
                handler=self._restart_language_server,
            ),
            CommandActionDefinition(
                "edit.format_document",
                "Format Document",
                "Edit",
                handler=self._format_current_document,
            ),
            CommandActionDefinition(
                "edit.undo",
                "Undo",
                "Edit",
                handler=lambda: self._with_editor(lambda e: e.undo()),
                shortcut="Ctrl+Z",
            ),
            CommandActionDefinition(
                "edit.redo",
                "Redo",
                "Edit",
                handler=lambda: self._with_editor(lambda e: e.redo()),
                shortcut="Ctrl+Shift+Z",
            ),
            CommandActionDefinition(
                "edit.cut",
                "Cut",
                "Edit",
                handler=lambda: self._with_editor(lambda e: e.cut()),
                shortcut="Ctrl+X",
            ),
            CommandActionDefinition(
                "edit.copy",
                "Copy",
                "Edit",
                handler=lambda: self._with_editor(lambda e: e.copy()),
                shortcut="Ctrl+C",
            ),
            CommandActionDefinition(
                "edit.paste",
                "Paste",
                "Edit",
                handler=lambda: self._with_editor(lambda e: e.paste()),
                shortcut="Ctrl+V",
            ),
            CommandActionDefinition(
                "edit.find",
                "Find",
                "Edit",
                handler=lambda: self._focus_editor_find(),
                shortcut="Ctrl+F",
            ),
            CommandActionDefinition(
                "edit.replace",
                "Replace",
                "Edit",
                handler=lambda: self._focus_editor_find(replace=True),
                shortcut="Ctrl+H",
            ),
            CommandActionDefinition(
                "edit.select_all",
                "Select All",
                "Edit",
                handler=lambda: self._with_editor(lambda e: e.selectAll()),
                shortcut="Ctrl+A",
            ),
            CommandActionDefinition(
                "project.settings",
                "Project Settings",
                "Project",
                handler=lambda: self.status.show_message("Project settings coming soon"),
            ),
            CommandActionDefinition(
                "run.run",
                "Run",
                "Run",
                handler=lambda: self.status.show_message("Run current project"),
            ),
            CommandActionDefinition("run.tests", "Run Tests", "Run", handler=self._run_tests),
            CommandActionDefinition("run.tasks", "Run Tasks", "Run", handler=self._run_task_command),
            CommandActionDefinition(
                "debug.start",
                "Start Debugging",
                "Debug",
                handler=lambda: self.status.show_message("Starting debugger"),
            ),
            CommandActionDefinition(
                "debug.stop",
                "Stop Debugging",
                "Debug",
                handler=lambda: self.status.show_message("Debugger stopped"),
            ),
            CommandActionDefinition(
                "debug.step_over",
                "Step Over",
                "Debug",
                handler=lambda: self.status.show_message("Step over"),
            ),
            CommandActionDefinition(
                "debug.step_into",
                "Step Into",
                "Debug",
                handler=lambda: self.status.show_message("Step into"),
            ),
            CommandActionDefinition(
                "debug.step_out",
                "Step Out",
                "Debug",
                handler=lambda: self.status.show_message("Step out"),
            ),
            CommandActionDefinition("help.docs", "Documentation", "Help", handler=self._open_docs),
            CommandActionDefinition(
                "help.report_issue",
                "Report Issue",
                "Help",
                handler=self._open_feature_request,
            ),
            CommandActionDefinition("help.walkthrough", "Product Walkthrough", "Help", handler=self._open_walkthrough),
            CommandActionDefinition("help.playground", "Editor Playground", "Help", handler=self._open_editor_playground),
            CommandActionDefinition("help.view_license", "View License", "Help", handler=self._open_license),
            CommandActionDefinition(
                "help.developer_tools", "Toggle Developer Tools", "Help", handler=self._toggle_developer_tools
            ),
            CommandActionDefinition(
                "help.process_explorer", "Process Explorer", "Help", handler=self._open_process_explorer
            ),
            CommandActionDefinition("help.check_updates", "Check for Updates", "Help", handler=self._check_for_updates),
            CommandActionDefinition("help.about", "About Ghostline Studio", "Help", handler=self._show_about),
            CommandActionDefinition(
                "help.ghost_terminal",
                "Ghost Terminal...",
                "Help",
                handler=self._open_ghost_terminal,
            ),
        ]

        self.ui_action_registry = CommandActionRegistry(self, self.command_registry)
        self.ui_action_registry.bulk_register(command_definitions)
        actions = self.ui_action_registry.build()

        self.action_new_file = actions["file.new"]
        self.action_save_file = actions["file.save"]
        self.action_save_file_as = actions["file.save_as"]
        self.action_open_file = actions["file.open"]
        self.action_open_folder = actions["file.open_folder"]
        self.action_close_folder = actions["file.close_folder"]
        self.action_global_search = actions["search.global"]
        self.action_goto_symbol = actions["navigate.symbol"]
        self.action_goto_file = actions["navigate.file"]
        self.action_command_palette = actions["palette.command"]
        self.action_view_picker = actions["view.picker"]
        self.action_toggle_autoflow = actions["ai.toggle_autoflow"]
        self.action_toggle_project = actions["view.toggle_project"]
        self.action_toggle_split_editor = actions["view.toggle_split"]
        self.action_toggle_terminal = actions["view.toggle_terminal"]
        self.action_toggle_architecture_map = actions["view.toggle_architecture"]
        self.action_toggle_ai_dock = actions["view.toggle_ai_dock"]
        self.action_toggle_word_wrap = actions["view.word_wrap"]
        self.action_toggle_autosave = actions["view.autosave"]
        self.action_toggle_activity_bar = actions["view.activity_bar"]
        self.action_toggle_status_bar = actions["view.status_bar"]
        self.action_toggle_menu_bar = actions["view.menu_bar"]
        self.action_editor_settings = actions["settings.editor"]
        self.action_ghostline_settings = actions["settings.ghostline"]
        self.action_extensions = actions["settings.extensions"]
        self.action_keyboard_shortcuts = actions["settings.keyboard"]
        self.action_configure_snippets = actions["settings.snippets"]
        self.action_tasks_view = actions["settings.tasks"]
        self.action_ai_settings = actions["ai.settings"]
        self.action_setup_wizard = actions["ai.setup"]
        self.action_ai_explain = actions["ai.explain_selection"]
        self.action_ai_refactor = actions["ai.refactor_selection"]
        self.action_ai_code_actions = actions["ai.code_actions"]
        self.action_ask_ai = actions["ai.panel"]
        self.action_open_plugins = actions["plugins.manage"]
        self.action_run_task = actions["tasks.run"]
        self.action_restart_language = actions["lsp.restart"]
        self.action_format_document = actions["edit.format_document"]
        self.action_undo = actions["edit.undo"]
        self.action_redo = actions["edit.redo"]
        self.action_cut = actions["edit.cut"]
        self.action_copy = actions["edit.copy"]
        self.action_paste = actions["edit.paste"]
        self.action_find = actions["edit.find"]
        self.action_replace = actions["edit.replace"]
        self.action_select_all = actions["edit.select_all"]
        self.action_project_settings = actions["project.settings"]
        self.action_run = actions["run.run"]
        self.action_run_tests = actions["run.tests"]
        self.action_run_tasks = actions["run.tasks"]
        self.action_start_debugging = actions["debug.start"]
        self.action_stop_debugging = actions["debug.stop"]
        self.action_step_over = actions["debug.step_over"]
        self.action_step_into = actions["debug.step_into"]
        self.action_step_out = actions["debug.step_out"]
        self.action_docs = actions["help.docs"]
        self.action_report_issue = actions["help.report_issue"]
        self.action_walkthrough = actions["help.walkthrough"]
        self.action_playground = actions["help.playground"]
        self.action_view_license = actions["help.view_license"]
        self.action_developer_tools = actions["help.developer_tools"]
        self.action_process_explorer = actions["help.process_explorer"]
        self.action_check_updates = actions["help.check_updates"]
        self.action_about = actions["help.about"]
        self.action_ghost_terminal = actions["help.ghost_terminal"]
        self.action_ghost_terminal.setVisible(False)

        self.addActions(
            [
                self.action_ghostline_settings,
                self.action_extensions,
                self.action_keyboard_shortcuts,
            ]
        )

    def _create_menus(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction(self.action_new_file)
        file_menu.addAction(self.action_save_file)
        file_menu.addAction(self.action_save_file_as)
        file_menu.addAction(self.action_open_file)
        file_menu.addAction(self.action_open_folder)
        file_menu.addAction(self.action_close_folder)
        file_menu.addAction(self.action_project_settings)
        file_menu.addSeparator()
        new_window_action = QAction("New Window", self)
        new_window_action.triggered.connect(lambda: self._launch_new_window())
        file_menu.addAction(new_window_action)
        profile_window_action = QAction("New Window with Profile...", self)
        profile_window_action.triggered.connect(self._prompt_new_profile_window)
        file_menu.addAction(profile_window_action)
        file_menu.addSeparator()
        share_menu = file_menu.addMenu("Share")
        share_menu.addAction(self._create_share_file_action())
        share_menu.addAction(self._create_share_workspace_action())
        file_menu.addSeparator()
        tools_menu = file_menu.addMenu("Tools")
        tools_menu.addAction(self.action_open_plugins)
        prefs_menu = file_menu.addMenu("Preferences")
        prefs_menu.addAction(self.action_ghostline_settings)
        prefs_menu.addAction(self.action_keyboard_shortcuts)

        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_cut)
        edit_menu.addAction(self.action_copy)
        edit_menu.addAction(self.action_paste)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_format_document)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_find)
        edit_menu.addAction(self.action_replace)

        selection_menu = menubar.addMenu("Selection")
        selection_menu.addAction(self.action_select_all)
        selection_menu.addSeparator()
        selection_menu.addAction(self.action_ai_explain)
        selection_menu.addAction(self.action_ai_refactor)

        self.view_menu = menubar.addMenu("View")
        self.view_menu.addAction(self.action_command_palette)
        self.view_menu.addAction(self.action_view_picker)
        self.view_menu.addAction(self.action_toggle_project)
        self.view_menu.addAction(self.action_toggle_split_editor)
        self.view_menu.addAction(self.action_toggle_terminal)
        self.view_menu.addAction(self.action_toggle_architecture_map)
        self.view_menu.addAction(self.action_toggle_ai_dock)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.action_toggle_word_wrap)
        self.view_menu.addAction(self.action_toggle_autosave)
        interface_menu = self.view_menu.addMenu("Interface")
        interface_menu.addAction(self.action_toggle_activity_bar)
        interface_menu.addAction(self.action_toggle_status_bar)
        interface_menu.addAction(self.action_toggle_menu_bar)
        ai_menu = self.view_menu.addMenu("AI")
        ai_menu.addAction(self.action_ask_ai)
        ai_menu.addAction(self.action_ai_code_actions)
        ai_menu.addAction(self.action_toggle_autoflow)
        ai_menu.addSeparator()
        ai_menu.addAction(self.action_ai_settings)
        ai_menu.addAction(self.action_setup_wizard)

        go_menu = menubar.addMenu("Go")
        go_menu.addAction(self.action_goto_file)
        go_menu.addAction(self.action_goto_symbol)
        go_menu.addAction(self.action_global_search)

        run_menu = menubar.addMenu("Run")
        run_menu.addAction(self.action_run)
        run_menu.addAction(self.action_run_tests)
        run_menu.addAction(self.action_run_task)
        debug_menu = run_menu.addMenu("Debug")
        debug_menu.addAction(self.action_start_debugging)
        debug_menu.addAction(self.action_stop_debugging)
        debug_menu.addAction(self.action_step_over)
        debug_menu.addAction(self.action_step_into)
        debug_menu.addAction(self.action_step_out)

        terminal_menu = menubar.addMenu("Terminal")
        terminal_menu.addAction(self.action_toggle_terminal)
        terminal_menu.addAction(self.action_restart_language)

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(self.action_docs)
        help_menu.addAction(self.action_report_issue)
        help_menu.addAction(self.action_walkthrough)
        help_menu.addAction(self.action_playground)
        help_menu.addAction(self.action_view_license)
        help_menu.addSeparator()
        help_menu.addAction(self.action_developer_tools)
        help_menu.addAction(self.action_process_explorer)
        help_menu.addAction(self.action_check_updates)
        help_menu.addSeparator()
        help_menu.addAction(self.action_about)
        # Hidden easter egg: hold Shift while opening the Help menu to reveal Ghost Terminal.
        help_menu.aboutToShow.connect(self._on_help_menu_about_to_show)
        help_menu.addAction(self.action_ghost_terminal)

    def _search_workspace_files(self, query: str):
        workspace = self.workspace_manager.current_workspace
        if not workspace or not query:
            return []
        lowered = query.lower()
        results = []
        for path in workspace.rglob("*"):
            if len(results) >= 20:
                break
            if path.is_file() and lowered in path.name.lower():
                results.append(path)
        return results

    def _create_terminal_dock(self) -> None:
        """Create all bottom panels (Windsurf-style)."""
        # Create all panel widgets
        self.problems_panel = ProblemsPanel(self)
        self.output_panel = OutputPanel(self)
        self.debug_console_panel = DebugConsolePanel(self)
        self.terminal_widget = WindsurfTerminalWidget(self.workspace_manager, self, use_external_toolbar=True)
        self.ports_panel = PortsPanel(self)

        # Add panels to bottom panel in Windsurf order
        self.bottom_panel.add_panel("Problems", self.problems_panel)
        self.output_panel_index = self.bottom_panel.add_panel("Output", self.output_panel)
        self.bottom_panel.add_panel("Debug Console", self.debug_console_panel)
        self.terminal_panel_index = self.bottom_panel.add_panel(
            "Terminal", self.terminal_widget, controls=self.terminal_widget.toolbar_widget
        )
        self.bottom_panel.add_panel("Ports", self.ports_panel)

        # Set terminal as default panel
        self.bottom_panel.set_current_panel(self.terminal_panel_index)

        # Keep backward compatibility references
        self.terminal = self.terminal_widget
        self.terminal_dock = self.bottom_panel  # For compatibility

    def _create_project_dock(self) -> None:
        dock = QDockWidget("Explorer", self)
        dock.setObjectName("projectDock")
        # Reduced minimums and removed restrictive maximum for better responsiveness
        dock.setMinimumWidth(180)  # Reduced from 280
        dock.setMaximumWidth(600)  # Increased from 520 for large screens
        self.project_model = ProjectModel(self)
        self.project_view = ProjectView(self)
        self.project_view.setTextElideMode(Qt.ElideRight)
        self.project_view.set_model(self.project_model)
        self.project_placeholder = QLabel("No workspace open. Use File → Open Folder…", self)
        self.workspace_manager.fileChanged.connect(lambda _=None: self.project_model.layoutChanged.emit())
        self.workspace_manager.fileAdded.connect(lambda _=None: self.project_model.layoutChanged.emit())
        self.workspace_manager.fileRemoved.connect(lambda _=None: self.project_model.layoutChanged.emit())
        self.project_placeholder.setAlignment(Qt.AlignCenter)
        self.project_placeholder.setWordWrap(True)
        container = QWidget(self)
        self.project_stack = QStackedLayout(container)
        self.project_stack.setContentsMargins(8, 8, 8, 8)
        self.project_stack.addWidget(self.project_placeholder)
        self.project_stack.addWidget(self.project_view)
        dock.setWidget(container)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.project_dock = dock

    def _create_search_dock(self) -> None:
        dock = SearchPanel(
            lambda: str(self.workspace_manager.current_workspace) if self.workspace_manager.current_workspace else None,
            lambda path, line: self.open_file_at(path, line),
            self,
        )
        dock.setObjectName("searchDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.search_dock = dock

    def _create_ai_dock(self) -> None:
        dock = QDockWidget("Ghostline AI", self)
        dock.setObjectName("aiDock")
        # Remove close button from the dock
        dock.setFeatures(dock.features() & ~QDockWidget.DockWidgetClosable)
        panel = AIChatPanel(self.ai_client, self.context_engine, self)
        panel.set_active_document_provider(self._active_document_payload)
        panel.set_open_documents_provider(self._open_document_payloads)
        panel.set_command_adapter(self.ai_command_adapter)
        panel.set_insert_handler(lambda code: self._with_editor(lambda e: e.insertPlainText(code)))
        panel.set_patch_handler(self._apply_ai_suggestion_patch)
        dock.setWidget(panel)
        dock.setMinimumWidth(200)  # Reduced from 260 for small screens
        self._place_ai_dock(dock)
        self._register_dock_action(dock)
        self.ai_dock = dock

    def _create_diagnostics_dock(self) -> None:
        dock = QDockWidget("Diagnostics", self)
        dock.setObjectName("diagnosticsDock")
        table = QTableView(self)
        self.diagnostics_model = DiagnosticsModel(self)
        table.setModel(self.diagnostics_model)
        table.doubleClicked.connect(self._jump_to_diagnostic)
        self.diagnostics_empty = QLabel("No diagnostics yet. Run analysis or tests to see issues.", self)
        self.diagnostics_empty.setAlignment(Qt.AlignCenter)
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.diagnostics_empty)
        layout.addWidget(table)
        dock.setWidget(container)
        dock.setMinimumHeight(100)  # Reduced from 140 for small screens
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_bottom_dock(dock)
        self._register_dock_action(dock)
        self.diagnostics_view = table
        self.diagnostics_dock = dock

    def _create_debugger_dock(self) -> None:
        dock = QDockWidget("Debugger", self)
        dock.setObjectName("debuggerDock")
        panel = DebuggerPanel(self.debugger, self)
        dock.setWidget(panel)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.debugger_panel = panel
        self.debugger_dock = dock

    def _create_task_dock(self) -> None:
        dock = QDockWidget("Tasks", self)
        dock.setObjectName("tasksDock")
        panel = TaskPanel(self.task_manager, self)
        dock.setWidget(panel)
        dock.setMinimumWidth(180)  # Changed from height to width for left dock
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)  # Changed from _place_bottom_dock
        self._register_dock_action(dock)
        self.task_dock = dock

    def _create_test_dock(self) -> None:
        dock = QDockWidget("Tests", self)
        dock.setObjectName("testsDock")
        panel = TestPanel(self.test_manager, self.get_current_editor, self)
        dock.setWidget(panel)
        dock.setMinimumWidth(180)  # Changed from height to width for left dock
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)  # Changed from _place_bottom_dock
        self._register_dock_action(dock)
        self.test_dock = dock

    def _create_architecture_dock(self) -> None:
        dock = ArchitectureDock(self)
        dock.setObjectName("architectureDock")
        dock.open_file_requested.connect(self._open_graph_location)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.architecture_dock = dock
        self._refresh_architecture_graph()

    def _create_build_dock(self) -> None:
        dock = BuildPanel(self.build_manager, self)
        dock.setObjectName("buildDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_bottom_dock(dock)
        self._register_dock_action(dock)
        self.build_dock = dock

    def _create_doc_dock(self) -> None:
        dock = DocPanel(self.doc_generator, self)
        dock.setObjectName("docDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.doc_dock = dock

    def _format_current_document(self) -> None:
        editor = self.get_current_editor()
        if not editor:
            return
        new_text = self.formatter.format_document(editor.path, editor.toPlainText())
        editor.setPlainText(new_text)

    def _create_git_dock(self) -> None:
        dock = QDockWidget("Git", self)
        dock.setObjectName("gitDock")
        panel = GitPanel(self.git_service, self)
        dock.setWidget(panel)
        dock.setMinimumWidth(180)  # Reduced from 240 for small screens
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.git_panel = panel
        self.git_dock = dock

    def _create_coverage_dock(self) -> None:
        dock = QDockWidget("Coverage", self)
        dock.setObjectName("coverageDock")
        dock.setWidget(CoveragePanel(self))
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.coverage_dock = dock

    def _create_collaboration_dock(self) -> None:
        dock = CollabPanel(self.crdt_engine, self.collab_transport, self)
        dock.setObjectName("collabDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.collab_dock = dock

    def _create_agent_console_dock(self) -> None:
        dock = AgentConsole(self.agent_manager, self)
        dock.setObjectName("agentConsoleDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.agent_console_dock = dock

    def _create_pipeline_dock(self) -> None:
        dock = PipelinePanel(self.pipeline_manager, self)
        dock.setObjectName("pipelineDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.pipeline_dock = dock

    def _create_runtime_dock(self) -> None:
        dock = RuntimePanel(self.runtime_inspector, self)
        dock.setObjectName("runtimeDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(dock)
        self._register_dock_action(dock)
        self.runtime_dock = dock

    def show_command_palette(self, preset: str | None = None) -> None:
        self._register_core_commands()
        if preset:
            self.command_palette.open_with_query(preset)
        else:
            self.command_palette.open_palette()

    def toggle_maximize_restore(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        if hasattr(self, "title_bar"):
            self.title_bar.update_maximize_icon()

    def _toggle_autoflow_mode(self, _checked: bool | None = None) -> None:
        new_mode = "active" if self.command_palette.autoflow_mode == "passive" else "passive"
        self.command_palette.set_autoflow_mode(new_mode)
        self.navigation_assistant.autoflow_enabled = new_mode == "active"
        self.status.show_message(f"Autoflow mode: {new_mode}")

    def open_file(self, path: str, *, preview: bool = False) -> None:
        editor = self.editor_tabs.add_editor_for_file(Path(path), preview=preview)
        self.status.show_path(path)
        self.workspace_manager.register_recent(path)
        workspace = self.workspace_manager.current_workspace
        self.workspace_manager.record_recent_file(path)
        self._refresh_recent_views()
        if editor:
            editor.textChanged.connect(lambda _=None, e=editor: self._sync_editor_to_index(e))
        self.status.update_git(str(workspace) if workspace else None)
        logger.info("Opened file: %s", path)
        self.plugin_loader.emit_event("file.opened", path=path)
        self.workspace_indexer.rebuild([path])
        self.semantic_index.reindex([path])
        if hasattr(self, "doc_dock"):
            self.doc_dock.set_current_file(Path(path))
        ai_client = getattr(self, "ai_client", None)
        logger.info("[MainWindow] ai_client exists: %s", ai_client is not None)
        if ai_client:
            try:
                file_text = editor.toPlainText() if editor else Path(path).read_text(encoding="utf-8")
                logger.info("[MainWindow] Calling ai_client.on_file_opened for %s (%d chars)", path, len(file_text))
            except Exception:  # noqa: BLE001
                logger.exception("Failed to capture file contents for AI backend on open: %s", path)
                file_text = ""
            ai_client.on_file_opened(Path(path), file_text)
        self._update_title_context()

    def _open_graph_location(self, path: str, line: int | None) -> None:
        if line is None:
            self.open_file(path)
            return
        self.open_file_at(path, line)

    def open_folder(self, folder: str) -> None:
        self.workspace_manager.open_workspace(folder)
        workspace_path = self.workspace_manager.current_workspace
        if hasattr(self, "context_engine"):
            self.context_engine.on_workspace_changed(workspace_path)
        workspace_str = str(workspace_path) if workspace_path else None
        self.status.update_git(workspace_str)
        self._update_title_context()
        self.status.show_message(f"Opened workspace: {folder}")
        self._refresh_recent_views()

        # Make the opened folder the root of the explorer tree,
        # so it behaves like Windsurf and shows just the project.
        index = self.project_model.set_workspace_root(workspace_str)
        if index and index.isValid():
            self.project_view.setRootIndex(index)
            self.project_view.expand(index)
            self.project_view.setCurrentIndex(index)
        self._update_workspace_state()
        if hasattr(self, "terminal"):
            self.terminal.set_workspace(workspace_path)
        self.plugin_loader.emit_event("workspace.opened", path=folder)
        self.task_manager.load_workspace_tasks()
        self.semantic_index.reindex()
        self._restore_workspace_tabs(workspace_str)
        self._show_welcome_if_empty()

    def save_all(self) -> None:
        for editor in self.editor_tabs.iter_editors():
            editor.save()
            if editor.path:
                self.plugin_loader.emit_event("file.saved", path=str(editor.path))

    def _run_all_pipelines(self) -> None:
        for pipeline in self.pipeline_manager.pipelines:
            if pipeline.enabled:
                self.pipeline_manager.run_pipeline(pipeline)
        self.status.show_message("Pipelines executed")
        self.status.show_message("Saved all files")

    def _run_tests(self) -> None:
        if self.workspace_manager.current_workspace:
            self.test_manager.run_all()
            self.status.show_message("Running tests...")
        else:
            self.status.show_message("Open a workspace to run tests")

    def _run_current_file(self, file_path: str | None = None) -> None:
        """Run the active Python file in the embedded terminal.

        This is wired to the editor header Run button (python.runFile) and
        prefers the bottom terminal dock so the user can see the command and
        its live output. If the terminal is not available, it falls back to
        the generic task manager runner.
        """
        path = Path(file_path) if file_path else None
        if not path:
            editor = self.get_current_editor()
            path = editor.path if editor and editor.path else None
        if not path:
            self.status.show_message("No file selected to run")
            return
        if path.suffix.lower() not in {".py", ".pyw"}:
            self.status.show_message("This file type cannot be run")
            return
        if not path.exists():
            self.status.show_message("File does not exist on disk")
            return

        # Build the command we want to run. Quote the path so spaces are safe.
        command = f'{sys.executable} "{path}"'

        # Prefer the embedded terminal dock so the user sees a live stream
        # of the command and any errors / logs.
        terminal = getattr(self, "terminal", None)
        terminal_dock = getattr(self, "terminal_dock", None)
        
        if terminal is not None and terminal_dock is not None:
            try:
                self._show_and_raise_dock(terminal_dock, tool_id=None)
                terminal.run_command(command)
                return
            except Exception as e:
                print(f"Error using terminal: {e}")
                # If anything goes wrong showing the dock, fall back to tasks
                self.task_manager.run_command("Run", command, cwd=str(path.parent))
                return

        # Final fallback: run through the generic task manager so the command
        # still executes even if the terminal is missing.
        self.task_manager.run_command("Run", command, cwd=str(path.parent))

    def get_current_editor(self) -> CodeEditor | None:
        return self.editor_tabs.current_editor()

    def _active_document_payload(self) -> tuple[str | Path | None, str] | None:
        editor = self.get_current_editor()
        if not editor:
            return None
        path: str | Path | None = editor.path if editor.path else "untitled"
        return (path, editor.toPlainText())

    def _clean_patch_text(self, patch: str) -> str:
        """Remove common formatting wrappers around AI patch responses."""

        lines = patch.strip().splitlines()
        if lines and lines[0].startswith("```"):
            # Drop opening code fence
            lines = lines[1:]
            # Drop closing fence if present
            while lines and lines[-1].startswith("```"):
                lines.pop()

        return "\n".join(lines).strip()

    def _apply_ai_suggestion_patch(self, path: Path, patch: str) -> bool:
        """Open a file and apply an AI-generated patch to the active editor."""

        try:
            self.open_file(str(path))
        except Exception:  # noqa: BLE001
            self.status.show_message(f"Unable to open {path} for AI fix")
            return False

        editor = self.get_current_editor()
        if not editor:
            self.status.show_message("No editor available to apply AI fix")
            return False

        sanitized_patch = self._clean_patch_text(patch)
        if not sanitized_patch:
            self.status.show_message("AI patch was empty; review the suggestion manually")
            return False

        try:
            editor.apply_unified_patch(sanitized_patch)
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("Failed to apply AI suggestion patch")
            self.status.show_message(
                "Could not apply AI patch; review the suggested changes"
            )
            return False

        self._sync_editor_to_index(editor)
        self.status.show_message(f"Applied AI fix to {Path(path).name}")
        return True

    def _open_document_payloads(self) -> list[tuple[str | Path | None, str]]:
        payloads: list[tuple[str | Path | None, str]] = []
        for editor in self.editor_tabs.iter_editors():
            payloads.append((editor.path if editor.path else "untitled", editor.toPlainText()))
        return payloads

    def _sync_editor_to_index(self, editor: CodeEditor) -> None:
        if hasattr(self, "workspace_indexer") and editor.path:
            self.workspace_indexer.update_memory_snapshot(editor.path, editor.toPlainText())

    def _with_editor(self, func) -> None:
        editor = self.get_current_editor()
        if editor:
            func(editor)

    def register_dock(self, identifier: str, widget: QDockWidget) -> None:
        widget.setObjectName(identifier)
        widget.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self._place_left_dock(widget)
        self._register_dock_action(widget)

    def execute_command(self, command_id: str, **kwargs) -> None:
        commands = {
            "file.save_all": self.save_all,
        }
        if command_id in commands:
            commands[command_id](**kwargs)

    def _create_new_file(self) -> None:
        editor = self.editor_tabs.add_untitled_editor()
        editor.document().setModified(True)
        self._update_title_context()

    def _save_current_file(self) -> None:
        editor = self.get_current_editor()
        if not editor:
            return
        if not editor.path:
            self._save_current_file_as()
            return
        editor.save()
        self.editor_tabs.update_tab_for_editor(editor)
        self.status.show_message("File saved")
        if editor.path:
            self.workspace_manager.record_recent_file(str(editor.path))
            self.plugin_loader.emit_event("file.saved", path=str(editor.path))

    def _save_current_file_as(self) -> None:
        editor = self.get_current_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save File")
        if not path:
            return
        editor.set_path(Path(path))
        editor.save()
        self.editor_tabs.update_tab_for_editor(editor)
        self.workspace_manager.register_recent(path)
        self.workspace_manager.record_recent_file(path)
        self.status.show_message(f"Saved {Path(path).name}")
        self.plugin_loader.emit_event("file.saved", path=path)

    def _prompt_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open File")
        if path:
            self.open_file(path)

    def _open_recent_item(self, path: str) -> None:
        target = Path(path)
        if target.is_dir():
            self.open_folder(path)
        elif target.exists():
            self.open_file(path)

    def _prompt_open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder:
            self.open_folder(folder)

    def _prompt_create_template(self) -> None:
        templates = self.workspace_manager.templates.list_templates()
        if not templates:
            self.status.show_message("No templates available")
            return
        template, ok = QInputDialog.getItem(self, "Create Workspace", "Template", templates, 0, False)
        if not ok or not template:
            return
        destination = QFileDialog.getExistingDirectory(self, "Choose Destination")
        if not destination:
            return
        workspace_path = self.workspace_manager.templates.create(template, destination)
        self.open_folder(str(workspace_path))

    def _create_share_file_action(self) -> QAction:
        action = QAction("Copy Active File Path", self)
        action.triggered.connect(self._copy_active_file_path)
        return action

    def _create_share_workspace_action(self) -> QAction:
        action = QAction("Copy Workspace Path", self)
        action.triggered.connect(self._copy_workspace_path)
        return action

    def _copy_active_file_path(self) -> None:
        editor = self.get_current_editor()
        if editor and editor.path:
            QApplication.clipboard().setText(str(editor.path))
            self.status.show_message("Copied file path to clipboard")
        else:
            self.status.show_message("No active file to share")

    def _copy_workspace_path(self) -> None:
        workspace = self.workspace_manager.current_workspace
        if workspace:
            QApplication.clipboard().setText(str(workspace))
            self.status.show_message("Copied workspace path to clipboard")
        else:
            self.status.show_message("No workspace open")

    def _launch_new_window(self, profile: str | None = None) -> None:
        executable = sys.executable
        entry = Path(sys.argv[0]).resolve()
        if not entry.exists():
            entry = Path(__file__).resolve().parents[2] / "start.py"

        env = dict(os.environ)
        if profile:
            profile_dir = CONFIG_DIR / "profiles" / profile
            profile_dir.mkdir(parents=True, exist_ok=True)
            env["GHOSTLINE_CONFIG_DIR"] = str(profile_dir)
        else:
            env.setdefault("GHOSTLINE_CONFIG_DIR", str(CONFIG_DIR))

        subprocess.Popen([executable, str(entry)], env=env)

    def _prompt_new_profile_window(self) -> None:
        profile, ok = QInputDialog.getText(self, "Profile", "Profile name", QLineEdit.Normal, "default")
        if not ok or not profile.strip():
            return
        self._launch_new_window(profile.strip())

    def _dirty_editors(self) -> list[CodeEditor]:
        return [editor for editor in self.editor_tabs.iter_editors() if editor.is_dirty()]

    def _confirm_unsaved_changes(self) -> bool:
        dirty = self._dirty_editors()
        if not dirty:
            return True

        answer = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Save them before continuing?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.Yes:
            self.save_all()
        return True

    def _close_folder(self) -> None:
        if not self._confirm_unsaved_changes():
            return
        self.workspace_manager.clear_workspace()
        self._restored_workspace = None
        if hasattr(self, "project_model"):
            self.project_model.set_workspace_root(None)
        self._update_workspace_state()
        if hasattr(self, "terminal"):
            self.terminal.set_workspace(None)
        if hasattr(self, "context_engine"):
            self.context_engine.on_workspace_changed(None)
        self._show_welcome_if_empty()
        self._refresh_recent_views()
        self._update_title_context()

    def open_file_at(self, path: str, line: int) -> None:
        self.open_file(path)
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.MoveAnchor, line)
            editor.setTextCursor(cursor)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if not self._confirm_unsaved_changes():
            event.ignore()
            return
        try:
            if hasattr(self, "analysis_service") and self.analysis_service:
                try:
                    self.analysis_service.shutdown()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if hasattr(self, "lsp_manager") and self.lsp_manager:
                try:
                    self.lsp_manager.shutdown()
                    logger.debug(
                        "LSP manager shutdown invoked during application close; remaining clients: %s",
                        getattr(self.lsp_manager, "clients", {}),
                    )
                except Exception:
                    logger.debug(
                        "LSP manager shutdown encountered an error during application close",
                        exc_info=True,
                    )
        except Exception:
            pass

        from ghostline.core import threads as _threads

        _threads.SHUTTING_DOWN = True

        self.workspace_manager.save_recents()
        window_cfg = self.config.settings.setdefault("window", {})
        window_cfg["maximized"] = self.isMaximized()
        geometry = self.saveGeometry()
        if isinstance(geometry, QByteArray):
            window_cfg["geometry"] = bytes(geometry.toHex()).decode("ascii")

        # Save dock/panel state
        dock_state = {}
        if hasattr(self, "main_splitter"):
            dock_state["main_splitter_sizes"] = self.main_splitter.sizes()
        if hasattr(self, "center_vertical_splitter"):
            dock_state["center_vertical_splitter_sizes"] = self.center_vertical_splitter.sizes()
        if hasattr(self, "left_dock_stack"):
            dock_state["left_dock_index"] = self.left_dock_stack.currentIndex()
        if hasattr(self, "right_dock_stack"):
            dock_state["right_dock_index"] = self.right_dock_stack.currentIndex()
        if hasattr(self, "left_region_container"):
            dock_state["left_region_visible"] = self.left_region_container.isVisible()
        if hasattr(self, "right_region_container"):
            dock_state["right_region_visible"] = self.right_region_container.isVisible()
        if hasattr(self, "bottom_panel"):
            dock_state["bottom_panel_visible"] = self.bottom_panel.isVisible()
            dock_state["bottom_panel_index"] = self.bottom_panel.get_current_panel_index()
        window_cfg["dock_state"] = dock_state

        workspace = self.workspace_manager.current_workspace
        if workspace and hasattr(self, "editor_tabs"):
            tab_session = self.editor_tabs.get_session_state()
            workspace_sessions = self.config.settings.setdefault("workspace_sessions", {})
            workspace_sessions[str(workspace)] = tab_session

        self.config.save()
        super().closeEvent(event)

    def changeEvent(self, event) -> None:  # type: ignore[override]
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and hasattr(self, "title_bar"):
            self.title_bar.update_maximize_icon()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        self.handle_konami(event)
        super().keyPressEvent(event)

    def handle_konami(self, event: QKeyEvent) -> None:
        """Handle Konami code easter egg; set ui.konami_enabled to false to disable."""

        if not self.konami_enabled:
            return
        if event.type() != QEvent.KeyPress:
            return

        key = event.key()
        self._konami_reset_timer.start(4000)
        expected_key = self.konami_sequence[self._konami_index]
        if key == expected_key:
            self._konami_index += 1
            if self._konami_index == len(self.konami_sequence):
                self._konami_index = 0
                self.show_konami_easter_egg()
        else:
            self._konami_index = 1 if key == self.konami_sequence[0] else 0

    def _reset_konami_index(self) -> None:
        self._konami_index = 0

    def show_konami_easter_egg(self) -> None:
        message = "Konami code unlocked!"
        if hasattr(self, "status") and hasattr(self.status, "show_message"):
            try:
                self.status.show_message(message)
                self._on_konami_code()
                return
            except RuntimeError:
                # Status bar might already be disposed during shutdown
                pass

        toast = QWidget(self)
        toast.setObjectName("konamiEasterEggToast")
        toast.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout = QHBoxLayout(toast)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        ghost_icon_path = icon_path("creator_ghost.svg")
        if ghost_icon_path:
            ghost_icon = QIcon(str(ghost_icon_path))
            pixmap = ghost_icon.pixmap(QSize(24, 24))
            if not pixmap.isNull():
                icon_label = QLabel(toast)
                icon_label.setPixmap(pixmap)
                icon_label.setFixedSize(pixmap.size())
                layout.addWidget(icon_label)

        text_label = QLabel(message, toast)
        text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(text_label)

        toast.setStyleSheet(
            """
            #konamiEasterEggToast {
                background-color: rgba(30, 30, 30, 200);
                color: white;
                padding: 6px 10px;
                border-radius: 8px;
                font-weight: bold;
            }
            #konamiEasterEggToast QLabel { color: white; }
            """
        )
        toast.adjustSize()

        available_rect = self.rect()
        x_pos = available_rect.center().x() - toast.width() // 2
        y_pos = available_rect.top() + available_rect.height() // 5
        toast.move(x_pos, y_pos)
        toast.show()
        QTimer.singleShot(2500, toast.deleteLater)
        self._on_konami_code()

    def _on_konami_code(self) -> None:
        logger.info("Konami code detected")

    # Command registration
    def _register_core_commands(self) -> None:
        if hasattr(self, "ui_action_registry"):
            self.ui_action_registry.refresh_enabled()
            return
        registry = self.command_registry
        registry.register_command(CommandDescriptor("file.open", "Open File", "File", self._prompt_open_file))
        registry.register_command(CommandDescriptor("file.save_all", "Save All", "File", self.save_all))
        registry.register_command(CommandDescriptor("view.toggle_project", "Toggle Project", "View", self._toggle_project))
        registry.register_command(CommandDescriptor("view.toggle_terminal", "Toggle Terminal", "View", self._toggle_terminal))
        registry.register_command(
            CommandDescriptor(
                "view.toggle_split", "Toggle Split Editor", "View", lambda: self._toggle_split_editor(not self.editor_tabs.split_active())
            )
        )
        registry.register_command(CommandDescriptor("ai.explain_selection", "Explain Selection", "AI", lambda: self._run_ai_command(explain_selection)))
        registry.register_command(CommandDescriptor("ai.refactor_selection", "Refactor Selection", "AI", lambda: self._run_ai_command(refactor_selection)))
        registry.register_command(CommandDescriptor("ai.toggle_autoflow", "Toggle Autoflow", "AI", self._toggle_autoflow_mode))
        registry.register_command(CommandDescriptor("ai.settings", "AI Settings", "AI", self._open_ai_settings))
        registry.register_command(CommandDescriptor("ai.setup", "Re-run Setup Wizard", "AI", self.show_setup_wizard))
        registry.register_command(CommandDescriptor("search.global", "Find in Files", "Navigate", self._open_global_search))
        registry.register_command(CommandDescriptor("navigate.symbol", "Go to Symbol", "Navigate", self._open_symbol_picker))
        registry.register_command(CommandDescriptor("navigate.file", "Go to File", "Navigate", self._open_file_picker))
        registry.register_command(
            CommandDescriptor(
                "workspace.create_template", "Create Workspace from Template", "Workspace", self._prompt_create_template
            )
        )
        registry.register_command(CommandDescriptor("workflow.run", "Run Pipelines", "Automation", self._run_all_pipelines))
        registry.register_command(CommandDescriptor("tasks.run", "Run Task", "Tasks", self._run_task_command))
        registry.register_command(CommandDescriptor("plugins.manage", "Plugin Manager", "Plugins", self._open_plugin_manager))
        registry.register_command(CommandDescriptor("lsp.restart", "Restart Language Server", "LSP", self._restart_language_server))
        registry.register_command(CommandDescriptor("python.runFile", "Run Current File", "Run", self._run_current_file))

    def _show_and_raise_dock(self, dock: QDockWidget | None, tool_id: str | None = None) -> None:
        if not dock:
            if hasattr(self, "status"):
                self.status.show_message("This tool is coming soon")
            return
        dock.setVisible(True)
        if dock in getattr(self, "left_docks", []):
            self.left_dock_stack.setCurrentWidget(dock)
            self._set_left_docks_visible(True)
            self.toggle_left_region.setChecked(True)
        elif dock in getattr(self, "right_docks", []):
            self.right_dock_stack.setCurrentWidget(dock)
            self.right_region_container.show()
            self.toggle_right_region.setChecked(True)
        elif dock in getattr(self, "bottom_docks", []):
            # Legacy support - bottom docks now managed by BottomPanel
            if hasattr(self, "bottom_panel"):
                self.bottom_panel.show()
                self.toggle_bottom_region.setChecked(True)
        if tool_id and hasattr(self, "activity_bar"):
            self.activity_bar.setActiveTool(tool_id)

    def _connect_activity_bar(self) -> None:
        self.activity_bar.explorerRequested.connect(
            lambda: self._show_and_raise_dock(getattr(self, "project_dock", None), "explorer")
        )
        self.activity_bar.gitRequested.connect(
            lambda: self._show_and_raise_dock(getattr(self, "git_dock", None), "git")
        )
        self.activity_bar.debugRequested.connect(
            lambda: self._show_and_raise_dock(getattr(self, "debugger_dock", None), "debug")
        )
        self.activity_bar.testsRequested.connect(
            lambda: self._show_and_raise_dock(getattr(self, "test_dock", None), "tests")
        )
        self.activity_bar.tasksRequested.connect(
            lambda: self._show_and_raise_dock(getattr(self, "task_dock", None), "tasks")
        )
        self.activity_bar.architectureRequested.connect(
            lambda: self._show_and_raise_dock(getattr(self, "architecture_dock", None), "architecture")
        )
        self.activity_bar.settingsRequested.connect(self._open_settings)

    def _focus_editor_find(self, replace: bool = False) -> None:
        editor = self.get_current_editor()
        if editor:
            editor.show_find_bar(replace=replace)
            editor.setFocus()

    def _focus_global_search(self) -> None:
        query: str | None = None
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                query = cursor.selectedText()
        self._open_global_search(query)

    def _trigger_global_search_action(self) -> None:
        self._focus_global_search()

    def _toggle_project(self, checked: bool) -> None:
        if not hasattr(self, "project_dock"):
            return

        self.view_settings.setdefault("panels", {})["project"] = bool(checked)

        if checked:
            # Show the project dock
            self.left_dock_stack.setCurrentWidget(self.project_dock)
            self.project_dock.show()
            self._set_left_docks_visible(True)
            self.toggle_left_region.setChecked(True)
        else:
            # Hide the left dock container
            self._set_left_docks_visible(False)
            self.toggle_left_region.setChecked(False)

    def _toggle_terminal(self, checked: bool) -> None:
        if not hasattr(self, "bottom_panel"):
            return

        self.view_settings.setdefault("panels", {})["terminal"] = bool(checked)

        self.bottom_panel.setVisible(checked)

        if checked and hasattr(self, "terminal_panel_index"):
            # Ensure the terminal panel is visible when showing the bottom region
            self.bottom_panel.set_current_panel(self.terminal_panel_index)
            self.toggle_bottom_region.setChecked(True)
        else:
            self.toggle_bottom_region.setChecked(False)

        self._update_view_action_states()

    def _toggle_architecture_map(self, checked: bool) -> None:
        dock = getattr(self, "architecture_dock", None)
        if not dock:
            return

        self.view_settings.setdefault("panels", {})["architecture"] = bool(checked)

        if checked:
            # Show the architecture dock
            self.left_dock_stack.setCurrentWidget(dock)
            dock.show()
            self._set_left_docks_visible(True)
            self.toggle_left_region.setChecked(True)
        else:
            # Hide the architecture dock
            dock.hide()

        self._update_view_action_states()

    def _toggle_ai_dock(self, checked: bool) -> None:
        """Toggle visibility of the Ghostline AI dock from the View menu."""
        dock = getattr(self, "ai_dock", None)
        if not dock:
            return

        self.view_settings.setdefault("panels", {})["ai"] = bool(checked)

        dock.setVisible(checked)

        # Make sure the right region is visible when turning the AI panel on
        if checked and hasattr(self, "right_region_container"):
            self.right_region_container.setVisible(True)
            if hasattr(self, "toggle_right_region"):
                self.toggle_right_region.setChecked(True)

        self._update_view_action_states()

    def _toggle_word_wrap(self, checked: bool) -> None:
        self._word_wrap_enabled = bool(checked)
        self.view_settings["word_wrap"] = self._word_wrap_enabled
        editor_cfg = self.config.settings.setdefault("editor", {}) if self.config else {}
        editor_cfg["word_wrap"] = self._word_wrap_enabled

        if hasattr(self, "editor_tabs"):
            for editor in self.editor_tabs.iter_editors():
                if hasattr(editor, "set_word_wrap_enabled"):
                    editor.set_word_wrap_enabled(self._word_wrap_enabled)

    def _toggle_autosave(self, checked: bool) -> None:
        self._autosave_enabled = bool(checked)
        autosave_cfg = self.config.settings.setdefault("autosave", {}) if self.config else {}
        autosave_cfg["enabled"] = self._autosave_enabled
        autosave_cfg.setdefault("interval_seconds", self._autosave_interval)
        self._autosave_interval = int(autosave_cfg.get("interval_seconds", self._autosave_interval))
        if self._autosave_enabled:
            self._autosave_timer.start(self._autosave_interval * 1000)
        else:
            self._autosave_timer.stop()

    def _perform_autosave(self) -> None:
        if not self._autosave_enabled:
            return
        for editor in self.editor_tabs.iter_editors():
            if editor.is_dirty():
                editor.save()
                if editor.path:
                    self.plugin_loader.emit_event("file.saved", path=str(editor.path))
        self.status.show_message("Autosaved dirty files")

    def _toggle_activity_bar_visible(self, checked: bool) -> None:
        self.view_settings.setdefault("bars", {})["activity"] = bool(checked)
        if hasattr(self, "activity_bar"):
            self.activity_bar.setVisible(checked)

    def _toggle_status_bar_visible(self, checked: bool) -> None:
        self.view_settings.setdefault("bars", {})["status"] = bool(checked)
        if hasattr(self, "status"):
            self.status.setVisible(checked)

    def _toggle_menu_bar_visible(self, checked: bool) -> None:
        self.view_settings.setdefault("bars", {})["menu"] = bool(checked)
        if menubar := self.menuBar():
            menubar.setVisible(checked)

    def _refresh_architecture_graph(self) -> None:
        dock = getattr(self, "architecture_dock", None)
        if not dock:
            return
        dock.set_graph(self.semantic_index.get_graph_snapshot())

    def _on_semantic_graph_changed(self, _path: Path) -> None:
        QTimer.singleShot(0, self._refresh_architecture_graph)

    def _open_settings(self) -> None:
        if hasattr(self, "activity_bar"):
            self.activity_bar.setActiveTool("settings")
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            app = QApplication.instance()
            if app:
                self.theme.apply(app)

    def _open_extensions(self) -> None:
        self._open_plugin_manager()

    def _open_keyboard_shortcuts(self) -> None:
        QMessageBox.information(self, "Keyboard Shortcuts", "Keyboard shortcuts UI not implemented yet")

    def _open_snippets(self) -> None:
        QMessageBox.information(self, "Snippets", "Snippets UI not implemented yet")

    def _open_tasks_panel(self) -> None:
        dock = getattr(self, "task_dock", None)
        if dock:
            self._show_and_raise_dock(dock, "tasks")
            return
        QMessageBox.information(self, "Tasks", "Tasks panel not available")

    def _open_ai_settings(self) -> None:
        dialog = AISettingsDialog(self.config, self)
        dialog.exec()

    def show_setup_wizard(self, initial_run: bool = False) -> int:
        wizard = SetupWizardDialog(self.config, self)
        result = wizard.exec()
        if result == QDialog.Accepted:
            self.first_run = False
            self.status.show_message("Setup complete")
        elif initial_run and not self.config.get("first_run_completed", False):
            self.status.show_message("Setup cancelled")
        self._update_workspace_state()
        return result

    def _open_global_search(self, initial_query: str | None = None) -> None:
        dock = getattr(self, "search_dock", None)
        if not dock:
            return
        self._show_and_raise_dock(dock, "search")
        if initial_query:
            dock.open_with_query(initial_query)

    def _apply_theme_from_config(self) -> None:
        configured_theme = self._theme_id_from_value(self.config.get("theme"))
        if configured_theme in self.theme.THEMES and configured_theme != self.theme.theme_name:
            self.theme.set_theme(configured_theme)
            app = QApplication.instance()
            if app:
                self.theme.apply(app)
        if configured_theme:
            self.config.set("theme", self._theme_display_name(configured_theme))

    def _theme_id_from_value(self, value: str | None) -> str:
        if not value:
            return ThemeManager.DEFAULT_THEME
        normalized = value.strip().lower()
        mapping = {tid: self._theme_display_name(tid).lower() for tid in self.theme.THEMES}
        for theme_id, label in mapping.items():
            if normalized in {theme_id.lower(), label}:
                return theme_id
        return ThemeManager.DEFAULT_THEME

    def _theme_display_name(self, theme_id: str) -> str:
        labels = {
            "ghost_dark": "Ghostline Dark",
            "ghost_night": "Ghost Night",
        }
        return labels.get(theme_id, theme_id.replace("_", " ").title())

    def _populate_theme_menu(self, menu: QMenu) -> None:
        menu.clear()
        group = QActionGroup(menu)
        group.setExclusive(True)
        current_theme = self.theme.theme_name
        self._theme_actions.clear()

        for theme_id in self.theme.THEMES:
            action = menu.addAction(self._theme_display_name(theme_id))
            action.setCheckable(True)
            action.setChecked(theme_id == current_theme)
            action.triggered.connect(lambda _checked, tid=theme_id: self._apply_theme_choice(tid))
            group.addAction(action)
            self._theme_actions[theme_id] = action

    def _refresh_theme_checks(self, active_theme: str) -> None:
        for theme_id, action in self._theme_actions.items():
            action.setChecked(theme_id == active_theme)

    def _apply_theme_choice(self, theme_id: str) -> None:
        if theme_id not in self.theme.THEMES:
            return
        self.theme.set_theme(theme_id)
        app = QApplication.instance()
        if app:
            self.theme.apply(app)
        self.config.set("theme", self._theme_display_name(theme_id))
        try:
            self.config.save()
        except Exception:
            logger.exception("Failed to persist theme selection")
        self._refresh_theme_checks(theme_id)

    def _current_user_identity(self) -> tuple[str, str | None]:
        user_cfg = self.config.get("user", {}) if self.config else {}
        name = "Guest"
        email: str | None = None
        if isinstance(user_cfg, dict):
            name = user_cfg.get("display_name") or user_cfg.get("name") or name
            email = user_cfg.get("email")
        return name, email

    def _trigger_sign_in_placeholder(self) -> None:
        QMessageBox.information(self, "Sign in", "Authentication is not implemented yet.")

    def _trigger_sign_out_placeholder(self) -> None:
        QMessageBox.information(self, "Sign out", "No signed-in account to sign out from." if not self._current_user_identity()[1] else "Signed out.")

    def _trigger_manage_account_placeholder(self) -> None:
        QMessageBox.information(self, "Manage Account", "Account management is not implemented yet.")

    def _show_account_details(self) -> None:
        name, email = self._current_user_identity()
        QMessageBox.information(
            self,
            "Ghostline Account",
            f"User: {name}\nEmail: {email or 'not signed in'}",
        )

    def _show_usage_placeholder(self) -> None:
        QMessageBox.information(self, "Ghostline Usage", "Usage not implemented yet")

    def _open_quick_settings_placeholder(self) -> None:
        QMessageBox.information(self, "Quick Settings", "Quick Settings Panel not implemented yet")

    def _check_for_updates(self) -> None:
        current_version = self._detect_app_version()
        latest_version = None
        release_url = CHANGELOG_URL
        try:
            with request.urlopen(
                "https://api.github.com/repos/ghostline-studio/Ghostline-Studio/releases/latest", timeout=5
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            latest_version = payload.get("tag_name") or payload.get("name")
            release_url = QUrl(payload.get("html_url") or CHANGELOG_URL)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.information(
                self,
                "Check for Updates",
                f"Current version: {current_version}\nUnable to reach update service:\n{exc}",
            )
            return

        latest_label = latest_version or "unknown"
        if latest_version and current_version != "unknown" and latest_version.strip("v") != current_version.strip("v"):
            status = f"A new version is available: {latest_label}\nCurrent version: {current_version}"
        else:
            status = f"You are up to date. Current version: {current_version}"
            if current_version == "unknown":
                status = f"Latest release: {latest_label}\nCurrent version: {current_version}"

        box = QMessageBox(self)
        box.setWindowTitle("Check for Updates")
        box.setText(status)
        if latest_version and current_version != latest_version:
            box.setInformativeText("Open the latest release notes?")
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        else:
            box.setStandardButtons(QMessageBox.Ok)

        result = box.exec()
        if box.standardButton(result) == QMessageBox.Yes and isinstance(release_url, QUrl):
            QDesktopServices.openUrl(release_url)

    def _open_license(self) -> None:
        license_path = Path(__file__).resolve().parents[2] / "LICENSE"
        if license_path.exists():
            self.open_file(str(license_path))
            return
        QMessageBox.warning(self, "License", "LICENSE file not found in this installation.")

    def _open_editor_playground(self) -> None:
        if not self._playground_dialog:
            self._playground_dialog = EditorPlaygroundDialog(self.open_file, self)
        self._playground_dialog.show()
        self._playground_dialog.raise_()
        self._playground_dialog.activateWindow()

    def _open_walkthrough(self) -> None:
        if not self._walkthrough_dialog:
            self._walkthrough_dialog = WalkthroughDialog(DOCS_URL, self)
        self._walkthrough_dialog.show()
        self._walkthrough_dialog.raise_()
        self._walkthrough_dialog.activateWindow()

    def _toggle_developer_tools(self) -> None:
        if not self._developer_tools_dialog:
            self._developer_tools_dialog = DeveloperToolsDialog(str(LOG_FILE), self)
        if self._developer_tools_dialog.isVisible():
            self._developer_tools_dialog.close()
            return
        self._developer_tools_dialog.refresh()
        self._developer_tools_dialog.show()
        self._developer_tools_dialog.raise_()
        self._developer_tools_dialog.activateWindow()

    def _open_process_explorer(self) -> None:
        if not self._process_explorer_dialog:
            self._process_explorer_dialog = ProcessExplorerDialog(self._collect_process_snapshot, self)
        self._process_explorer_dialog.refresh()
        self._process_explorer_dialog.show()
        self._process_explorer_dialog.raise_()
        self._process_explorer_dialog.activateWindow()

    def _open_docs(self) -> None:
        QDesktopServices.openUrl(DOCS_URL)

    def _open_feature_request(self) -> None:
        QDesktopServices.openUrl(FEATURE_REQUEST_URL)

    def _open_community(self) -> None:
        QDesktopServices.openUrl(COMMUNITY_URL)

    def _open_changelog(self) -> None:
        QDesktopServices.openUrl(CHANGELOG_URL)

    def _collect_process_snapshot(self) -> list[dict]:
        records: list[dict] = []
        records.append(self._process_record("Ghostline Studio", "App", os.getpid(), "Main application"))

        for label, process in self.task_manager.processes.items():
            pid = int(process.processId()) if process.processId() else None
            records.append(self._process_record(f"Task: {label}", "Task", pid, "Workspace task"))

        if hasattr(self, "terminal_widget"):
            for session in self.terminal_widget.sessions:
                pid = getattr(session.terminal, "pid", None)
                details = f"{session.working_dir}" if session.working_dir else "Terminal session"
                records.append(self._process_record(session.name, "Terminal", pid, details))

        if self.debugger.process:
            records.append(self._process_record("Debugger", "Debug", self.debugger.process.pid, "debugpy session"))

        return records

    def _process_record(self, name: str, kind: str, pid: int | None, details: str) -> dict:
        cpu = "n/a"
        memory = "n/a"
        if pid and self._psutil:
            try:
                proc = self._psutil.Process(pid)
                with proc.oneshot():
                    cpu = f"{proc.cpu_percent(interval=0.0):.1f}%"
                    memory = f"{proc.memory_info().rss / (1024 * 1024):.1f} MB"
            except Exception:
                pass
        return {
            "name": name,
            "type": kind,
            "pid": pid or "–",
            "cpu": cpu,
            "memory": memory,
            "details": details,
        }

    def _detect_app_version(self) -> str:
        try:
            return importlib_metadata.version("ghostline")
        except Exception:
            return "unknown"

    def _download_diagnostics(self) -> None:
        default_name = "ghostline-diagnostics.zip"
        default_path = str(CONFIG_DIR / default_name)
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Diagnostics", default_path, "Zip Files (*.zip)"
        )
        if not filename:
            return
        if not filename.lower().endswith(".zip"):
            filename = f"{filename}.zip"

        temp_dir = Path(tempfile.mkdtemp(prefix="ghostline_diagnostics_"))
        try:
            info = {
                "app_version": self._detect_app_version(),
                "os": platform.platform(),
                "python_version": sys.version.replace("\n", " "),
                "config_dir": str(CONFIG_DIR),
            }
            (temp_dir / "diagnostics.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

            config_files = [USER_SETTINGS_PATH]
            for extra_cfg in CONFIG_DIR.glob("*.yaml"):
                if extra_cfg not in config_files:
                    config_files.append(extra_cfg)
            for extra_cfg in CONFIG_DIR.glob("*.json"):
                if extra_cfg not in config_files:
                    config_files.append(extra_cfg)
            for cfg in config_files:
                if cfg.exists():
                    shutil.copy(cfg, temp_dir / cfg.name)

            log_dir = LOG_DIR if LOG_DIR.exists() else LOG_FILE.parent
            if log_dir.exists():
                copied = False
                for log_path in log_dir.glob("ghostline.log*"):
                    if log_path.is_file():
                        shutil.copy(log_path, temp_dir / log_path.name)
                        copied = True
                if not copied:
                    (temp_dir / "logs.txt").write_text("No log files found.", encoding="utf-8")
            else:
                (temp_dir / "logs.txt").write_text("Log directory missing.", encoding="utf-8")

            with zipfile.ZipFile(filename, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for item in temp_dir.iterdir():
                    archive.write(item, item.name)

            QMessageBox.information(self, "Diagnostics", f"Diagnostics saved to {filename}")
        except Exception:
            logger.exception("Failed to export diagnostics")
            QMessageBox.warning(self, "Diagnostics", "Unable to export diagnostics bundle.")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _open_symbol_picker(self) -> None:
        query, ok = QInputDialog.getText(self, "Go to Symbol", "Name contains:")
        if not ok or not query:
            return

        def _show(symbols):
            if not symbols:
                self.status.show_message("No symbols found")
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("Symbols")
            layout = QVBoxLayout(dialog)
            list_widget = QListWidget(dialog)
            for symbol in symbols:
                item = QListWidgetItem(f"{Path(symbol.file).name}:{symbol.line + 1} {symbol.name}")
                item.setData(Qt.UserRole, symbol)
                list_widget.addItem(item)

            def _activate(item):
                sym = item.data(Qt.UserRole)
                self.open_file_at(sym.file, sym.line)
                dialog.accept()

            list_widget.itemActivated.connect(_activate)
            layout.addWidget(list_widget)
            dialog.exec()

        self.symbols.workspace_symbols(query, _show)

    def _open_file_picker(self) -> None:
        files = [p for p in self.workspace_manager.iter_workspace_files() if p.is_file()]
        if not files:
            return
        name, ok = QInputDialog.getText(self, "Go to File", "Filename contains:")
        if not ok:
            return
        lowered = name.lower()
        for file in files:
            if lowered in file.name.lower():
                self.open_file(str(file))
                return
        self.status.show_message("No matching file found")

    def _open_plugin_manager(self) -> None:
        dialog = PluginManagerDialog(self.plugin_loader, self)
        dialog.exec()

    def _run_task_command(self) -> None:
        self.task_manager.load_workspace_tasks()
        panel = getattr(self, "task_dock", None)
        if panel:
            panel.show()
        if self.task_manager.tasks:
            self.task_manager.run_task(self.task_manager.tasks[0].name)
        else:
            self.status.show_message("No tasks configured in .ghostline/tasks.yaml")

    def _restart_language_server(self) -> None:
        languages = sorted(set(self.lsp_manager._language_map.values()))
        if not languages:
            return
        lang, ok = QInputDialog.getItem(self, "Restart Language Server", "Language", languages, 0, False)
        if ok and lang:
            self.lsp_manager.restart_language_server(lang)

    def _run_ai_command(self, func) -> None:
        editor = self.get_current_editor()
        if editor:
            func(editor, self.ai_client)

    def toggle_ai_dock(self) -> None:
        # Toggle the entire right region container visibility
        right_region = getattr(self, "right_region_container", None)
        if not right_region:
            return
        visible = not right_region.isVisible()
        right_region.setVisible(visible)
        
        # Also ensure the AI dock is visible when showing the right region
        if visible:
            dock = getattr(self, "ai_dock", None)
            if dock:
                dock.show()
                dock.raise_()

    def _focus_ai_dock(self) -> None:
        dock = getattr(self, "ai_dock", None)
        if dock:
            dock.show()
            dock.raise_()

    def _handle_diagnostics(self, diagnostics) -> None:
        app = QApplication.instance()
        if app is None:
            return
        if getattr(self, "isVisible", None) and not self.isVisible():
            return
        try:
            if hasattr(self, "analysis_service") and self.analysis_service:
                self.analysis_service.on_diagnostics([diag.__dict__ for diag in diagnostics])
        except Exception:
            pass
        try:
            if hasattr(self, "diagnostics_model") and self.diagnostics_model:
                self.diagnostics_model.set_diagnostics(diagnostics)
        except RuntimeError:
            return
        except Exception:
            return
        if hasattr(self, "diagnostics_empty"):
            has_items = bool(diagnostics)
            self.diagnostics_empty.setVisible(not has_items)
            self.diagnostics_view.setVisible(has_items)
        for editor in self.editor_tabs.iter_editors():
            file_diags = [d for d in diagnostics if d.file == str(editor.path)]
            editor.apply_diagnostics(file_diags)

    def _jump_to_diagnostic(self, index) -> None:
        file_path = self.diagnostics_model.item(index.row(), 0).text()
        line = int(self.diagnostics_model.item(index.row(), 1).text()) - 1
        self.open_file(file_path)
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.MoveAnchor, line)
            editor.setTextCursor(cursor)

    def _on_help_menu_about_to_show(self) -> None:
        reveal_easter_egg = QApplication.keyboardModifiers() & Qt.ShiftModifier
        self.action_ghost_terminal.setVisible(bool(reveal_easter_egg))

    def _open_ghost_terminal(self) -> None:
        if not hasattr(self, "_ghost_terminal_dialog"):
            dialog = QDialog(self)
            dialog.setWindowTitle("Ghost Terminal")
            layout = QVBoxLayout(dialog)
            self._ghost_terminal_widget = GhostTerminalWidget(dialog)
            layout.addWidget(self._ghost_terminal_widget)
            dialog.setLayout(layout)
            dialog.resize(480, 320)
            self._ghost_terminal_dialog = dialog

        self._ghost_terminal_dialog.show()
        self._ghost_terminal_dialog.raise_()
        self._ghost_terminal_dialog.activateWindow()
        self._ghost_terminal_widget.reset_game()

    def _show_about(self) -> None:
        version = self._detect_app_version()
        build_timestamp = datetime.fromtimestamp(Path(__file__).stat().st_mtime)
        build_date = build_timestamp.strftime("%Y-%m-%d %H:%M")
        python_version = sys.version.split()[0]
        os_info = platform.platform()
        details = (
            f"Version: {version}\n"
            f"Build date: {build_date}\n"
            f"Python: {python_version}\n"
            f"OS: {os_info}\n"
            f"Config path: {CONFIG_DIR}"
        )
        QMessageBox.information(self, "About Ghostline Studio", details)
