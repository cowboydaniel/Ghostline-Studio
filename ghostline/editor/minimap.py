"""Lightweight minimap preview for the code editor.

This version is intentionally simple and avoids any recursive signal
chains. It draws a very compact representation of every line in the
document and a highlighted rectangle for the visible viewport.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAbstractTextDocumentLayout, QPainter
from PySide6.QtWidgets import QPlainTextEdit, QWidget


class MiniMap(QWidget):
    """A small vertical overview of the document."""

    def __init__(self, editor: QPlainTextEdit) -> None:
        super().__init__(editor)
        self.editor = editor
        self._content_height: int = 1

        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        doc = self.editor.document()
        doc.contentsChanged.connect(self._on_editor_changed)
        self.editor.verticalScrollBar().valueChanged.connect(self._on_editor_changed)
        self.editor.updateRequest.connect(self._on_editor_update)

    # Sizing
    def sizeHint(self) -> QSize:  # type: ignore[override]
        fm = self.editor.fontMetrics()
        # Slightly wider strip so the tiny text is visible
        width = fm.horizontalAdvance("0" * 8)
        height = self.editor.viewport().height()
        return QSize(width, height)

    # Update triggers
    def _on_editor_changed(self, *args) -> None:
        self.update()

    def _on_editor_update(self, *args) -> None:
        self.update()

    # Painting
    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        rect = self.rect()

        # Background to match the editor
        painter.fillRect(rect, self.palette().base())
        painter.setRenderHint(QPainter.Antialiasing, False)

        doc = self.editor.document()
        layout = doc.documentLayout()
        if layout is None:
            return

        # Total document size in layout coordinates
        doc_size = layout.documentSize()
        doc_width = max(1.0, doc_size.width())
        doc_height = max(1.0, doc_size.height())
        self._content_height = int(doc_height)

        # Compute scale factors so the whole document fits inside the minimap rect
        if rect.width() <= 0 or rect.height() <= 0:
            return

        scale_x = rect.width() / doc_width
        scale_y = rect.height() / doc_height

        painter.save()
        painter.translate(rect.left(), rect.top())
        painter.scale(scale_x, scale_y)

        # Draw the full document with syntax highlighting into the minimap
        ctx = QAbstractTextDocumentLayout.PaintContext()
        layout.draw(painter, ctx)
        painter.restore()

        # Draw the viewport indicator on top, in minimap coordinates
        vsb = self.editor.verticalScrollBar()
        viewport = self.editor.viewport()

        if self._content_height <= 0:
            return

        # Map scroll position and viewport height into minimap space
        content_height = doc_height
        scale_y_minimap = rect.height() / content_height

        top = int(vsb.value() * scale_y_minimap)
        height = max(3, int(viewport.height() * scale_y_minimap))

        # Clamp into rect
        if top + height > rect.height():
            height = max(3, rect.height() - top)

        # Semi-transparent fill + border like other editors
        highlight_color = self.palette().highlight().color()
        fill_color = highlight_color
        fill_color.setAlpha(60)

        painter.save()
        painter.setPen(highlight_color)
        painter.setBrush(fill_color)
        painter.drawRect(rect.left(), rect.top() + top, rect.width() - 1, height)
        painter.restore()

    # Interaction
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
        target_ratio = y / max(1.0, self.height())
        scrollbar.setValue(int(target_ratio * maximum))
