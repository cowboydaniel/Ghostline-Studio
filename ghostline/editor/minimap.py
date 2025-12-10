"""Minimap widget that renders a tiny version of the editor contents with
syntax colors, like Windsurf / VS Code.

The key difference from earlier attempts:
We SCALE ONLY BY HEIGHT. Width is clipped. This keeps text visible.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QAbstractTextDocumentLayout, QColor
from PySide6.QtWidgets import QWidget, QPlainTextEdit


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
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        rect = self.rect()

        painter.fillRect(rect, self.palette().base())
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, False)

        doc = self.editor.document()
        layout: QAbstractTextDocumentLayout | None = doc.documentLayout()
        if not layout or rect.width() <= 0 or rect.height() <= 0:
            return

        doc_size = layout.documentSize()
        doc_h = max(1.0, doc_size.height())
        doc_w = max(1.0, doc_size.width())
        self._content_height = int(doc_h)

        # --------------------------------------------------------------
        # The important fix:
        # SCALE ONLY BY HEIGHT. Width is clipped naturally.
        # --------------------------------------------------------------
        scale = rect.height() / doc_h

        painter.save()
        painter.translate(rect.left(), rect.top())
        painter.scale(scale, scale)

        # Draw the full document (syntax-highlighted)
        ctx = QAbstractTextDocumentLayout.PaintContext()
        layout.draw(painter, ctx)

        painter.restore()

        # ------------------------------------------------------------------
        # Viewport highlight
        # ------------------------------------------------------------------
        vsb = self.editor.verticalScrollBar()
        viewport = self.editor.viewport()

        if self._content_height <= 0:
            return

        content_h = float(self._content_height)
        view_h = float(viewport.height())

        top_doc = float(vsb.value())
        height_doc = view_h

        scale_y = rect.height() / content_h

        top = int(top_doc * scale_y)
        height = max(3, int(height_doc * scale_y))

        if top + height > rect.height():
            height = rect.height() - top

        highlight = self.palette().highlight().color()
        fill = QColor(highlight)
        fill.setAlpha(60)

        painter.setPen(highlight)
        painter.setBrush(fill)
        painter.drawRect(rect.left(), rect.top() + top, rect.width() - 1, height)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._jump_to(event.position().y())

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.buttons() & Qt.LeftButton:
            self._jump_to(event.position().y())

    def _jump_to(self, y: float) -> None:
        if self._content_height <= 0:
            return
        scrollbar = self.editor.verticalScrollBar()
        maximum = max(1, scrollbar.maximum())
        ratio = y / max(1.0, self.height())
        scrollbar.setValue(int(ratio * maximum))
