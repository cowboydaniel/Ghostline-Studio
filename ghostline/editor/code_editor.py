"""Minimal code editor widget."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit


class CodeEditor(QPlainTextEdit):
    def __init__(self, path: Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        self.setFont(QFont("JetBrains Mono", 11))
        self.cursorPositionChanged.connect(self._highlight_current_line)
        if path and path.exists():
            self._load_file(path)

    def _load_file(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as handle:
            self.setPlainText(handle.read())

    def save(self) -> None:
        if not self.path:
            return
        with self.path.open("w", encoding="utf-8") as handle:
            handle.write(self.toPlainText())

    def _highlight_current_line(self) -> None:
        extra_selections = []
        if not self.isReadOnly():
            selection = QPlainTextEdit.ExtraSelection()
            line_color = QColor(60, 65, 70)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)
