"""Lightweight minimap preview for the code editor."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QPlainTextEdit, QWidget

MINIMAP_ENABLED = False


class MiniMap(QWidget):
    """A cached, scaled preview of the code editor's document."""

    SCALE = 0.12

    def __init__(self, editor: QPlainTextEdit) -> None:
        super().__init__(editor)
        self.editor = editor
        self.setObjectName("MiniMap")
        self.setMouseTracking(True)
        initial_width = max(40, int(self.editor.viewport().width() * self.SCALE))
        self.setFixedWidth(initial_width)
        self._cache: QPixmap | None = None
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(50)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_cache)
        self._content_height = 0.0

        if MINIMAP_ENABLED:
            self.editor.textChanged.connect(self.queue_render)
            self.editor.updateRequest.connect(lambda *_: self.queue_render())
            self.editor.verticalScrollBar().valueChanged.connect(lambda *_: self.update())

        if MINIMAP_ENABLED:
            self.queue_render()

    def queue_render(self) -> None:
        if not MINIMAP_ENABLED:
            return
        self._render_timer.start()

    def _render_cache(self) -> None:
        if not MINIMAP_ENABLED:
            return
        document = self.editor.document()
        layout = document.documentLayout()
        size = layout.documentSize().toSize()
        if size.isEmpty():
            self._cache = None
            self._content_height = 0.0
            self.update()
            return

        scaled_width = max(40, int(self.editor.viewport().width() * self.SCALE))
        scaled_height = max(1, int(size.height() * self.SCALE))
        image = QImage(scaled_width, scaled_height, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        painter = QPainter(image)
        painter.scale(self.SCALE, self.SCALE)
        document.drawContents(painter, QRectF(QPointF(0, 0), size))
        painter.end()

        self._cache = QPixmap.fromImage(image)
        self._content_height = scaled_height
        self.setFixedWidth(scaled_width)
        update_margins = getattr(self.editor, "minimap_resized", None)
        if callable(update_margins):
            update_margins()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not MINIMAP_ENABLED:
            return
        painter = QPainter(self)
        if self._cache:
            painter.drawPixmap(0, 0, self._cache)
        self._draw_viewport_marker(painter)
        painter.end()

    def _draw_viewport_marker(self, painter: QPainter) -> None:
        if not MINIMAP_ENABLED:
            return
        if self._content_height <= 0:
            return
        scrollbar = self.editor.verticalScrollBar()
        maximum = max(1, scrollbar.maximum())
        ratio = scrollbar.value() / maximum
        viewport_height = self.editor.viewport().height() * self.SCALE
        marker_height = max(12.0, viewport_height)
        y = ratio * max(1.0, self._content_height - marker_height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.black)
        painter.setOpacity(0.15)
        painter.drawRect(0, y, self.width(), marker_height)
        painter.setOpacity(0.35)
        painter.setBrush(Qt.white)
        painter.drawRect(0, y, self.width(), 2)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if not MINIMAP_ENABLED:
            return
        self._jump_to(event.position().y())

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if not MINIMAP_ENABLED:
            return
        if event.buttons() & Qt.LeftButton:
            self._jump_to(event.position().y())

    def _jump_to(self, y: float) -> None:
        if not MINIMAP_ENABLED:
            return
        if self._content_height <= 0:
            return
        scrollbar = self.editor.verticalScrollBar()
        maximum = max(1, scrollbar.maximum())
        target_ratio = y / max(1.0, self.height())
        scrollbar.setValue(int(target_ratio * maximum))
