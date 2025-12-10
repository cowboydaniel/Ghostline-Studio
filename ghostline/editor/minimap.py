"""Text-based minimap for Ghostline, Windsurf-style.

This minimap renders real, shrunken text for each line using a small font,
with per-line syntax colouring and a translucent viewport rectangle.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFontMetricsF, QPainter
from PySide6.QtWidgets import QPlainTextEdit, QWidget


class MiniMap(QWidget):
    def __init__(self, editor: QPlainTextEdit) -> None:
        super().__init__(editor)
        self.editor = editor
        self._content_height = 1

        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        doc = self.editor.document()
        doc.contentsChanged.connect(self.update)
        self.editor.verticalScrollBar().valueChanged.connect(self.update)
        self.editor.updateRequest.connect(self.update)

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # type: ignore[override]
        fm = self.editor.fontMetrics()
        width = fm.horizontalAdvance("0" * 12)
        height = self.editor.viewport().height()
        return QSize(width, height)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _line_color(self, block) -> QColor:
        """Pick a representative syntax colour for this line."""
        layout = block.layout()
        if layout is None:
            c = QColor(self.palette().mid().color())
            c.setAlpha(140)
            return c

        formats = layout.formats()
        if not formats:
            c = QColor(self.palette().mid().color())
            c.setAlpha(140)
            return c

        best = max(formats, key=lambda f: f.length)
        fg = best.format.foreground().color()
        if not fg.isValid():
            fg = QColor(self.palette().mid().color())

        fg = QColor(fg)
        fg.setAlpha(190)
        return fg

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        rect = self.rect()

        painter.fillRect(rect, self.palette().base())
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, False)

        doc = self.editor.document()
        block = doc.firstBlock()
        line_count = max(1, doc.blockCount())

        # Compute per-line height in minimap space
        line_height_px = rect.height() / float(line_count)
        self._content_height = int(line_height_px * line_count)

        # Choose a tiny font that roughly fits that line height
        base_font = self.editor.font()
        base_fm = QFontMetricsF(base_font)
        base_height = max(1.0, base_fm.height())
        scale = line_height_px / base_height

        tiny_font = base_font
        tiny_font.setPointSizeF(max(3.0, base_font.pointSizeF() * scale))
        tiny_fm = QFontMetricsF(tiny_font)
        painter.setFont(tiny_font)

        # Draw one line of tiny text per block
        y_line = 0
        while block.isValid():
            text = block.text()
            color = self._line_color(block)

            top = rect.top() + int(y_line * line_height_px)
            baseline = top + int(tiny_fm.ascent())

            # Elide to fit minimap width
            if rect.width() > 2:
                elided = tiny_fm.elidedText(text, Qt.ElideRight, rect.width() - 2)
            else:
                elided = ""

            painter.setPen(color)
            painter.drawText(rect.left() + 1, baseline, elided)

            y_line += 1
            block = block.next()

        # ------------------------------------------------------------------
        # Viewport highlight
        # ------------------------------------------------------------------
        vsb = self.editor.verticalScrollBar()
        maximum = vsb.maximum()
        if maximum >= 0:
            viewport = self.editor.viewport()
            visible_px = viewport.height()

            # Convert scrollbar value into line index range
            # Approximate by using ratio of scroll range.
            scroll_ratio = vsb.value() / max(1.0, float(maximum))
            visible_lines = visible_px / max(1.0, base_height)

            top_line = scroll_ratio * (line_count - visible_lines)
            top_line = max(0.0, min(float(line_count - 1), top_line))

            top = rect.top() + int(top_line * line_height_px)
            height = max(3, int(visible_lines * line_height_px))

            if top + height > rect.height():
                height = rect.height() - top

            highlight = self.palette().highlight().color()
            fill = QColor(highlight)
            fill.setAlpha(60)

            painter.setPen(highlight)
            painter.setBrush(fill)
            painter.drawRect(rect.left(), top, rect.width() - 1, height)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._jump_to(event.position().y())

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.buttons() & Qt.LeftButton:
            self._jump_to(event.position().y())

    def _jump_to(self, y: float) -> None:
        scrollbar = self.editor.verticalScrollBar()
        maximum = max(1, scrollbar.maximum())
        ratio = y / max(1.0, self.height())
        scrollbar.setValue(int(ratio * maximum))
