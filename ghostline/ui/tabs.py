"""Editor tab widget."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from PySide6.QtWidgets import QTabWidget

from ghostline.editor.code_editor import CodeEditor


class EditorTabs(QTabWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)

    def add_editor_for_file(self, path: Path) -> CodeEditor:
        editor = CodeEditor(path)
        self.addTab(editor, path.name)
        self.setCurrentWidget(editor)
        return editor

    def _close_tab(self, index: int) -> None:
        widget = self.widget(index)
        if widget:
            widget.deleteLater()
        self.removeTab(index)

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
