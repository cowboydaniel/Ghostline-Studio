"""Enhanced code editor widget with line numbers and LSP integration."""
from __future__ import annotations

import builtins
import keyword
import tokenize
from io import StringIO
from pathlib import Path
from typing import Iterable, List

from PySide6.QtCore import QTimer, QPoint, QRect, QSize, Qt
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
from ghostline.ui.editor.semantic_tokens import SemanticToken, SemanticTokenProvider


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
    """Advanced Python syntax highlighter with semantic and token-based rules."""

    def __init__(
        self,
        document: QTextDocument,
        theme: ThemeManager | None,
        *,
        token_provider: SemanticTokenProvider | None = None,
    ) -> None:
        super().__init__(document)
        self.theme = theme or ThemeManager()
        self.token_provider = token_provider
        self._token_cache: dict[int, list[tuple[int, int, QTextCharFormat]]] = {}
        self._token_cache_revision: int = -1
        self._builtins = set(dir(builtins))
        self._semantic_tokens: dict[int, list[SemanticToken]] = {}
        self._init_rules()
        # Precompute token cache whenever the document changes to avoid
        # expensive parsing work from inside highlightBlock (which can
        # otherwise re-enter Qt's painting stack and crash certain builds).
        self.document().contentsChange.connect(self._rebuild_token_cache)
        self._rebuild_token_cache()

    def _fmt(self, color_key: str, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(self.theme.syntax_color(color_key))
        if bold:
            fmt.setFontWeight(QFont.Bold)
        return fmt

    def _init_rules(self) -> None:
        import re

        self.rules: List[tuple[object, QTextCharFormat]] = []
        keywords = r"\b(" + "|".join(keyword.kwlist) + r")\b"
        self.rules.append((re.compile(keywords), self._fmt("keyword", True)))
        self.rules.append((re.compile(r"#[^\n]*"), self._fmt("comment")))
        self.rules.append((re.compile(r"\b[0-9]+\b"), self._fmt("number")))
        self.rules.append((re.compile(r"\bself\b"), self._fmt("builtin")))
        self.rules.append((re.compile(r"\bclass\s+\w+"), self._fmt("definition", True)))
        string_fmt = self._fmt("string")
        self.rules.append((re.compile(r"'(?:[^'\\]|\\.)*'"), string_fmt))
        self.rules.append((re.compile(r'"(?:[^"\\]|\\.)*"'), string_fmt))

        # Token-based formats for richer highlighting.
        self._format_keyword = self._fmt("keyword", True)
        self._format_comment = self._fmt("comment")
        self._format_string = self._fmt("string")
        self._format_number = self._fmt("number")
        self._format_builtin = self._fmt("builtin")
        self._format_definition = self._fmt("definition", True)
        self._format_function = self._fmt("function", True)
        self._format_class = self._fmt("class", True)
        self._format_import = self._fmt("import")
        self._format_literal = self._fmt("literal")
        self._format_dunder = self._fmt("dunder")
        self._format_typehint = self._fmt("typehint")

    def set_semantic_tokens(self, tokens: List[SemanticToken]) -> None:
        self._semantic_tokens.clear()
        for token in tokens:
            self._semantic_tokens.setdefault(token.line, []).append(token)
        self.rehighlight()

    def _semantic_format(self, token_type: str) -> QTextCharFormat:
        if self.token_provider:
            return self.token_provider.format_for(token_type)
        return self._fmt("definition", True)

    def highlightBlock(self, text: str) -> None:  # type: ignore[override]
        for start, length, fmt in self._token_cache.get(self.currentBlock().blockNumber(), []):
            self.setFormat(start, length, fmt)

        line_tokens = self._semantic_tokens.get(self.currentBlock().blockNumber(), [])
        for token in line_tokens:
            fmt = self._semantic_format(token.token_type)
            self.setFormat(token.start, token.length, fmt)

    def _rebuild_token_cache(self, *_args) -> None:
        """Re-tokenize the document when its contents change."""
        revision = self.document().revision()
        if revision == self._token_cache_revision:
            return

        self._token_cache.clear()
        text = self.document().toPlainText()

        try:
            tokens = tokenize.generate_tokens(StringIO(text).readline)
            self._populate_token_cache(tokens)
        except (tokenize.TokenError, IndentationError, SyntaxError):
            # Fall back to the simpler regex rules if tokenization breaks.
            self._regex_fallback(text)

        self._token_cache_revision = revision
        self.rehighlight()

    def _regex_fallback(self, text: str) -> None:
        lines = text.splitlines()
        for line_no, line in enumerate(lines):
            block_tokens: list[tuple[int, int, QTextCharFormat]] = []
            for pattern, fmt in self.rules:
                for match in pattern.finditer(line):
                    start, end = match.span()
                    block_tokens.append((start, end - start, fmt))
            if block_tokens:
                self._token_cache[line_no] = block_tokens

    def _populate_token_cache(self, tokens: Iterable[tokenize.TokenInfo]) -> None:
        pending_definition: str | None = None
        decorator_next = False
        type_hint_context = False
        import_context = False

        for token_info in tokens:
            tok_type = token_info.type
            tok_str = token_info.string

            if tok_type in (tokenize.ENCODING, tokenize.ENDMARKER, tokenize.NL):
                continue
            if tok_type == tokenize.NEWLINE:
                type_hint_context = False
                import_context = False
                decorator_next = False
                continue

            fmt: QTextCharFormat | None = None
            if tok_type == tokenize.COMMENT:
                fmt = self._format_comment
            elif tok_type == tokenize.STRING:
                fmt = self._format_string
            elif tok_type == tokenize.NUMBER:
                fmt = self._format_number
            elif tok_type == tokenize.OP:
                if tok_str == "@":
                    decorator_next = True
                if tok_str in {":", "->", "|"}:
                    type_hint_context = True
                elif tok_str not in {".", ",", "|"}:
                    type_hint_context = False
            elif tok_type == tokenize.NAME:
                fmt, pending_definition = self._format_name(
                    tok_str,
                    pending_definition,
                    decorator_next,
                    import_context,
                    type_hint_context,
                )
                decorator_next = False
                if keyword.iskeyword(tok_str):
                    import_context = tok_str in {"import", "from"}
                    type_hint_context = tok_str in {"as"}
                else:
                    import_context = import_context and tok_str not in {"as"}

            if fmt:
                self._add_token_range(token_info.start, token_info.end, fmt)

    def _format_name(
        self,
        name: str,
        pending_definition: str | None,
        decorator_next: bool,
        import_context: bool,
        type_hint_context: bool,
    ) -> tuple[QTextCharFormat | None, str | None]:
        if keyword.iskeyword(name):
            pending = "class" if name == "class" else "def" if name == "def" else None
            return self._format_keyword, pending

        if pending_definition:
            fmt = self._format_function if pending_definition == "def" else self._format_class
            return fmt, None

        if decorator_next:
            return self._format_definition, None

        if name in {"True", "False", "None"}:
            return self._format_literal, pending_definition
        if name.startswith("__") and name.endswith("__"):
            return self._format_dunder, pending_definition
        if import_context:
            return self._format_import, pending_definition
        if type_hint_context and name[:1].isupper():
            return self._format_typehint, pending_definition
        if name in self._builtins:
            return self._format_builtin, pending_definition
        return None, pending_definition

    def _add_token_range(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        fmt: QTextCharFormat,
    ) -> None:
        start_line, start_col = start
        end_line, end_col = end
        for line in range(start_line - 1, end_line):
            line_start = start_col if line == start_line - 1 else 0
            line_end = end_col if line == end_line - 1 else self._line_length(line)
            length = max(0, line_end - line_start)
            if length:
                self._token_cache.setdefault(line, []).append((line_start, length, fmt))

    def _line_length(self, line: int) -> int:
        block = self.document().findBlockByNumber(line)
        return len(block.text()) if block.isValid() else 0


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
        self.theme = theme or ThemeManager()
        self.lsp_manager = lsp_manager
        self._document_version = 0
        self._loading_document = False
        self._lsp_document_opened = False
        self._diagnostics: list[Diagnostic] = []
        self._extra_cursors: list[QTextCursor] = []
        self._bracket_selection: list[QTextEdit.ExtraSelection] = []
        self._bracket_scope: tuple[int, int, int] | None = None
        self.breakpoints = BreakpointStore.instance()
        self._semantic_provider = SemanticTokenProvider("python", theme=self.theme)
        self._lsp_sync_timer = QTimer(self)
        self._lsp_sync_timer.setSingleShot(True)
        self._lsp_sync_timer.timeout.connect(self._flush_lsp_change)
        self._semantic_timer = QTimer(self)
        self._semantic_timer.setSingleShot(True)
        self._semantic_timer.timeout.connect(self._request_semantic_tokens)

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
        self.textChanged.connect(self._refresh_semantic_tokens)

        self._highlighter = PythonHighlighter(
            self.document(), self.theme, token_provider=self._semantic_provider
        )
        self.folding = FoldingManager(self)
        self.minimap = MiniMap(self)
        self.inline_ai = InlineCompletionController(self, self.config, ai_client)

        self._update_line_number_area_width(self.blockCount())
        if path and path.exists():
            self._load_file(path)
            self._open_in_lsp()
        self._refresh_semantic_tokens()

    # Line number plumbing
    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_margins()
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )
        self._position_minimap(cr)

    def _update_line_number_area_width(self, _=None) -> None:
        # Left margin for gutter, small top margin so code does not stick
        # directly to the tab strip (more like Windsurf).
        self._update_margins()

    def _update_margins(self) -> None:
        right_margin = self.minimap.width() if self.minimap.isVisible() else 0
        self.setViewportMargins(self.line_number_area_width(), 4, right_margin, 0)

    def minimap_resized(self) -> None:
        self._update_margins()
        self._position_minimap()
        self.updateGeometry()

    def _position_minimap(self, rect: QRect | None = None) -> None:
        cr = rect or self.contentsRect()
        minimap_width = self.minimap.width()
        self.minimap.setGeometry(
            QRect(cr.right() - minimap_width + 1, cr.top(), minimap_width, cr.height())
        )

    def _update_line_number_area(self, rect, dy) -> None:
        """Update the visible area of the line number gutter.

        Important: do NOT adjust margins from here. On some Qt builds,
        changing viewport margins during an updateRequest causes an
        endless cascade of update events and RecursionError.
        """
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        # We intentionally do NOT call _update_line_number_area_width() here.
        # Line number area width is already updated via blockCountChanged
        # and explicit resizeEvent handling.

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
        self._loading_document = True
        try:
            with path.open("r", encoding="utf-8") as handle:
                self.setPlainText(handle.read())
        finally:
            self._loading_document = False

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
            self._document_version = 1
            self._lsp_document_opened = True

    def _notify_lsp_change(self) -> None:
        if self._loading_document:
            return
        if not (self.lsp_manager and self.path):
            return

        # Guard against recursive logging/path handling in Python 3.12 by
        # throttling updates through a single-shot timer.
        if self._lsp_sync_timer.isActive():
            self._lsp_sync_timer.stop()
        self._lsp_sync_timer.start(120)

    def _flush_lsp_change(self) -> None:
        if self._loading_document:
            return
        if not (self.lsp_manager and self.path):
            return

        try:
            if not self._lsp_document_opened:
                self._open_in_lsp()
                return

            self._document_version += 1
            self.lsp_manager.change_document(
                str(self.path), self.toPlainText(), self._document_version
            )
        except RecursionError:
            return

    def _refresh_semantic_tokens(self) -> None:
        if self._semantic_timer.isActive():
            self._semantic_timer.stop()
        self._semantic_timer.start(150)

    def _request_semantic_tokens(self) -> None:
        if self._loading_document:
            return
        text = self.toPlainText()
        if not self.lsp_manager or not self.path:
            tokens = self._semantic_provider.custom_tokens(text)
            self._highlighter.set_semantic_tokens(tokens)
            return

        try:
            if self.lsp_manager.supports_semantic_tokens(self.path):
                if self.lsp_manager.request_semantic_tokens(
                    self.path,
                    callback=self._apply_semantic_tokens,
                    range_params=self._visible_range_params(),
                ):
                    self._lsp_document_opened = True
                    return
        except RecursionError:
            return

        tokens = self._semantic_provider.custom_tokens(text)
        self._highlighter.set_semantic_tokens(tokens)
        try:
            if not self._lsp_document_opened:
                self._open_in_lsp()
        except RecursionError:
            return

    def _apply_semantic_tokens(self, result: dict, legend: list[str]) -> None:
        tokens = SemanticTokenProvider.from_lsp(result, legend)
        if not tokens:
            tokens = self._semantic_provider.custom_tokens(self.toPlainText())
        self._highlighter.set_semantic_tokens(tokens)
        self._highlighter.rehighlight()

    def _visible_range_params(self) -> dict | None:
        block = self.firstVisibleBlock()
        if not block.isValid():
            return None

        start_line = block.blockNumber()
        offset = self.contentOffset()
        top = int(self.blockBoundingGeometry(block).translated(offset).top())
        bottom_limit = self.viewport().rect().bottom()
        end_line = start_line

        while block.isValid() and top <= bottom_limit:
            if block.isVisible():
                end_line = block.blockNumber()
            block = block.next()
            if not block.isValid():
                break
            top = int(self.blockBoundingGeometry(block).translated(offset).top())

        end_line = max(end_line, start_line)
        return {
            "start": {"line": start_line, "character": 0},
            "end": {"line": end_line + 1, "character": 0},
        }

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

    def get_state(self) -> dict:
        """Get current editor state including cursor and scroll positions."""
        cursor = self.textCursor()
        return {
            "cursor_position": cursor.position(),
            "scroll_vertical": self.verticalScrollBar().value(),
            "scroll_horizontal": self.horizontalScrollBar().value(),
        }

    def restore_state(self, state: dict) -> None:
        """Restore editor state including cursor and scroll positions."""
        if "cursor_position" in state:
            cursor = self.textCursor()
            cursor.setPosition(min(state["cursor_position"], len(self.toPlainText())))
            self.setTextCursor(cursor)
        if "scroll_vertical" in state:
            self.verticalScrollBar().setValue(state["scroll_vertical"])
        if "scroll_horizontal" in state:
            self.horizontalScrollBar().setValue(state["scroll_horizontal"])
