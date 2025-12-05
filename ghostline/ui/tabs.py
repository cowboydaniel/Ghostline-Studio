"""Editor tab widget."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QTabWidget

from ghostline.core.config import ConfigManager
from ghostline.core.theme import ThemeManager
from ghostline.editor.code_editor import CodeEditor
from ghostline.lang.lsp_manager import LSPManager
from ghostline.ai.ai_client import AIClient


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
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.theme = theme
        self.lsp_manager = lsp_manager
        self.ai_client = ai_client
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)

    def add_editor_for_file(self, path: Path) -> CodeEditor:
        editor = CodeEditor(
            path,
            config=self.config,
            theme=self.theme,
            lsp_manager=self.lsp_manager,
            ai_client=self.ai_client,
        )
        icon = self._icon_for_file(path)
        self.addTab(editor, icon, path.name)
        self.setCurrentWidget(editor)
        self.countChanged.emit(self.count())
        return editor

    def _icon_for_file(self, path: Path) -> QIcon:
        suffix = path.suffix.lower()
        if suffix in {".py"}:
            return QIcon(":/icons/file_python.svg")
        if suffix in {".json"}:
            return QIcon(":/icons/file_json.svg")
        return QIcon(":/icons/file_generic.svg")

    def _close_tab(self, index: int) -> None:
        widget = self.widget(index)
        if widget:
            widget.deleteLater()
        self.removeTab(index)
        self.countChanged.emit(self.count())

    def iter_editors(self) -> Iterator[CodeEditor]:
        for index in range(self.count()):
            editor = self.widget(index)
            if isinstance(editor, CodeEditor):
                yield editor

    def current_editor(self) -> CodeEditor | None:
        widget = self.currentWidget()
        if isinstance(widget, CodeEditor):
            return widget
        return None
