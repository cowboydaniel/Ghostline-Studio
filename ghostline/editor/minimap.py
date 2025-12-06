"""Lightweight minimap preview for the code editor.

This version is intentionally simple and avoids any recursive signal
chains. It draws a very compact representation of every line in the
document and a highlighted rectangle for the visible viewport.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter
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
        self.editor.viewport().updateRequest.connect(self._on_editor_update)

    # Sizing
    def sizeHint(self) -> QSize:  # type: ignore[override]
        fm = self.editor.fontMetrics()
        # A narrow strip beside the editor.
        return fm.boundingRect("0" * 4).size()

    # Update triggers
    def _on_editor_changed(self, *args) -> None:
        self.update()

    def _on_editor_update(self, *args) -> None:
        self.update()

    # Painting
    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        rect = self.rect()

        painter.fillRect(rect, self.palette().base())

        doc = self.editor.document()
        block = doc.firstBlock()
        fm = self.editor.fontMetrics()
        line_height = max(1, fm.height())
        line_count = max(1, doc.blockCount())
        self._content_height = line_count * line_height

        # Map document pixel height to minimap height.
        scale = rect.height() / float(self._content_height)

        y = 0
        width = rect.width()
        mid_color = self.palette().mid().color()

        # Very simple representation: one thin bar per line.
        while block.isValid():
            painter.fillRect(
                0,
                int(y * scale),
                width,
                max(1, int(line_height * scale)),
                mid_color,
            )
            y += line_height
            block = block.next()

        # Draw viewport indicator.
        vsb = self.editor.verticalScrollBar()
        maximum = vsb.maximum()
        if maximum > 0:
            viewport_blocks = max(1, int(self.editor.viewport().height() / line_height))
            viewport_start_px = (vsb.value() / maximum) * self._content_height
            viewport_height_px = viewport_blocks * line_height

            top = int(viewport_start_px * scale)
            height = max(3, int(viewport_height_px * scale))

            pen = self.palette().highlight().color()
            painter.setPen(pen)
            painter.drawRect(0, top, width - 1, height)

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
