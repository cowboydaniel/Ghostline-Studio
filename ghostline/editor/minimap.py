"""Windsurf-style minimap for Ghostline.

This implementation draws thin color-coded bars per line and overlays a
viewport rectangle. It is lightweight, always visible, and avoids the
blank/minimap-less rendering issue.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget, QPlainTextEdit


class MiniMap(QWidget):
    def __init__(self, editor: QPlainTextEdit) -> None:
        super().__init__(editor)
        self.editor = editor
        self._content_height = 1

        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        # Update when document or scrollbar changes
        doc = self.editor.document()
        doc.contentsChanged.connect(self.update)
        self.editor.verticalScrollBar().valueChanged.connect(self.update)
        self.editor.updateRequest.connect(self.update)

    # ------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------
    def sizeHint(self) -> QSize:  # type: ignore[override]
        fm = self.editor.fontMetrics()
        width = fm.horizontalAdvance("0" * 6)
        height = self.editor.viewport().height()
        return QSize(width, height)

    # ------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        rect = self.rect()

        # Background
        painter.fillRect(rect, self.palette().base())

        doc = self.editor.document()
        block = doc.firstBlock()

        fm = self.editor.fontMetrics()
        line_height = max(1, fm.height())
        line_count = max(1, doc.blockCount())
        self._content_height = line_count * line_height

        if rect.height() <= 0:
            return

        scale = rect.height() / float(self._content_height)
        width = rect.width()

        # Colors
        base = self.palette().base().color()
        mid = self.palette().mid().color()
        midlight = self.palette().midlight().color()
        alt = self.palette().alternateBase().color()

        def tint(c: QColor, a: int) -> QColor:
            c = QColor(c)
            c.setAlpha(a)
            return c

        text_color = tint(mid, 160)
        comment_color = tint(midlight, 150)
        string_color = tint(alt, 150)
        empty_color = tint(base.lighter(115), 110)

        # Render line bars
        y_px = 0
        while block.isValid():
            text = block.text().lstrip()

            if not text:
                color = empty_color
            elif text.startswith("#"):
                color = comment_color
            elif text.startswith(("'", '"', "'''", '"""')):
                color = string_color
            else:
                color = text_color

            top = int(y_px * scale)
            h = max(1, int(line_height * scale))
            painter.fillRect(0, top, width, h, color)

            y_px += line_height
            block = block.next()

        # ------------------------------------------------------------
        # Viewport highlight
        # ------------------------------------------------------------
        vsb = self.editor.verticalScrollBar()
        maximum = vsb.maximum()

        if maximum > 0:
            viewport_pixel_height = self.editor.viewport().height()
            viewport_lines = max(1, viewport_pixel_height / line_height)

            viewport_start_px = (vsb.value() / maximum) * self._content_height
            viewport_height_px = viewport_lines * line_height

            top = int(viewport_start_px * scale)
            h = max(3, int(viewport_height_px * scale))

            if top + h > rect.height():
                h = rect.height() - top

            highlight = self.palette().highlight().color()
            fill = QColor(highlight)
            fill.setAlpha(60)

            painter.setPen(highlight)
            painter.setBrush(fill)
            painter.drawRect(0, top, width - 1, h)

    # ------------------------------------------------------------
    # Interaction (click + drag scrolling)
    # ------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._jump(event.position().y())

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.buttons() & Qt.LeftButton:
            self._jump(event.position().y())

    def _jump(self, y: float) -> None:
        if self._content_height <= 0:
            return

        scrollbar = self.editor.verticalScrollBar()
        maximum = max(1, scrollbar.maximum())
        ratio = y / max(1.0, self.height())
        scrollbar.setValue(int(ratio * maximum))
