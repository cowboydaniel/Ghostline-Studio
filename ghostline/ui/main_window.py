"""Main window for Ghostline Studio."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QByteArray, QUrl, QPoint, QEvent, QModelIndex, QSize
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeyEvent
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
    QStyle,
)

from ghostline.core.config import ConfigManager
from ghostline.core.events import CommandDescriptor, CommandRegistry
from ghostline.core.resources import load_icon
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
from ghostline.search.global_search import GlobalSearchDialog
from ghostline.search.symbol_search import SymbolSearcher
from ghostline.plugins.loader import PluginLoader
from ghostline.ui.dialogs.settings_dialog import SettingsDialog
from ghostline.ui.dialogs.plugin_manager_dialog import PluginManagerDialog
from ghostline.ui.dialogs.setup_wizard import SetupWizardDialog
from ghostline.ui.dialogs.ai_settings_dialog import AISettingsDialog
from ghostline.ui.command_palette import CommandPalette
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


class GhostlineTitleBar(QWidget):
    """Custom frameless title bar with navigation and command search."""

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self._drag_position: QPoint | None = None

        self.setObjectName("GhostlineTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        left_container = QWidget(self)
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        icon_button = QToolButton(left_container)
        icon_button.setObjectName("TitleIconButton")
        icon_button.setIcon(load_icon("ghostline_logo.svg"))
        icon_button.setAutoRaise(True)
        icon_button.setToolTip("Ghostline Studio")
        left_layout.addWidget(icon_button)

        menubar: QMenuBar = self.window.menuBar()
        menubar.setNativeMenuBar(False)
        menubar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        left_layout.addWidget(menubar)

        center_container = QWidget(self)
        center_layout = QHBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)

        # TODO: Wire navigation buttons to history actions when available.
        self.back_button = QToolButton(center_container)
        self.back_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.back_button.setEnabled(False)
        self.back_button.setToolTip("Back (not yet implemented)")
        center_layout.addWidget(self.back_button)

        self.forward_button = QToolButton(center_container)
        self.forward_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.forward_button.setEnabled(False)
        self.forward_button.setToolTip("Forward (not yet implemented)")
        center_layout.addWidget(self.forward_button)

        self.command_input = QLineEdit(center_container)
        self.command_input.setObjectName("CommandSearch")
        self.command_input.setPlaceholderText("Search files and commands…")
        self.command_input.returnPressed.connect(self._emit_command_search)
        center_layout.addWidget(self.command_input)

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
        right_layout.setSpacing(4)

        self.minimize_button = QToolButton(right_container)
        self.minimize_button.setObjectName("WindowControl")
        self.minimize_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMinButton))
        self.minimize_button.clicked.connect(self.window.showMinimized)
        right_layout.addWidget(self.minimize_button)

        self.maximize_button = QToolButton(right_container)
        self.maximize_button.setObjectName("WindowControl")
        self.maximize_button.clicked.connect(self.window.toggle_maximize_restore)
        right_layout.addWidget(self.maximize_button)

        self.close_button = QToolButton(right_container)
        self.close_button.setObjectName("CloseControl")
        self.close_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
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

    def _emit_command_search(self) -> None:
        self.window.show_command_palette(self.command_input.text())

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            #GhostlineTitleBar {
                background: palette(window);
                border-bottom: 1px solid palette(mid);
            }
            #GhostlineTitleBar QWidget {
                background: transparent;
            }
            #GhostlineTitleBar QMenuBar {
                background: transparent;
                border: none;
            }
            #GhostlineTitleBar QToolBar {
                background: transparent;
                border: none;
                spacing: 0;
            }
            #GhostlineTitleBar QToolButton {
                background: transparent;
                border: none;
                padding: 6px 8px;
                border-radius: 6px;
            }
            #GhostlineTitleBar QToolButton:hover {
                background: rgba(255, 255, 255, 0.08);
            }
            #CloseControl:hover {
                background: #d9534f;
                color: white;
            }
            #CommandSearch {
                border-radius: 14px;
                padding: 6px 10px;
                background: palette(base);
                border: 1px solid palette(mid);
                min-height: 28px;
            }
            #CommandSearch:focus {
                border: 1px solid palette(highlight);
            }
        """
        )

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
        self.workspace_manager = workspace_manager
        self.git = GitIntegration()
        self.lsp_manager = LSPManager(config, workspace_manager)
        self.workspace_manager.workspaceChanged.connect(lambda _=None: self._refresh_recent_views())
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
        self.ai_command_adapter = AICommandAdapter(self.command_registry, self.command_palette)
        self._create_actions()
        self._create_menus()
        self._install_title_bar()
        self._create_terminal_dock()
        self._create_project_dock()
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
        self._connect_dock_toggles()
        self._update_workspace_state()
        self._show_welcome_if_empty()

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
            button.setMinimumSize(QSize(24, 24))
            button.setMaximumSize(QSize(28, 28))
            button.setIconSize(QSize(16, 16))
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

    def _enforce_left_exclusivity(self, dock: QDockWidget, visible: bool) -> None:
        if not visible or self.dockWidgetArea(dock) != Qt.LeftDockWidgetArea or dock.isFloating():
            return
        for other in self.left_docks:
            if other is dock:
                continue
            if other.isVisible() and not other.isFloating() and self.dockWidgetArea(other) == Qt.LeftDockWidgetArea:
                other.hide()

    def _create_actions(self) -> None:
        self.action_open_file = QAction("Open File", self)
        self.action_open_file.triggered.connect(self._prompt_open_file)

        self.action_open_folder = QAction("Open Folder", self)
        self.action_open_folder.triggered.connect(self._prompt_open_folder)

        self.action_close_folder = QAction("Close Folder", self)
        self.action_close_folder.triggered.connect(self._close_folder)

        self.action_global_search = QAction("Global Search", self)
        self.action_global_search.setShortcut("Ctrl+Shift+F")
        self.action_global_search.triggered.connect(self._trigger_global_search_action)

        self.action_goto_symbol = QAction("Go to Symbol", self)
        self.action_goto_symbol.triggered.connect(self._open_symbol_picker)

        self.action_goto_file = QAction("Go to File", self)
        self.action_goto_file.triggered.connect(self._open_file_picker)

        self.action_command_palette = QAction("Command Palette", self)
        self.action_command_palette.setShortcut("Ctrl+P")
        self.action_command_palette.triggered.connect(self.show_command_palette)

        self.action_toggle_autoflow = QAction("Toggle Autoflow Mode", self)
        self.action_toggle_autoflow.setCheckable(True)
        self.action_toggle_autoflow.triggered.connect(self._toggle_autoflow_mode)

        self.action_toggle_project = QAction("Explorer", self)
        self.action_toggle_project.setCheckable(True)
        self.action_toggle_project.setChecked(True)  # Explorer is visible by default
        self.action_toggle_project.triggered.connect(self._toggle_project)

        self.action_toggle_split_editor = QAction("Split Editor", self)
        self.action_toggle_split_editor.setCheckable(True)
        self.action_toggle_split_editor.triggered.connect(self._toggle_split_editor)

        self.action_toggle_terminal = QAction("Terminal", self)
        self.action_toggle_terminal.setCheckable(True)
        self.action_toggle_terminal.triggered.connect(self._toggle_terminal)

        self.action_toggle_architecture_map = QAction("3D Architecture Map", self)
        self.action_toggle_architecture_map.setCheckable(True)
        self.action_toggle_architecture_map.triggered.connect(self._toggle_architecture_map)

        self.action_toggle_ai_dock = QAction("Ghostline AI", self)
        self.action_toggle_ai_dock.setCheckable(True)
        self.action_toggle_ai_dock.setChecked(True)  # AI dock is visible by default
        self.action_toggle_ai_dock.triggered.connect(self._toggle_ai_dock)

        self.action_settings = QAction("Settings", self)
        self.action_settings.triggered.connect(self._open_settings)

        self.action_ai_settings = QAction("AI Settings…", self)
        self.action_ai_settings.triggered.connect(self._open_ai_settings)

        self.action_setup_wizard = QAction("Re-run Setup Wizard…", self)
        self.action_setup_wizard.triggered.connect(self.show_setup_wizard)

        self.action_ai_explain = QAction("Explain Selection", self)
        self.action_ai_explain.triggered.connect(lambda: self._run_ai_command(explain_selection))

        self.action_ai_refactor = QAction("Refactor Selection", self)
        self.action_ai_refactor.triggered.connect(lambda: self._run_ai_command(refactor_selection))

        self.action_ai_code_actions = QAction("AI Code Actions...", self)
        self.action_ai_code_actions.triggered.connect(lambda: self._run_ai_command(ai_code_actions))

        self.action_ask_ai = QAction("Toggle AI Panel", self)
        self.action_ask_ai.triggered.connect(self.toggle_ai_dock)

        self.action_open_plugins = QAction("Plugins", self)
        self.action_open_plugins.triggered.connect(self._open_plugin_manager)

        self.action_run_task = QAction("Run Task...", self)
        self.action_run_task.setShortcut("Ctrl+Shift+R")
        self.action_run_task.triggered.connect(self._run_task_command)

        self.action_restart_language = QAction("Restart Language Server", self)
        self.action_restart_language.triggered.connect(self._restart_language_server)

        self.action_format_document = QAction("Format Document", self)
        self.action_format_document.triggered.connect(self._format_current_document)

        # Edit actions
        self.action_undo = QAction("Undo", self)
        self.action_undo.setShortcut("Ctrl+Z")
        self.action_undo.triggered.connect(lambda: self._with_editor(lambda e: e.undo()))

        self.action_redo = QAction("Redo", self)
        self.action_redo.setShortcut("Ctrl+Shift+Z")
        self.action_redo.triggered.connect(lambda: self._with_editor(lambda e: e.redo()))

        self.action_cut = QAction("Cut", self)
        self.action_cut.setShortcut("Ctrl+X")
        self.action_cut.triggered.connect(lambda: self._with_editor(lambda e: e.cut()))

        self.action_copy = QAction("Copy", self)
        self.action_copy.setShortcut("Ctrl+C")
        self.action_copy.triggered.connect(lambda: self._with_editor(lambda e: e.copy()))

        self.action_paste = QAction("Paste", self)
        self.action_paste.setShortcut("Ctrl+V")
        self.action_paste.triggered.connect(lambda: self._with_editor(lambda e: e.paste()))

        self.action_find = QAction("Find", self)
        self.action_find.setShortcut("Ctrl+F")
        self.action_find.triggered.connect(self._open_global_search)

        self.action_replace = QAction("Replace", self)
        self.action_replace.setShortcut("Ctrl+H")
        self.action_replace.triggered.connect(self._open_global_search)

        # Project/Run/Debug
        self.action_project_settings = QAction("Project Settings", self)
        self.action_project_settings.triggered.connect(lambda: self.status.show_message("Project settings coming soon"))

        self.action_run = QAction("Run", self)
        self.action_run.triggered.connect(lambda: self.status.show_message("Run current project"))

        self.action_run_tests = QAction("Run Tests", self)
        self.action_run_tests.triggered.connect(self._run_tests)

        self.action_run_tasks = QAction("Run Tasks", self)
        self.action_run_tasks.triggered.connect(self._run_task_command)

        self.action_start_debugging = QAction("Start Debugging", self)
        self.action_start_debugging.triggered.connect(lambda: self.status.show_message("Starting debugger"))

        self.action_stop_debugging = QAction("Stop Debugging", self)
        self.action_stop_debugging.triggered.connect(lambda: self.status.show_message("Debugger stopped"))

        self.action_step_over = QAction("Step Over", self)
        self.action_step_over.triggered.connect(lambda: self.status.show_message("Step over"))

        self.action_step_into = QAction("Step Into", self)
        self.action_step_into.triggered.connect(lambda: self.status.show_message("Step into"))

        self.action_step_out = QAction("Step Out", self)
        self.action_step_out.triggered.connect(lambda: self.status.show_message("Step out"))

        # Help actions
        self.action_docs = QAction("Documentation", self)
        self.action_docs.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com")))

        self.action_report_issue = QAction("Report Issue", self)
        self.action_report_issue.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com")))

        self.action_about = QAction("About Ghostline Studio", self)
        self.action_about.triggered.connect(self._show_about)

        self.action_ghost_terminal = QAction("Ghost Terminal...", self)
        self.action_ghost_terminal.setVisible(False)
        self.action_ghost_terminal.triggered.connect(self._open_ghost_terminal)

    def _create_menus(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction(self.action_open_file)
        file_menu.addAction(self.action_open_folder)
        file_menu.addAction(self.action_close_folder)
        file_menu.addSeparator()
        file_menu.addAction(self.action_settings)

        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_cut)
        edit_menu.addAction(self.action_copy)
        edit_menu.addAction(self.action_paste)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_find)
        edit_menu.addAction(self.action_replace)

        self.view_menu = menubar.addMenu("View")
        self.view_menu.addAction(self.action_command_palette)
        self.view_menu.addAction(self.action_toggle_project)
        self.view_menu.addAction(self.action_toggle_split_editor)
        self.view_menu.addAction(self.action_toggle_terminal)
        self.view_menu.addAction(self.action_global_search)
        self.view_menu.addAction(self.action_goto_symbol)
        self.view_menu.addAction(self.action_goto_file)
        self.view_menu.addAction(self.action_toggle_architecture_map)
        self.view_menu.addAction(self.action_toggle_ai_dock)
        self.view_menu.addAction(self.action_restart_language)

        project_menu = menubar.addMenu("Project")
        project_menu.addAction(self.action_open_folder)
        project_menu.addAction(self.action_close_folder)
        project_menu.addAction(self.action_project_settings)

        run_menu = menubar.addMenu("Run")
        run_menu.addAction(self.action_run)
        run_menu.addAction(self.action_run_tests)
        run_menu.addAction(self.action_run_tasks)

        debug_menu = menubar.addMenu("Debug")
        debug_menu.addAction(self.action_start_debugging)
        debug_menu.addAction(self.action_stop_debugging)
        debug_menu.addAction(self.action_step_over)
        debug_menu.addAction(self.action_step_into)
        debug_menu.addAction(self.action_step_out)

        ai_menu = menubar.addMenu("AI")
        ai_menu.addAction(self.action_ask_ai)
        ai_menu.addAction(self.action_ai_explain)
        ai_menu.addAction(self.action_ai_refactor)
        ai_menu.addAction(self.action_ai_code_actions)
        ai_menu.addSeparator()
        ai_menu.addAction(self.action_ai_settings)
        ai_menu.addAction(self.action_setup_wizard)

        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction(self.action_open_plugins)
        tools_menu.addAction(self.action_run_task)
        tools_menu.addAction(self.action_format_document)

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(self.action_docs)
        help_menu.addAction(self.action_report_issue)
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

    def _toggle_autoflow_mode(self) -> None:
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

    def _close_folder(self) -> None:
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

    def open_file_at(self, path: str, line: int) -> None:
        self.open_file(path)
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.MoveAnchor, line)
            editor.setTextCursor(cursor)

    def closeEvent(self, event) -> None:  # type: ignore[override]
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
        self._on_konami_code()

    def _on_konami_code(self) -> None:
        logger.info("Konami code detected")

    # Command registration
    def _register_core_commands(self) -> None:
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
        registry.register_command(CommandDescriptor("search.global", "Global Search", "Navigate", self._open_global_search))
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

    def _focus_global_search(self) -> None:
        query: str | None = None
        if hasattr(self, "title_bar") and hasattr(self.title_bar, "command_input"):
            query = self.title_bar.command_input.text()
            self.title_bar.command_input.setFocus()
            self.title_bar.command_input.selectAll()
        self._open_global_search(query)

    def _trigger_global_search_action(self) -> None:
        self._focus_global_search()

    def _toggle_project(self, checked: bool) -> None:
        if not hasattr(self, "project_dock"):
            return

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

        dock.setVisible(checked)

        # Make sure the right region is visible when turning the AI panel on
        if checked and hasattr(self, "right_region_container"):
            self.right_region_container.setVisible(True)
            if hasattr(self, "toggle_right_region"):
                self.toggle_right_region.setChecked(True)

        self._update_view_action_states()

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
        if not hasattr(self, "_global_search_dialog"):
            self._global_search_dialog = GlobalSearchDialog(
                lambda: str(self.workspace_manager.current_workspace) if self.workspace_manager.current_workspace else None,
                lambda path, line: self.open_file_at(path, line),
                self,
            )

        if initial_query:
            if hasattr(self._global_search_dialog, "open_with_query"):
                self._global_search_dialog.open_with_query(initial_query)
            else:
                self._global_search_dialog.input.setText(initial_query)
        self._global_search_dialog.show()
        self._global_search_dialog.raise_()

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
        QMessageBox.information(
            self,
            "About Ghostline Studio",
            "Ghostline Studio\nA code understanding environment with AI assistance.",
        )
