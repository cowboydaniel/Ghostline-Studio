"""Lightweight minimap preview for the code editor."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPlainTextEdit


class MiniMap(QPlainTextEdit):
    """A shrunken, read-only mirror of the main editor."""

    def __init__(self, editor: QPlainTextEdit) -> None:
        super().__init__(editor)
        self.editor = editor
        self.setReadOnly(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setStyleSheet("font-size:8px; color: #888;")
        self.setFixedWidth(120)
        self._syncing = False
        self.hide()

        self.editor.textChanged.connect(self._sync_text)
        self.editor.verticalScrollBar().valueChanged.connect(self._sync_scroll_from_editor)
        self.verticalScrollBar().valueChanged.connect(self._sync_editor_from_minimap)
        self._sync_text()

    def _sync_text(self) -> None:
        self._syncing = True
        self.setPlainText(self.editor.toPlainText())
        self._syncing = False

    def _sync_scroll_from_editor(self, value: int) -> None:
        if self._syncing:
            return
        ratio = value / max(1, self.editor.verticalScrollBar().maximum())
        self.verticalScrollBar().setValue(int(ratio * max(1, self.verticalScrollBar().maximum())))

    def _sync_editor_from_minimap(self, value: int) -> None:
        if self._syncing:
            return
        ratio = value / max(1, self.verticalScrollBar().maximum())
        self.editor.verticalScrollBar().setValue(int(ratio * max(1, self.editor.verticalScrollBar().maximum())))

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        # Jump the main editor to the clicked position.
        ratio = event.position().y() / max(1, self.viewport().height())
        target = int(ratio * max(1, self.editor.verticalScrollBar().maximum()))
        self.editor.verticalScrollBar().setValue(target)
        super().mousePressEvent(event)
