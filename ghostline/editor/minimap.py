"""Minimap widget that renders a tiny version of the editor contents."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QAbstractTextDocumentLayout, QColor
from PySide6.QtWidgets import QWidget, QPlainTextEdit


class MiniMap(QWidget):
    """A Windsurf-style minimap with scaled text and syntax colours."""

    def __init__(self, editor: QPlainTextEdit) -> None:
        super().__init__(editor)
        self.editor = editor
        self._content_height: int = 1

        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        doc = self.editor.document()
        doc.contentsChanged.connect(self._on_editor_changed)
        self.editor.verticalScrollBar().valueChanged.connect(self._on_editor_changed)
        self.editor.updateRequest.connect(self._on_editor_changed)

    # ------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------
    def sizeHint(self) -> QSize:  # type: ignore[override]
        fm = self.editor.fontMetrics()
        # Narrow enough to be a sidebar, wide enough to show tiny text.
        width = fm.horizontalAdvance("0" * 10)
        height = self.editor.viewport().height()
        return QSize(width, height)

    # ------------------------------------------------------------
    # Update triggers
    # ------------------------------------------------------------
    def _on_editor_changed(self, *args) -> None:
        self.update()

    # ------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        rect = self.rect()

        painter.fillRect(rect, self.palette().base())

        doc = self.editor.document()
        layout: QAbstractTextDocumentLayout | None = doc.documentLayout()
        if layout is None or rect.width() <= 0 or rect.height() <= 0:
            return

        doc_size = layout.documentSize()
        doc_w = max(1.0, doc_size.width())
        doc_h = max(1.0, doc_size.height())
        self._content_height = int(doc_h)

        # Compute scale so the full document fits inside the minimap.
        scale_x = rect.width() / doc_w
        scale_y = rect.height() / doc_h
        scale = min(scale_x, scale_y)

        painter.save()
        painter.translate(rect.left(), rect.top())
        painter.scale(scale, scale)

        ctx = QAbstractTextDocumentLayout.PaintContext()
        layout.draw(painter, ctx)

        painter.restore()

        # --------------------------------------------------------
        # Viewport highlight (drawn in minimap coordinates)
        # --------------------------------------------------------
        vsb = self.editor.verticalScrollBar()
        viewport = self.editor.viewport()

        if self._content_height <= 0:
            return

        # Scrollbar value is in document pixels (content_height - viewport_height)
        content_height = float(self._content_height)
        visible_height = float(viewport.height())

        # Map document coords to minimap coords
        scale_y_minimap = rect.height() / content_height

        top_doc = float(vsb.value())
        height_doc = visible_height

        top = int(top_doc * scale_y_minimap)
        height = max(3, int(height_doc * scale_y_minimap))

        if top + height > rect.height():
            height = rect.height() - top

        highlight = self.palette().highlight().color()
        fill = QColor(highlight)
        fill.setAlpha(60)

        painter.save()
        painter.setPen(highlight)
        painter.setBrush(fill)
        painter.drawRect(rect.left(), rect.top() + top, rect.width() - 1, height)
        painter.restore()

    # ------------------------------------------------------------
    # Interaction (click + drag to scroll)
    # ------------------------------------------------------------
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
