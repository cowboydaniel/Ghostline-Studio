"""Dual-pane editor area with split view support."""
from __future__ import annotations

from itertools import chain
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from ghostline.core.config import ConfigManager
from ghostline.core.events import CommandRegistry
from ghostline.core.theme import ThemeManager
from ghostline.editor.code_editor import CodeEditor
from ghostline.lang.lsp_manager import LSPManager
from ghostline.ai.ai_client import AIClient
from ghostline.ui.tabs import EditorTabs


class SplitEditorArea(QWidget):
    """Wrap two EditorTabs instances to enable side-by-side editing."""

    countChanged = Signal(int)
    currentChanged = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        config: ConfigManager | None = None,
        theme: ThemeManager | None = None,
        lsp_manager: LSPManager | None = None,
        ai_client: AIClient | None = None,
        command_registry: CommandRegistry | None = None,
    ) -> None:
        super().__init__(parent)
        self.primary = EditorTabs(
            self,
            config=config,
            theme=theme,
            lsp_manager=lsp_manager,
            ai_client=ai_client,
            command_registry=command_registry,
        )
        self.secondary = EditorTabs(
            self,
            config=config,
            theme=theme,
            lsp_manager=lsp_manager,
            ai_client=ai_client,
            command_registry=command_registry,
        )
        self.secondary.hide()
        self._active_pane = "primary"

        self.primary.countChanged.connect(self._emit_count)
        self.secondary.countChanged.connect(self._emit_count)
        self.primary.currentChanged.connect(lambda index=None: self._handle_current_changed(index, "primary"))
        self.secondary.currentChanged.connect(lambda index=None: self._handle_current_changed(index, "secondary"))

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self.primary)
        splitter.addWidget(self.secondary)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(splitter)

    # Pane control -------------------------------------------------------
    def toggle_split(self) -> None:
        self.set_split_active(not self.secondary.isVisible())

    def set_split_active(self, active: bool) -> None:
        self.secondary.setVisible(active)
        self._set_active_pane("secondary" if active else "primary")
        self._emit_count()

    def add_editor_for_file(self, path: Path, *, preview: bool = False, target: str | None = None) -> CodeEditor:
        tabs = self.secondary if (target == "secondary" or (self.secondary.isVisible() and self._active_pane == "secondary")) else self.primary
        editor = tabs.add_editor_for_file(path, preview=preview)
        self._emit_count()
        return editor

    def iter_editors(self):
        return chain(self.primary.iter_editors(), self.secondary.iter_editors())

    def current_editor(self) -> CodeEditor | None:
        if self._active_pane == "secondary" and self.secondary.isVisible():
            return self.secondary.current_editor() or self.primary.current_editor()
        return self.primary.current_editor()

    def _active_tabs(self) -> EditorTabs:
        if self._active_pane == "secondary" and self.secondary.isVisible():
            return self.secondary
        return self.primary

    def focus_next_tab(self) -> None:
        tabs = self._active_tabs()
        count = tabs.count()
        if count == 0:
            return
        new_index = (tabs.currentIndex() + 1) % count
        tabs.setCurrentIndex(new_index)

    def focus_previous_tab(self) -> None:
        tabs = self._active_tabs()
        count = tabs.count()
        if count == 0:
            return
        new_index = (tabs.currentIndex() - 1) % count
        tabs.setCurrentIndex(new_index)

    def focus_pane(self, pane: str) -> None:
        if pane == "secondary" and not self.secondary.isVisible():
            self.secondary.show()
        self._set_active_pane(pane)
        target = self.secondary if pane == "secondary" else self.primary
        if target.count():
            target.setCurrentIndex(max(0, target.currentIndex()))
            target.setFocus()
        self._emit_count()

    def move_current_to_other(self) -> None:
        editor = self.current_editor()
        if not editor or not editor.path:
            return
        target = "secondary" if self._active_pane != "secondary" else "primary"
        moved = self.add_editor_for_file(editor.path, preview=False, target=target)
        if moved and moved is not editor:
            current_tabs = self._active_tabs()
            if isinstance(current_tabs, EditorTabs):
                index = current_tabs._find_tab_for_file(editor.path)
                if index is not None:
                    current_tabs._close_tab(index)
        self._set_active_pane(target)

    def count(self) -> int:
        total = self.primary.count()
        if self.secondary.isVisible():
            total += self.secondary.count()
        return total

    def get_session_state(self) -> dict:
        return {
            "primary": self.primary.get_session_state(),
            "secondary": self.secondary.get_session_state(),
            "secondary_visible": self.secondary.isVisible(),
            "active_pane": self._active_pane,
        }

    def split_active(self) -> bool:
        return self.secondary.isVisible()

    def restore_session_state(self, state: dict) -> None:
        self.primary.restore_session_state(state.get("primary", {}))
        self.secondary.restore_session_state(state.get("secondary", {}))
        if state.get("secondary_visible"):
            self.secondary.show()
        self._set_active_pane(state.get("active_pane", "primary"))
        self._emit_count()

    def _set_active_pane(self, pane: str) -> None:
        self._active_pane = pane if pane in {"primary", "secondary"} else "primary"

    def _handle_current_changed(self, index: int | None, pane: str) -> None:
        self._set_active_pane(pane)
        self.currentChanged.emit(index if index is not None else -1)

    def _emit_count(self) -> None:
        self.countChanged.emit(self.count())
