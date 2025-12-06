"""Editor tab widget."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QTabWidget

from ghostline.core.config import ConfigManager
from ghostline.core.events import CommandRegistry
from ghostline.core.resources import load_icon
from ghostline.core.theme import ThemeManager
from ghostline.editor.code_editor import CodeEditor
from ghostline.lang.lsp_manager import LSPManager
from ghostline.ai.ai_client import AIClient
from ghostline.ui.editor import EditorWidget


class EditorTabs(QTabWidget):
    countChanged = Signal(int)

    def __init__(
        self,
        parent=None,
        *,
        config: ConfigManager | None = None,
        theme: ThemeManager | None = None,
        lsp_manager: LSPManager | None = None,
        ai_client: AIClient | None = None,
        command_registry: CommandRegistry | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.theme = theme
        self.lsp_manager = lsp_manager
        self.ai_client = ai_client
        self.command_registry = command_registry
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)

    def add_editor_for_file(self, path: Path) -> CodeEditor:
        editor = EditorWidget(
            path,
            config=self.config,
            theme=self.theme,
            lsp_manager=self.lsp_manager,
            ai_client=self.ai_client,
            command_registry=self.command_registry,
        )
        icon = self._icon_for_file(path)
        self.addTab(editor, icon, path.name)
        self.setCurrentWidget(editor)
        self.countChanged.emit(self.count())
        return editor.editor

    def _icon_for_file(self, path: Path) -> QIcon:
        suffix = path.suffix.lower()
        if suffix in {".py"}:
            return load_icon("file_python.svg", fallback="file_generic.svg")
        if suffix in {".json"}:
            return load_icon("file_json.svg", fallback="file_generic.svg")
        return load_icon("file_generic.svg")

    def _close_tab(self, index: int) -> None:
        widget = self.widget(index)
        if widget:
            widget.deleteLater()
        self.removeTab(index)
        self.countChanged.emit(self.count())

    def iter_editors(self) -> Iterator[CodeEditor]:
        for index in range(self.count()):
            editor = self.widget(index)
            if isinstance(editor, EditorWidget):
                yield editor.editor
            elif isinstance(editor, CodeEditor):
                yield editor

    def current_editor(self) -> CodeEditor | None:
        widget = self.currentWidget()
        if isinstance(widget, EditorWidget):
            return widget.editor
        if isinstance(widget, CodeEditor):
            return widget
        return None
