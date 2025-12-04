"""Main window for Ghostline Studio."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QByteArray, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QDockWidget,
    QLabel,
    QMainWindow,
    QWidget,
    QTableView,
    QInputDialog,
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QStackedLayout,
    QLineEdit,
    QMessageBox,
)

from ghostline.core.config import ConfigManager
from ghostline.core.events import Command, CommandRegistry
from ghostline.core.theme import ThemeManager
from ghostline.lang.diagnostics import DiagnosticsModel
from ghostline.lang.lsp_manager import LSPManager
from ghostline.agents.agent_manager import AgentManager
from ghostline.ai.ai_client import AIClient
from ghostline.ai.ai_chat_panel import AIChatPanel
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
from ghostline.search.global_search import GlobalSearchDialog
from ghostline.search.symbol_search import SymbolSearcher
from ghostline.plugins.loader import PluginLoader
from ghostline.ui.dialogs.settings_dialog import SettingsDialog
from ghostline.ui.dialogs.plugin_manager_dialog import PluginManagerDialog
from ghostline.ui.dialogs.setup_wizard import SetupWizardDialog
from ghostline.ui.dialogs.ai_settings_dialog import AISettingsDialog
from ghostline.ui.command_palette import CommandPalette
from ghostline.ui.status_bar import StudioStatusBar
from ghostline.ui.layout_manager import LayoutManager
from ghostline.ui.tabs import EditorTabs
from ghostline.ui.workspace_dashboard import WorkspaceDashboard
from ghostline.visual3d.architecture_dock import ArchitectureDock
from ghostline.ui.docks.build_panel import BuildPanel
from ghostline.ui.docks.agent_console import AgentConsole
from ghostline.ui.docks.collab_panel import CollabPanel
from ghostline.ui.docks.doc_panel import DocPanel
from ghostline.ui.docks.pipeline_panel import PipelinePanel
from ghostline.ui.docks.runtime_panel import RuntimePanel
from ghostline.workspace.workspace_manager import WorkspaceManager
from ghostline.workspace.project_model import ProjectModel
from ghostline.workspace.project_view import ProjectView
from ghostline.terminal.terminal_widget import TerminalWidget
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


class MainWindow(QMainWindow):
    """Hosts docks, tabs, and menus."""

    def __init__(
        self, config: ConfigManager, theme: ThemeManager, workspace_manager: WorkspaceManager
    ) -> None:
        super().__init__(None, Qt.Window)  # Set window type and parent
        # Ensure proper window flags for maximize button
        self.setWindowFlags(self.windowFlags() | 
                          Qt.WindowMinimizeButtonHint | 
                          Qt.WindowMaximizeButtonHint |
                          Qt.WindowCloseButtonHint)
        # Ensure the window has proper size constraints
        self.setMinimumSize(800, 600)
        self.config = config
        self.theme = theme
        self.workspace_manager = workspace_manager
        self.git = GitIntegration()
        self.lsp_manager = LSPManager(config, workspace_manager)
        self.command_registry = CommandRegistry()
        self.ai_client = AIClient(config)
        self.symbols = SymbolSearcher(self.lsp_manager)
        self.index_manager = IndexManager(lambda: self.workspace_manager.current_workspace)
        self.semantic_index = SemanticIndexManager(lambda: self.workspace_manager.current_workspace)
        self.semantic_query = SemanticQueryEngine(self.semantic_index.graph)
        self.workspace_memory = WorkspaceMemory(self.config.workspace_memory_path)
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
        self._recent_files_by_workspace: dict[str, list[str]] = {}

        self.setWindowTitle("Ghostline Studio")
        self.resize(1200, 800)

        self.editor_tabs = EditorTabs(
            self, config=self.config, theme=self.theme, lsp_manager=self.lsp_manager, ai_client=self.ai_client
        )
        self.editor_tabs.countChanged.connect(self._update_central_stack)

        self.empty_state = self._create_empty_state()
        self.workspace_dashboard = WorkspaceDashboard(
            open_file=self.open_file,
            open_palette=self.show_command_palette,
        )
        self.central_stack = QStackedLayout()
        self.central_stack.setContentsMargins(0, 0, 0, 0)
        self.central_stack.addWidget(self.empty_state)
        self.central_stack.addWidget(self.workspace_dashboard)
        self.central_stack.addWidget(self.editor_tabs)
        central_container = QWidget(self)
        central_container.setObjectName("EditorArea")
        central_container.setLayout(self.central_stack)
        self.setCentralWidget(central_container)

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
            """
        )

        self.command_palette = CommandPalette(self)
        self.command_palette.set_registry(self.command_registry)
        self.command_palette.set_navigation_assistant(self.navigation_assistant)
        self.command_palette.set_autoflow_mode("passive")
        self.command_palette.set_file_provider(self._search_workspace_files)
        self.command_palette.set_open_file_handler(self.open_file)
        self._create_actions()
        self._create_menus()
        self._create_menu_search()
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

        self.lsp_manager.subscribe_diagnostics(self._handle_diagnostics)
        self.lsp_manager.lsp_error.connect(lambda msg: self.status.show_message(msg))
        self.lsp_manager.lsp_notice.connect(lambda msg: self.status.show_message(msg))
        self.plugin_loader.load_all()
        self.task_manager.load_workspace_tasks()
        self._apply_initial_layout()
        self._update_workspace_state()
        self._update_central_stack()

    def _create_empty_state(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)

        title = QLabel("Ghostline Studio", widget)
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Open a workspace to start exploring your codebase.", widget)
        subtitle.setAlignment(Qt.AlignCenter)

        button_row = QHBoxLayout()
        open_folder_btn = QPushButton("Open Folder…", widget)
        open_folder_btn.clicked.connect(self._prompt_open_folder)
        open_file_btn = QPushButton("Open File…", widget)
        open_file_btn.clicked.connect(self._prompt_open_file)
        palette_btn = QPushButton("Command Palette…", widget)
        palette_btn.clicked.connect(self.show_command_palette)
        for btn in (open_folder_btn, open_file_btn, palette_btn):
            button_row.addWidget(btn)

        hint_label = QLabel("Press Ctrl+O to open a file\nPress Ctrl+P to open the Command Palette.", widget)
        hint_label.setAlignment(Qt.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(button_row)
        layout.addWidget(hint_label)
        layout.addStretch(2)
        return widget

    def _update_central_stack(self) -> None:
        workspace = self.workspace_manager.current_workspace
        if self.editor_tabs.count():
            self.central_stack.setCurrentWidget(self.editor_tabs)
            return

        if workspace:
            workspace_str = str(workspace)
            last_path = self._recent_files_by_workspace.get(workspace_str, [None])
            last_file = last_path[0] if last_path else None
            if last_file and Path(last_file).exists():
                self.open_file(last_file)
                return

            self.workspace_dashboard.set_workspace(workspace, self._recent_files_by_workspace.get(workspace_str, []))
            self.central_stack.setCurrentWidget(self.workspace_dashboard)
        else:
            self.central_stack.setCurrentWidget(self.empty_state)

    def _apply_initial_layout(self) -> None:
        if hasattr(self, "terminal_dock") and hasattr(self, "diagnostics_dock"):
            self.tabifyDockWidget(self.terminal_dock, self.diagnostics_dock)
        if hasattr(self, "task_dock"):
            self.tabifyDockWidget(self.diagnostics_dock, self.task_dock)
        if hasattr(self, "test_dock"):
            self.tabifyDockWidget(self.diagnostics_dock, self.test_dock)
        if hasattr(self, "build_dock"):
            self.tabifyDockWidget(self.diagnostics_dock, self.build_dock)

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

        if self.first_run and hasattr(self, "debugger_dock"):
            self.debugger_dock.show()

        if hasattr(self, "project_dock") and hasattr(self, "ai_dock"):
            self.resizeDocks([self.project_dock, self.ai_dock], [320, 720], Qt.Horizontal)
        if hasattr(self, "terminal_dock") and hasattr(self, "diagnostics_dock"):
            self.resizeDocks([self.terminal_dock, self.diagnostics_dock], [280, 220], Qt.Vertical)

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

    def _update_workspace_state(self) -> None:
        workspace = self.workspace_manager.current_workspace
        has_workspace = workspace is not None
        self.agent_manager.set_workspace_active(has_workspace)
        if hasattr(self, "project_stack"):
            target = self.project_view if has_workspace else self.project_placeholder
            self.project_stack.setCurrentWidget(target)
            if not has_workspace:
                self.project_model.set_workspace_root(None)
                self.project_view.setRootIndex(self.project_model.index(str(Path(""))))

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

    def _register_dock_action(self, dock: QDockWidget) -> None:
        if hasattr(self, "view_menu"):
            if dock.objectName() in {"projectDock", "terminalDock", "architectureDock"}:
                return
            self.view_menu.addAction(dock.toggleViewAction())

    def _create_actions(self) -> None:
        self.action_open_file = QAction("Open File", self)
        self.action_open_file.triggered.connect(self._prompt_open_file)

        self.action_open_folder = QAction("Open Folder", self)
        self.action_open_folder.triggered.connect(self._prompt_open_folder)

        self.action_close_folder = QAction("Close Folder", self)
        self.action_close_folder.triggered.connect(self._close_folder)

        self.action_global_search = QAction("Global Search", self)
        self.action_global_search.setShortcut("Ctrl+Shift+F")
        self.action_global_search.triggered.connect(self._open_global_search)

        self.action_goto_symbol = QAction("Go to Symbol", self)
        self.action_goto_symbol.triggered.connect(self._open_symbol_picker)

        self.action_goto_file = QAction("Go to File", self)
        self.action_goto_file.triggered.connect(self._open_file_picker)

        self.action_command_palette = QAction("Command Palette", self)
        self.action_command_palette.setShortcut("Ctrl+P")
        self.action_command_palette.triggered.connect(self.show_command_palette)

        self.action_search_bar = QAction("Search", self)
        self.action_search_bar.setShortcut("Ctrl+P")

        self.action_toggle_autoflow = QAction("Toggle Autoflow Mode", self)
        self.action_toggle_autoflow.triggered.connect(self._toggle_autoflow_mode)

        self.action_toggle_project = QAction("Project Explorer", self)
        self.action_toggle_project.triggered.connect(self._toggle_project)

        self.action_toggle_terminal = QAction("Terminal", self)
        self.action_toggle_terminal.triggered.connect(self._toggle_terminal)

        self.action_toggle_architecture_map = QAction("3D Architecture Map", self)
        self.action_toggle_architecture_map.triggered.connect(self._toggle_architecture_map)

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

        self.action_ask_ai = QAction("Ask Ghostline AI…", self)
        self.action_ask_ai.triggered.connect(self._focus_ai_dock)

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
        self.view_menu.addAction(self.action_toggle_terminal)
        self.view_menu.addAction(self.action_global_search)
        self.view_menu.addAction(self.action_goto_symbol)
        self.view_menu.addAction(self.action_goto_file)
        self.view_menu.addAction(self.action_toggle_architecture_map)
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

    def _create_menu_search(self) -> None:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 8, 2)
        layout.setSpacing(6)
        self.menu_search = QLineEdit(container)
        self.menu_search.setPlaceholderText("Search files and commands…")
        self.menu_search.returnPressed.connect(self._handle_menu_search)
        hint = QLabel("Ctrl+P", container)
        hint.setStyleSheet("color: palette(mid); font-size: 11px;")
        layout.addWidget(self.menu_search)
        layout.addWidget(hint)
        self.menuBar().setCornerWidget(container, Qt.TopRightCorner)

    def _handle_menu_search(self) -> None:
        text = self.menu_search.text()
        self.show_command_palette(text)

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
        dock = QDockWidget("Terminal", self)
        dock.setObjectName("terminalDock")
        terminal = TerminalWidget(self.workspace_manager)
        dock.setWidget(terminal)
        dock.setMinimumHeight(140)
        dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.terminal = terminal
        self.terminal_dock = dock

    def _create_project_dock(self) -> None:
        dock = QDockWidget("Project", self)
        dock.setObjectName("projectDock")
        dock.setMinimumWidth(280)
        dock.setMaximumWidth(520)
        self.project_model = ProjectModel(self)
        self.project_view = ProjectView(self)
        self.project_view.setTextElideMode(Qt.ElideRight)
        self.project_view.setStyleSheet("QTreeView { font-size: 12px; }")
        self.project_view.setIndentation(18)
        self.project_view.setColumnWidth(0, 280)
        self.project_view.set_model(self.project_model)
        self.project_placeholder = QLabel("No workspace open. Use File → Open Folder…", self)
        self.project_placeholder.setAlignment(Qt.AlignCenter)
        self.project_placeholder.setWordWrap(True)
        container = QWidget(self)
        self.project_stack = QStackedLayout(container)
        self.project_stack.setContentsMargins(8, 8, 8, 8)
        self.project_stack.addWidget(self.project_placeholder)
        self.project_stack.addWidget(self.project_view)
        dock.setWidget(container)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.project_dock = dock

    def _create_ai_dock(self) -> None:
        dock = QDockWidget("Ghostline AI", self)
        dock.setObjectName("aiDock")
        panel = AIChatPanel(self.ai_client, self)
        panel.set_context_provider(lambda: self.get_current_editor().toPlainText() if self.get_current_editor() else "")
        dock.setWidget(panel)
        dock.setMinimumWidth(260)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
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
        dock.setMinimumHeight(140)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.diagnostics_view = table
        self.diagnostics_dock = dock

    def _create_debugger_dock(self) -> None:
        dock = QDockWidget("Debugger", self)
        dock.setObjectName("debuggerDock")
        panel = DebuggerPanel(self.debugger, self)
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.debugger_panel = panel
        self.debugger_dock = dock

    def _create_task_dock(self) -> None:
        dock = QDockWidget("Tasks", self)
        dock.setObjectName("tasksDock")
        panel = TaskPanel(self.task_manager, self)
        dock.setWidget(panel)
        dock.setMinimumHeight(140)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.task_dock = dock

    def _create_test_dock(self) -> None:
        dock = QDockWidget("Tests", self)
        dock.setObjectName("testsDock")
        panel = TestPanel(self.test_manager, self.get_current_editor, self)
        dock.setWidget(panel)
        dock.setMinimumHeight(140)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.test_dock = dock

    def _create_architecture_dock(self) -> None:
        dock = ArchitectureDock(self)
        dock.setObjectName("architectureDock")
        dock.open_file_requested.connect(self._open_graph_location)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.architecture_dock = dock
        self._refresh_architecture_graph()

    def _create_build_dock(self) -> None:
        dock = BuildPanel(self.build_manager, self)
        dock.setObjectName("buildDock")
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.build_dock = dock

    def _create_doc_dock(self) -> None:
        dock = DocPanel(self.doc_generator, self)
        dock.setObjectName("docDock")
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
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
        dock.setMinimumWidth(240)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.git_panel = panel
        self.git_dock = dock

    def _create_coverage_dock(self) -> None:
        dock = QDockWidget("Coverage", self)
        dock.setObjectName("coverageDock")
        dock.setWidget(CoveragePanel(self))
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.coverage_dock = dock

    def _create_collaboration_dock(self) -> None:
        dock = CollabPanel(self.crdt_engine, self.collab_transport, self)
        dock.setObjectName("collabDock")
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.collab_dock = dock

    def _create_agent_console_dock(self) -> None:
        dock = AgentConsole(self.agent_manager, self)
        dock.setObjectName("agentConsoleDock")
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.agent_console_dock = dock

    def _create_pipeline_dock(self) -> None:
        dock = PipelinePanel(self.pipeline_manager, self)
        dock.setObjectName("pipelineDock")
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.pipeline_dock = dock

    def _create_runtime_dock(self) -> None:
        dock = RuntimePanel(self.runtime_inspector, self)
        dock.setObjectName("runtimeDock")
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._register_dock_action(dock)
        self.runtime_dock = dock

    def show_command_palette(self, preset: str | None = None) -> None:
        self._register_core_commands()
        if preset:
            self.command_palette.open_with_query(preset)
        else:
            self.command_palette.open_palette()

    def _toggle_autoflow_mode(self) -> None:
        new_mode = "active" if self.command_palette.autoflow_mode == "passive" else "passive"
        self.command_palette.set_autoflow_mode(new_mode)
        self.navigation_assistant.autoflow_enabled = new_mode == "active"
        self.status.show_message(f"Autoflow mode: {new_mode}")

    def open_file(self, path: str) -> None:
        editor = self.editor_tabs.add_editor_for_file(Path(path))
        self.status.show_path(path)
        self.workspace_manager.register_recent(path)
        workspace = self.workspace_manager.current_workspace
        if workspace:
            workspace_str = str(workspace)
            files = self._recent_files_by_workspace.get(workspace_str, [])
            files = [p for p in files if p != path]
            files.insert(0, path)
            self._recent_files_by_workspace[workspace_str] = files[:5]
        self.status.update_git(str(workspace) if workspace else None)
        logger.info("Opened file: %s", path)
        self.plugin_loader.emit_event("file.opened", path=path)
        self.semantic_index.reindex([path])
        if hasattr(self, "doc_dock"):
            self.doc_dock.set_current_file(Path(path))

    def _open_graph_location(self, path: str, line: int | None) -> None:
        if line is None:
            self.open_file(path)
            return
        self.open_file_at(path, line)

    def open_folder(self, folder: str) -> None:
        self.workspace_manager.open_workspace(folder)
        workspace_path = self.workspace_manager.current_workspace
        workspace_str = str(workspace_path) if workspace_path else None
        self.status.update_git(workspace_str)
        self.status.show_message(f"Opened workspace: {folder}")
        index = self.project_model.set_workspace_root(workspace_str)
        if index:
            self.project_view.setRootIndex(index)
        self._update_workspace_state()
        if hasattr(self, "terminal"):
            self.terminal.set_workspace(workspace_path)
        self.plugin_loader.emit_event("workspace.opened", path=folder)
        self.task_manager.load_workspace_tasks()
        self.semantic_index.reindex()
        self._update_central_stack()

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

    def get_current_editor(self) -> CodeEditor | None:
        return self.editor_tabs.current_editor()

    def _with_editor(self, func) -> None:
        editor = self.get_current_editor()
        if editor:
            func(editor)

    def register_dock(self, identifier: str, widget: QDockWidget) -> None:
        widget.setObjectName(identifier)
        self.addDockWidget(Qt.RightDockWidgetArea, widget)
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

    def _prompt_open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder:
            self.open_folder(folder)

    def _close_folder(self) -> None:
        self.workspace_manager.clear_workspace()
        if hasattr(self, "project_model"):
            self.project_model.set_workspace_root(None)
        self._update_workspace_state()
        if hasattr(self, "terminal"):
            self.terminal.set_workspace(None)
        self._update_central_stack()

    def open_file_at(self, path: str, line: int) -> None:
        self.open_file(path)
        editor = self.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.MoveAnchor, line)
            editor.setTextCursor(cursor)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.workspace_manager.save_recents()
        window_cfg = self.config.settings.setdefault("window", {})
        window_cfg["maximized"] = self.isMaximized()
        geometry = self.saveGeometry()
        if isinstance(geometry, QByteArray):
            window_cfg["geometry"] = bytes(geometry.toHex()).decode("ascii")
        self.config.save()
        super().closeEvent(event)

    # Command registration
    def _register_core_commands(self) -> None:
        registry = self.command_registry
        registry.register_command(Command("file.open", "Open File", "File", self._prompt_open_file))
        registry.register_command(Command("file.save_all", "Save All", "File", self.save_all))
        registry.register_command(Command("view.toggle_project", "Toggle Project", "View", self._toggle_project))
        registry.register_command(Command("view.toggle_terminal", "Toggle Terminal", "View", self._toggle_terminal))
        registry.register_command(Command("ai.explain_selection", "Explain Selection", "AI", lambda: self._run_ai_command(explain_selection)))
        registry.register_command(Command("ai.refactor_selection", "Refactor Selection", "AI", lambda: self._run_ai_command(refactor_selection)))
        registry.register_command(Command("ai.toggle_autoflow", "Toggle Autoflow", "AI", self._toggle_autoflow_mode))
        registry.register_command(Command("ai.settings", "AI Settings", "AI", self._open_ai_settings))
        registry.register_command(Command("ai.setup", "Re-run Setup Wizard", "AI", self.show_setup_wizard))
        registry.register_command(Command("search.global", "Global Search", "Navigate", self._open_global_search))
        registry.register_command(Command("navigate.symbol", "Go to Symbol", "Navigate", self._open_symbol_picker))
        registry.register_command(Command("navigate.file", "Go to File", "Navigate", self._open_file_picker))
        registry.register_command(Command("workflow.run", "Run Pipelines", "Automation", self._run_all_pipelines))
        registry.register_command(Command("tasks.run", "Run Task", "Tasks", self._run_task_command))
        registry.register_command(Command("plugins.manage", "Plugin Manager", "Plugins", self._open_plugin_manager))
        registry.register_command(Command("lsp.restart", "Restart Language Server", "LSP", self._restart_language_server))

    def _toggle_project(self) -> None:
        visible = not self.project_dock.isVisible()
        self.project_dock.setVisible(visible)

    def _toggle_terminal(self) -> None:
        visible = not self.terminal_dock.isVisible()
        self.terminal_dock.setVisible(visible)

    def _toggle_architecture_map(self) -> None:
        dock = getattr(self, "architecture_dock", None)
        if not dock:
            return
        dock.setVisible(not dock.isVisible())

    def _refresh_architecture_graph(self) -> None:
        dock = getattr(self, "architecture_dock", None)
        if not dock:
            return
        dock.set_graph(self.semantic_index.get_graph_snapshot())

    def _on_semantic_graph_changed(self, _path: Path) -> None:
        QTimer.singleShot(0, self._refresh_architecture_graph)

    def _open_settings(self) -> None:
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

    def _open_global_search(self) -> None:
        if not hasattr(self, "_global_search_dialog"):
            self._global_search_dialog = GlobalSearchDialog(
                lambda: str(self.workspace_manager.current_workspace) if self.workspace_manager.current_workspace else None,
                lambda path, line: self.open_file_at(path, line),
                self,
            )
        self._global_search_dialog.show()

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

    def _focus_ai_dock(self) -> None:
        dock = getattr(self, "ai_dock", None)
        if dock:
            dock.show()
            dock.raise_()

    def _handle_diagnostics(self, diagnostics) -> None:
        self.diagnostics_model.set_diagnostics(diagnostics)
        if hasattr(self, "diagnostics_empty"):
            has_items = bool(diagnostics)
            self.diagnostics_empty.setVisible(not has_items)
            self.diagnostics_view.setVisible(has_items)
        for editor in self.editor_tabs.iter_editors():
            file_diags = [d for d in diagnostics if d.file == str(editor.path)]
            editor.apply_diagnostics(file_diags)
        self.analysis_service.on_diagnostics([diag.__dict__ for diag in diagnostics])

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

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "About Ghostline Studio",
            "Ghostline Studio\nA code understanding environment with AI assistance.",
        )
