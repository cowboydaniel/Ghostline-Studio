"""Enhanced code editor widget with line numbers and LSP integration."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QPainter,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QSyntaxHighlighter,
    QTextDocument,
    QPalette,
)
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QToolTip

from ghostline.core.config import ConfigManager
from ghostline.core.theme import ThemeManager
from ghostline.lang.diagnostics import Diagnostic
from ghostline.lang.lsp_manager import LSPManager


class LineNumberArea(QWidget):
    """Side widget that paints line numbers."""

    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        self.code_editor._paint_line_numbers(event)


class PythonHighlighter(QSyntaxHighlighter):
    """Simple regex-based syntax highlighter for Python."""

    def __init__(self, document: QTextDocument, theme: ThemeManager | None) -> None:
        super().__init__(document)
        self.theme = theme
        self._init_rules()

    def _fmt(self, color_key: str, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(self.theme.syntax_color(color_key) if self.theme else QColor())
        if bold:
            fmt.setFontWeight(QFont.Bold)
        return fmt

    def _init_rules(self) -> None:
        import re

        self.rules: List[tuple[object, QTextCharFormat]] = []
        keywords = r"\b(" + "|".join(
            [
                "def",
                "class",
                "if",
                "elif",
                "else",
                "while",
                "for",
                "try",
                "except",
                "finally",
                "return",
                "import",
                "from",
                "as",
                "with",
                "pass",
                "yield",
                "lambda",
            ]
        ) + r")\b"
        self.rules.append((re.compile(keywords), self._fmt("keyword", True)))
        self.rules.append((re.compile(r"#[^\n]*"), self._fmt("comment")))
        self.rules.append((re.compile(r"\b[0-9]+\b"), self._fmt("number")))
        self.rules.append((re.compile(r"\bself\b"), self._fmt("builtin")))
        self.rules.append((re.compile(r"\bclass\s+\w+"), self._fmt("definition", True)))
        string_fmt = self._fmt("string")
        self.rules.append((re.compile(r"'(?:[^'\\]|\\.)*'"), string_fmt))
        self.rules.append((re.compile(r'"(?:[^"\\]|\\.)*"'), string_fmt))

    def highlightBlock(self, text: str) -> None:  # type: ignore[override]
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)


class CodeEditor(QPlainTextEdit):
    def __init__(
        self,
        path: Path | None = None,
        parent=None,
        *,
        config: ConfigManager | None = None,
        theme: ThemeManager | None = None,
        lsp_manager: LSPManager | None = None,
    ) -> None:
        super().__init__(parent)
        self.path = path
        self.config = config
        self.theme = theme
        self.lsp_manager = lsp_manager
        self._document_version = 0
        self._diagnostics: list[Diagnostic] = []

        font_family = self.config.get("font", {}).get("editor_family", "JetBrains Mono") if self.config else "JetBrains Mono"
        font_size = self.config.get("font", {}).get("editor_size", 11) if self.config else 11
        self.setFont(QFont(font_family, font_size))
        self.line_number_area = LineNumberArea(self)

        tab_size = self.config.get("tabs", {}).get("tab_size", 4) if self.config else 4
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" " * tab_size))

        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.textChanged.connect(self._notify_lsp_change)

        self._highlighter = PythonHighlighter(self.document(), self.theme)

        self._update_line_number_area_width(self.blockCount())
        if path and path.exists():
            self._load_file(path)
            self._open_in_lsp()

    # Line number plumbing
    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def _update_line_number_area_width(self, _=None) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def _paint_line_numbers(self, event) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.theme.color(QPalette.Base) if self.theme else QColor(40, 40, 40))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self.theme.color(QPalette.Text) if self.theme else QColor(180, 180, 180))
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    # File operations
    def _load_file(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as handle:
            self.setPlainText(handle.read())

    def save(self) -> None:
        if not self.path:
            return
        with self.path.open("w", encoding="utf-8") as handle:
            handle.write(self.toPlainText())

    # Indentation helpers
    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_K:
            self._request_hover()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            cursor.select(QTextCursor.LineUnderCursor)
            line_text = cursor.selectedText()
            indent = len(line_text) - len(line_text.lstrip())
            super().keyPressEvent(event)
            indent_str = " " * indent
            if self.config and not self.config.get("tabs", {}).get("use_spaces", True):
                tab_size = self.config.get("tabs", {}).get("tab_size", 4)
                indent_str = "\t" * max(1, indent // tab_size) if indent else ""
            self.insertPlainText(indent_str)
            return
        super().keyPressEvent(event)

    # Highlight current line and diagnostics
    def _highlight_current_line(self) -> None:
        extra_selections = []
        if not self.isReadOnly():
            selection = QPlainTextEdit.ExtraSelection()
            line_color = self.theme.color(QPalette.AlternateBase) if self.theme else QColor(60, 65, 70)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        extra_selections.extend(self._diagnostic_selections())
        self.setExtraSelections(extra_selections)

    def _diagnostic_selections(self) -> list[QPlainTextEdit.ExtraSelection]:
        selections: list[QPlainTextEdit.ExtraSelection] = []
        for diag in self._diagnostics:
            selection = QPlainTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setUnderlineColor(QColor(255, 99, 71))
            fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
            selection.format = fmt
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, diag.line)
            cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, diag.col)
            selection.cursor = cursor
            selections.append(selection)
        return selections

    # LSP integration
    def _open_in_lsp(self) -> None:
        if self.lsp_manager and self.path:
            self.lsp_manager.open_document(str(self.path), self.toPlainText())

    def _notify_lsp_change(self) -> None:
        if self.lsp_manager and self.path:
            self._document_version += 1
            self.lsp_manager.change_document(
                str(self.path), self.toPlainText(), version=self._document_version
            )

    def apply_diagnostics(self, diagnostics: Iterable[Diagnostic]) -> None:
        self._diagnostics = list(diagnostics)
        self._highlight_current_line()

    def _request_hover(self) -> None:
        if not (self.lsp_manager and self.path):
            return
        cursor = self.textCursor()
        position = {"line": cursor.blockNumber(), "character": cursor.columnNumber()}

        def _show_hover(message: dict) -> None:
            contents = message.get("result", {})
            value = ""
            if isinstance(contents, dict):
                value = contents.get("contents", "")
            elif isinstance(contents, str):
                value = contents
            if value:
                QToolTip.showText(self.mapToGlobal(self.cursorRect().bottomRight()), str(value))

        self.lsp_manager.request_hover(str(self.path), position, callback=_show_hover)
