"""Inline completion renderer for the editor."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QKeyEvent

from ghostline.ai.ai_client import AIClient
from ghostline.core.config import ConfigManager


class InlineCompletionController(QObject):
    def __init__(self, editor, config: ConfigManager | None, client: AIClient | None = None) -> None:
        super().__init__(editor)
        self.editor = editor
        self.config = config
        self.client = client or (AIClient(config) if config else None)
        self.ghost_text = ""
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        interval = (config.get("ai", {}).get("inline_delay_ms", 600) if config else 600)
        self.timer.setInterval(interval)
        self.timer.timeout.connect(self._request_completion)
        self.editor.textChanged.connect(self._arm_timer)

    def _arm_timer(self) -> None:
        self.ghost_text = ""
        self.editor.viewport().update()
        if self.config and not self.config.get("ai", {}).get("enabled", False):
            return
        self.timer.start()

    def _request_completion(self) -> None:
        if not self.client:
            return
        cursor = self.editor.textCursor()
        prefix = self.editor.toPlainText()[: cursor.position()]
        prompt = prefix[-500:]
        stream = self.client.stream(f"Continue code:\n{prompt}")
        try:
            first_chunk = next(iter(stream))
        except StopIteration:
            return
        self.ghost_text = first_chunk.strip().split("\n")[0]
        self.editor.viewport().update()

    def handle_key(self, event: QKeyEvent) -> bool:
        if self.ghost_text:
            if event.key() == Qt.Key_Tab:
                self.editor.insertPlainText(self.ghost_text)
                self.ghost_text = ""
                return True
            if event.key() == Qt.Key_Escape:
                self.ghost_text = ""
                self.editor.viewport().update()
                return False
        return False

    def paint_hint(self) -> None:
        if not self.ghost_text:
            return
        painter = QPainter(self.editor.viewport())
        painter.setPen(QColor(150, 150, 150, 160))
        rect = self.editor.cursorRect()
        painter.drawText(rect.topLeft(), self.ghost_text)
