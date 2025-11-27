"""Main window for Ghostline Studio."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
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
from ghostline.ui.command_palette import CommandPalette
from ghostline.ui.status_bar import StudioStatusBar
from ghostline.ui.layout_manager import LayoutManager
from ghostline.ui.tabs import EditorTabs
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
        super().__init__()
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

        self.setWindowTitle("Ghostline Studio")
        self.resize(1200, 800)

        self.editor_tabs = EditorTabs(
            self, config=self.config, theme=self.theme, lsp_manager=self.lsp_manager, ai_client=self.ai_client
        )
        self.setCentralWidget(self.editor_tabs)

        self.status = StudioStatusBar(self.git)
        self.setStatusBar(self.status)
        self.analysis_service.suggestions_changed.connect(lambda items: self.status.set_ai_suggestions_available(bool(items)))

        self.command_palette = CommandPalette(self)
        self.command_palette.set_registry(self.command_registry)
        self.command_palette.set_navigation_assistant(self.navigation_assistant)
        self.command_palette.set_autoflow_mode("passive")
        self._create_actions()
        self._create_menus()
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

    def _create_actions(self) -> None:
        self.action_open_file = QAction("Open File", self)
        self.action_open_file.triggered.connect(self._prompt_open_file)

        self.action_open_folder = QAction("Open Folder", self)
        self.action_open_folder.triggered.connect(self._prompt_open_folder)

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

        self.action_ai_explain = QAction("Explain Selection", self)
        self.action_ai_explain.triggered.connect(lambda: self._run_ai_command(explain_selection))

        self.action_ai_refactor = QAction("Refactor Selection", self)
        self.action_ai_refactor.triggered.connect(lambda: self._run_ai_command(refactor_selection))

        self.action_ai_code_actions = QAction("AI Code Actions...", self)
        self.action_ai_code_actions.triggered.connect(lambda: self._run_ai_command(ai_code_actions))

        self.action_open_plugins = QAction("Plugins", self)
        self.action_open_plugins.triggered.connect(self._open_plugin_manager)

        self.action_run_task = QAction("Run Task...", self)
        self.action_run_task.setShortcut("Ctrl+Shift+R")
        self.action_run_task.triggered.connect(self._run_task_command)

        self.action_restart_language = QAction("Restart Language Server", self)
        self.action_restart_language.triggered.connect(self._restart_language_server)

        self.action_format_document = QAction("Format Document", self)
        self.action_format_document.triggered.connect(self._format_current_document)

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.action_open_file)
        file_menu.addAction(self.action_open_folder)
        file_menu.addAction(self.action_settings)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.action_command_palette)
        view_menu.addAction(self.action_toggle_project)
        view_menu.addAction(self.action_toggle_terminal)
        view_menu.addAction(self.action_global_search)
        view_menu.addAction(self.action_goto_symbol)
        view_menu.addAction(self.action_goto_file)
        view_menu.addAction(self.action_toggle_architecture_map)
        view_menu.addAction(self.action_restart_language)

        ai_menu = self.menuBar().addMenu("AI")
        ai_menu.addAction(self.action_ai_explain)
        ai_menu.addAction(self.action_ai_refactor)
        ai_menu.addAction(self.action_ai_code_actions)

        tools_menu = self.menuBar().addMenu("Tools")
        tools_menu.addAction(self.action_open_plugins)
        tools_menu.addAction(self.action_run_task)
        tools_menu.addAction(self.action_format_document)

    def _create_terminal_dock(self) -> None:
        dock = QDockWidget("Terminal", self)
        dock.setObjectName("terminalDock")
        dock.setWidget(TerminalWidget(self.workspace_manager))
        dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self.terminal_dock = dock

    def _create_project_dock(self) -> None:
        dock = QDockWidget("Project", self)
        dock.setObjectName("projectDock")
        self.project_model = ProjectModel(self)
        self.project_view = ProjectView(self)
        self.project_view.set_model(self.project_model)
        dock.setWidget(self.project_view)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.project_dock = dock

    def _create_ai_dock(self) -> None:
        dock = QDockWidget("Ghostline AI", self)
        dock.setObjectName("aiDock")
        panel = AIChatPanel(self.ai_client, self)
        panel.set_context_provider(lambda: self.get_current_editor().toPlainText() if self.get_current_editor() else "")
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.ai_dock = dock

    def _create_diagnostics_dock(self) -> None:
        dock = QDockWidget("Diagnostics", self)
        dock.setObjectName("diagnosticsDock")
        table = QTableView(self)
        self.diagnostics_model = DiagnosticsModel(self)
        table.setModel(self.diagnostics_model)
        table.doubleClicked.connect(self._jump_to_diagnostic)
        dock.setWidget(table)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self.diagnostics_view = table
        self.diagnostics_dock = dock

    def _create_debugger_dock(self) -> None:
        dock = QDockWidget("Debugger", self)
        dock.setObjectName("debuggerDock")
        panel = DebuggerPanel(self.debugger, self)
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.debugger_dock = dock

    def _create_task_dock(self) -> None:
        dock = QDockWidget("Tasks", self)
        dock.setObjectName("tasksDock")
        panel = TaskPanel(self.task_manager, self)
        dock.setWidget(panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self.task_dock = dock

    def _create_test_dock(self) -> None:
        dock = QDockWidget("Tests", self)
        dock.setObjectName("testsDock")
        panel = TestPanel(self.test_manager, self.get_current_editor, self)
        dock.setWidget(panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self.test_dock = dock

    def _create_architecture_dock(self) -> None:
        dock = ArchitectureDock(self)
        dock.setObjectName("architectureDock")
        dock.open_file_requested.connect(self._open_graph_location)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.architecture_dock = dock
        self._refresh_architecture_graph()

    def _create_build_dock(self) -> None:
        dock = BuildPanel(self.build_manager, self)
        dock.setObjectName("buildDock")
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self.build_dock = dock

    def _create_doc_dock(self) -> None:
        dock = DocPanel(self.doc_generator, self)
        dock.setObjectName("docDock")
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
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
        dock.setWidget(GitPanel(self.git_service, self))
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.git_dock = dock

    def _create_coverage_dock(self) -> None:
        dock = QDockWidget("Coverage", self)
        dock.setObjectName("coverageDock")
        dock.setWidget(CoveragePanel(self))
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.coverage_dock = dock

    def _create_collaboration_dock(self) -> None:
        dock = CollabPanel(self.crdt_engine, self.collab_transport, self)
        dock.setObjectName("collabDock")
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.collab_dock = dock

    def _create_agent_console_dock(self) -> None:
        dock = AgentConsole(self.agent_manager, self)
        dock.setObjectName("agentConsoleDock")
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.agent_console_dock = dock

    def _create_pipeline_dock(self) -> None:
        dock = PipelinePanel(self.pipeline_manager, self)
        dock.setObjectName("pipelineDock")
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.pipeline_dock = dock

    def _create_runtime_dock(self) -> None:
        dock = RuntimePanel(self.runtime_inspector, self)
        dock.setObjectName("runtimeDock")
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.runtime_dock = dock

    def show_command_palette(self) -> None:
        self._register_core_commands()
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
        self.status.update_git(self.workspace_manager.current_workspace)
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
        self.status.update_git(folder)
        self.status.show_message(f"Opened workspace: {folder}")
        index = self.project_model.set_workspace_root(folder)
        if index:
            self.project_view.setRootIndex(index)
        self.plugin_loader.emit_event("workspace.opened", path=folder)
        self.task_manager.load_workspace_tasks()
        self.semantic_index.reindex()

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
        super().closeEvent(event)

    # Command registration
    def _register_core_commands(self) -> None:
        self.command_registry.register_command(Command("file.open", "Open File", "File", self._prompt_open_file))
        self.command_registry.register_command(
            Command("file.save_all", "Save All", "File", self.save_all)
        )
        self.command_registry.register_command(
            Command("view.toggle_project", "Toggle Project", "View", self._toggle_project)
        )
        self.command_registry.register_command(
            Command("view.toggle_terminal", "Toggle Terminal", "View", self._toggle_terminal)
        )
        self.command_registry.register_command(
            Command("ai.explain_selection", "Explain Selection", "AI", lambda: self._run_ai_command(explain_selection))
        )
        self.command_registry.register_command(
            Command("ai.refactor_selection", "Refactor Selection", "AI", lambda: self._run_ai_command(refactor_selection))
        )
        self.command_registry.register_command(
            Command("ai.toggle_autoflow", "Toggle Autoflow", "AI", self._toggle_autoflow_mode)
        )
        self.command_registry.register_command(
            Command("search.global", "Global Search", "Navigate", self._open_global_search)
        )
        self.command_registry.register_command(
            Command("navigate.symbol", "Go to Symbol", "Navigate", self._open_symbol_picker)
        )
        self.command_registry.register_command(
            Command("workflow.run", "Run Pipelines", "Automation", self._run_all_pipelines)
        )
        self.command_registry.register_command(
            Command("navigate.file", "Go to File", "Navigate", self._open_file_picker)
        )
        self.command_registry.register_command(Command("tasks.run", "Run Task", "Tasks", self._run_task_command))
        self.command_registry.register_command(Command("plugins.manage", "Plugin Manager", "Plugins", self._open_plugin_manager))
        self.command_registry.register_command(
            Command("lsp.restart", "Restart Language Server", "LSP", self._restart_language_server)
        )

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
                self.theme.apply_theme(app)

    def _open_global_search(self) -> None:
        if not hasattr(self, "_global_search_dialog"):
            self._global_search_dialog = GlobalSearchDialog(
                lambda: self.workspace_manager.current_workspace,
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

    def _handle_diagnostics(self, diagnostics) -> None:
        self.diagnostics_model.set_diagnostics(diagnostics)
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
