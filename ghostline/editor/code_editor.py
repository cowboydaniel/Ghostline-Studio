"""Enhanced code editor widget with line numbers and LSP integration."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QSyntaxHighlighter,
    QTextDocument,
    QPalette,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget, QToolTip

from ghostline.core.config import ConfigManager
from ghostline.core.theme import ThemeManager
from ghostline.lang.diagnostics import Diagnostic
from ghostline.lang.lsp_manager import LSPManager
from ghostline.editor.folding import FoldingManager
from ghostline.editor.minimap import MiniMap
from ghostline.ai.ai_inline import InlineCompletionController
from ghostline.debugger.breakpoints import BreakpointStore
from ghostline.ai.ai_client import AIClient


class LineNumberArea(QWidget):
    """Side widget that paints line numbers."""

    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        self.code_editor._paint_line_numbers(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self.code_editor.toggle_breakpoint_from_gutter(event)


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
        ai_client: AIClient | None = None,
    ) -> None:
        super().__init__(parent)
        self.path = path
        self.config = config
        self.theme = theme
        self.lsp_manager = lsp_manager
        self._document_version = 0
        self._diagnostics: list[Diagnostic] = []
        self._extra_cursors: list[QTextCursor] = []
        self._bracket_selection: list[QTextEdit.ExtraSelection] = []
        self._bracket_scope: tuple[int, int, int] | None = None
        self.breakpoints = BreakpointStore.instance()

        font_family = self.config.get("font", {}).get("editor_family", "JetBrains Mono") if self.config else "JetBrains Mono"
        font_size = self.config.get("font", {}).get("editor_size", 11) if self.config else 11
        self.setFont(QFont(font_family, font_size))
        self.line_number_area = LineNumberArea(self)

        tab_size = self.config.get("tabs", {}).get("tab_size", 4) if self.config else 4
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" " * tab_size))

        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.cursorPositionChanged.connect(self._update_bracket_match)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.textChanged.connect(self._notify_lsp_change)

        self._highlighter = PythonHighlighter(self.document(), self.theme)
        self.folding = FoldingManager(self)
        self.minimap = MiniMap(self)
        self.inline_ai = InlineCompletionController(self, self.config, ai_client)

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
        # Left margin for gutter, small top margin so code does not stick
        # directly to the tab strip (more like Windsurf).
        self.setViewportMargins(self.line_number_area_width(), 4, 0, 0)

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
                if self.path and self.breakpoints.has(str(self.path), block_number):
                    radius = 5
                    painter.setBrush(QColor(200, 80, 80))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(
                        self.line_number_area.width() - 2 * radius - 2,
                        top + (self.fontMetrics().height() - radius) / 2,
                        radius * 2,
                        radius * 2,
                    )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

        # Vertical divider between gutter and code area.
        gutter_right = self.line_number_area.width() - 1
        painter.setPen(self.theme.color(QPalette.Dark) if self.theme else QColor(55, 55, 60))
        painter.drawLine(gutter_right, event.rect().top(), gutter_right, event.rect().bottom())

    def _block_at_position(self, y: float):
        block = self.firstVisibleBlock()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= y:
            if block.isVisible() and bottom >= y:
                return block
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
        return None

    def toggle_breakpoint_from_gutter(self, event: QMouseEvent) -> None:
        block = self._block_at_position(event.position().y())
        if block and self.path:
            self.breakpoints.toggle(str(self.path), block.blockNumber())
            self.line_number_area.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        self._paint_indent_guides()
        if self.inline_ai:
            self.inline_ai.paint_hint()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.modifiers() & Qt.AltModifier:
            cursor = self.cursorForPosition(event.position().toPoint())
            self._extra_cursors.append(cursor)
            self._highlight_current_line()
            return
        super().mousePressEvent(event)
        self._extra_cursors.clear()
        self._highlight_current_line()

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
        if self.inline_ai and self.inline_ai.handle_key(event):
            return
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_K:
            self._request_hover()
            return
        if event.key() == Qt.Key_Escape and self._extra_cursors:
            self._extra_cursors.clear()
            self._highlight_current_line()
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
        if self._extra_cursors and event.text() and not event.modifiers():
            text = event.text()
            for cursor in self._extra_cursors:
                cursor.insertText(text)
            super().keyPressEvent(event)
            self._sync_extra_cursors()
            return
        if self._extra_cursors and event.key() == Qt.Key_Backspace:
            for cursor in self._extra_cursors:
                if cursor.hasSelection():
                    cursor.removeSelectedText()
                else:
                    cursor.deletePreviousChar()
            super().keyPressEvent(event)
            self._sync_extra_cursors()
            return
        super().keyPressEvent(event)

    # Highlight current line and diagnostics
    def _highlight_current_line(self) -> None:
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = self.theme.color(QPalette.AlternateBase) if self.theme else QColor(60, 65, 70)
            # Softer, translucent band across the full width, Windsurf-style.
            line_color = QColor(line_color)
            line_color.setAlpha(80)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        extra_selections.extend(self._diagnostic_selections())
        extra_selections.extend(self._bracket_selection)
        extra_selections.extend(self._multi_cursor_selections())
        self.setExtraSelections(extra_selections)

    def _update_bracket_match(self) -> None:
        brackets = {"(": ")", "[": "]", "{": "}", ")": "(", "]": "[", "}": "{"}
        cursor = self.textCursor()
        doc_text = self.toPlainText()
        pos = cursor.position()
        char = doc_text[pos:pos + 1]
        backward = False
        if char not in brackets and pos > 0:
            char = doc_text[pos - 1:pos]
            pos -= 1
            backward = True
        if char not in brackets:
            self._bracket_selection = []
            self._bracket_scope = None
            self._highlight_current_line()
            return
        target = brackets[char]
        step = -1 if backward or char in ")]}" else 1
        depth = 0
        idx = pos + step
        match_pos = None
        while 0 <= idx < len(doc_text):
            token = doc_text[idx]
            if token == char:
                depth += 1
            elif token == target:
                if depth == 0:
                    match_pos = idx
                    break
                depth -= 1
            idx += step
        if match_pos is None:
            self._bracket_selection = []
            self._bracket_scope = None
            self._highlight_current_line()
            return
        self._bracket_selection = [
            self._selection_for_position(pos),
            self._selection_for_position(match_pos),
        ]
        start_line, start_col = self._block_and_column(min(pos, match_pos))
        end_line, end_col = self._block_and_column(max(pos, match_pos))
        scope_col = min(start_col, end_col)
        self._bracket_scope = (start_line, end_line, scope_col) if end_line != start_line else None
        self._highlight_current_line()

    def _diagnostic_selections(self) -> list[QTextEdit.ExtraSelection]:
        selections: list[QTextEdit.ExtraSelection] = []
        for diag in self._diagnostics:
            selection = QTextEdit.ExtraSelection()
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

    def _selection_for_position(self, position: int) -> QTextEdit.ExtraSelection:
        selection = QTextEdit.ExtraSelection()
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        cursor.setPosition(position + 1, QTextCursor.KeepAnchor)
        selection.cursor = cursor
        selection.format.setBackground(QColor(80, 120, 200, 120))
        return selection

    def _block_and_column(self, position: int) -> tuple[int, int]:
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        return cursor.blockNumber(), cursor.positionInBlock()

    def _multi_cursor_selections(self) -> list[QTextEdit.ExtraSelection]:
        selections: list[QTextEdit.ExtraSelection] = []
        for cursor in self._extra_cursors:
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.format.setBackground(QColor(90, 90, 120, 80))
            selections.append(sel)
        return selections

    def _sync_extra_cursors(self) -> None:
        synced: list[QTextCursor] = []
        for cursor in self._extra_cursors:
            clone = QTextCursor(self.document())
            clone.setPosition(cursor.position())
            synced.append(clone)
        self._extra_cursors = synced
        self._highlight_current_line()

    def _indent_columns(self, text: str) -> list[int]:
        tab_size = self.config.get("tabs", {}).get("tab_size", 4) if self.config else 4
        columns: list[int] = []
        col = 0
        for ch in text:
            if ch == " ":
                col += 1
            elif ch == "\t":
                remainder = col % tab_size
                col += tab_size - remainder if remainder else tab_size
            else:
                break
            if col and col % tab_size == 0:
                columns.append(col)
        return columns

    def _paint_indent_guides(self) -> None:
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, False)

        base_color = self.theme.color(QPalette.Dark) if self.theme else QColor(60, 60, 70)
        active_color = self.theme.color(QPalette.Highlight) if self.theme else QColor(100, 130, 180)
        base_color = QColor(base_color)
        base_color.setAlpha(80)
        active_color = QColor(active_color)
        active_color.setAlpha(110)

        tab_size = self.config.get("tabs", {}).get("tab_size", 4) if self.config else 4
        space_width = (self.tabStopDistance() or self.fontMetrics().horizontalAdvance(" " * tab_size)) / tab_size

        cursor_block = self.textCursor().block()
        active_columns = set(self._indent_columns(cursor_block.text()))
        if self._bracket_scope:
            active_columns.add(self._bracket_scope[2])

        block = self.firstVisibleBlock()
        offset = self.contentOffset()
        top = int(self.blockBoundingGeometry(block).translated(offset).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= self.viewport().rect().bottom():
            if block.isVisible() and bottom >= self.viewport().rect().top():
                indent_cols = self._indent_columns(block.text())
                for col in indent_cols:
                    x = offset.x() + col * space_width - space_width / 2
                    color = active_color if col in active_columns else base_color
                    painter.setPen(QPen(color, 1))
                    painter.drawLine(
                        int(x),
                        top,
                        int(x),
                        bottom,
                    )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())

        if self._bracket_scope:
            start_line, end_line, col = self._bracket_scope
            start_block = self.document().findBlockByNumber(start_line)
            end_block = self.document().findBlockByNumber(end_line)
            if start_block.isValid() and end_block.isValid():
                start_top = int(self.blockBoundingGeometry(start_block).translated(offset).top())
                end_bottom = int(
                    self.blockBoundingGeometry(end_block).translated(offset).top()
                    + self.blockBoundingRect(end_block).height()
                )
                x = offset.x() + col * space_width - space_width / 2
                painter.setPen(QPen(active_color, 2))
                painter.drawLine(int(x), start_top, int(x), end_bottom)

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

    def apply_unified_patch(self, patch: str) -> None:
        """Apply a unified diff to the current buffer as a single undo step."""
        from ghostline.ai.refactor_pipeline import UnifiedDiffApplier

        applier = UnifiedDiffApplier()
        updated = applier.apply(self.toPlainText(), patch)
        cursor = self.textCursor()
        cursor.beginEditBlock()
        self.setPlainText(updated)
        cursor.endEditBlock()
