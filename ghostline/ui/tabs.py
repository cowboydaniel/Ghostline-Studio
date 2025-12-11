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
from ghostline.ui.editor.EditorWidget import EditorWidget
from ghostline.ui.tabbar import EditorTabBar


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
        self._preview_tabs: set[int] = set()
        self.setTabBar(EditorTabBar())
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)

    def add_editor_for_file(self, path: Path, *, preview: bool = False) -> CodeEditor:
        existing_index = self._find_tab_for_file(path)
        if existing_index is not None:
            if not preview and existing_index in self._preview_tabs:
                self._make_tab_permanent(existing_index)
            self.setCurrentIndex(existing_index)
            widget = self.widget(existing_index)
            if isinstance(widget, EditorWidget):
                return widget.editor
            elif isinstance(widget, CodeEditor):
                return widget
            return self.current_editor()

        if preview:
            self._close_preview_tab()

        editor = EditorWidget(
            path,
            config=self.config,
            theme=self.theme,
            lsp_manager=self.lsp_manager,
            ai_client=self.ai_client,
            command_registry=self.command_registry,
        )
        icon = self._icon_for_file(path)
        tab_index = self.addTab(editor, icon, path.name)

        if preview:
            self._preview_tabs.add(tab_index)
            self._update_tab_text(tab_index, path.name, preview=True)

            def make_permanent():
                self._make_tab_permanent(tab_index)
                editor.editor.textChanged.disconnect(make_permanent)

            editor.editor.textChanged.connect(make_permanent)

        self.setCurrentWidget(editor)
        self.countChanged.emit(self.count())
        return editor.editor

    def _find_tab_for_file(self, path: Path) -> int | None:
        for index in range(self.count()):
            widget = self.widget(index)
            if isinstance(widget, EditorWidget) and widget.editor.path == path:
                return index
            elif isinstance(widget, CodeEditor) and widget.path == path:
                return index
        return None

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
        self._preview_tabs.discard(index)
        self._preview_tabs = {i if i < index else i - 1 for i in self._preview_tabs}
        tab_bar = self.tabBar()
        if isinstance(tab_bar, EditorTabBar):
            for i in range(tab_bar.count() + 1):
                tab_bar.set_tab_preview(i, False)
            for preview_index in self._preview_tabs:
                tab_bar.set_tab_preview(preview_index, True)
        self.countChanged.emit(self.count())

    def _close_preview_tab(self) -> None:
        if self._preview_tabs:
            preview_index = next(iter(self._preview_tabs))
            self._close_tab(preview_index)

    def _make_tab_permanent(self, index: int) -> None:
        if index in self._preview_tabs:
            self._preview_tabs.discard(index)
            tab_bar = self.tabBar()
            if isinstance(tab_bar, EditorTabBar):
                tab_bar.set_tab_preview(index, False)
            widget = self.widget(index)
            if isinstance(widget, EditorWidget):
                self._update_tab_text(index, widget.editor.path.name if widget.editor.path else "Untitled", preview=False)

    def _update_tab_text(self, index: int, text: str, preview: bool) -> None:
        self.setTabText(index, text)
        tab_bar = self.tabBar()
        if isinstance(tab_bar, EditorTabBar):
            tab_bar.set_tab_preview(index, preview)

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

    def get_session_state(self) -> dict:
        tabs = []
        current_index = self.currentIndex()
        for index in range(self.count()):
            widget = self.widget(index)
            if isinstance(widget, EditorWidget) and widget.editor.path:
                editor_state = widget.editor.get_state()
                tabs.append({
                    "path": str(widget.editor.path),
                    "is_preview": index in self._preview_tabs,
                    "editor_state": editor_state,
                })
        return {"tabs": tabs, "current_index": current_index}

    def restore_session_state(self, state: dict) -> None:
        tabs = state.get("tabs", [])
        current_index = state.get("current_index", 0)

        for tab_info in tabs:
            try:
                path = Path(tab_info["path"])
                if path.exists():
                    is_preview = tab_info.get("is_preview", False)
                    editor = self.add_editor_for_file(path, preview=is_preview)
                    editor_state = tab_info.get("editor_state", {})
                    if editor_state:
                        editor.restore_state(editor_state)
            except Exception:
                pass

        if 0 <= current_index < self.count():
            self.setCurrentIndex(current_index)
