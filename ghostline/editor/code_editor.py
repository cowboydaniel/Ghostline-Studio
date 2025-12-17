"""Enhanced code editor widget with line numbers and LSP integration."""
from __future__ import annotations

import builtins
import keyword
from functools import partial
import re
import tokenize
from io import StringIO
from pathlib import Path
from typing import Iterable, List, Optional

from PySide6.QtCore import QTimer, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QSyntaxHighlighter,
    QTextDocument,
    QPalette,
    QShortcut,
)
from PySide6.QtWidgets import (
    QPlainTextEdit,
    QTextEdit,
    QWidget,
    QToolTip,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QVBoxLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QToolButton,
    QCheckBox,
)

from ghostline.core.config import ConfigManager
from ghostline.core.theme import ThemeManager
from ghostline.lang.diagnostics import Diagnostic
from ghostline.lang.lsp_manager import LSPManager
from ghostline.editor.folding import FoldingManager
from ghostline.editor.minimap import MiniMap
from ghostline.debugger.breakpoints import BreakpointStore
from ghostline.ai.ai_client import AIClient
from ghostline.editor.highlighting import create_highlighting
from ghostline.ui.editor.semantic_tokens import SemanticToken, SemanticTokenProvider


class SnippetManager:
    """Manages snippet insertion and tab stop navigation."""

    def __init__(self, editor: "CodeEditor") -> None:
        self.editor = editor
        self.active_snippet: Optional[dict] = None
        self.tab_stops: List[tuple[int, int, str]] = []  # (start_pos, length, placeholder)
        self.current_tab_stop = 0

    def parse_snippet(self, text: str) -> tuple[str, List[tuple[int, int, str]]]:
        """Parse snippet text and extract tab stops.

        Supports:
        - ${1:placeholder} - tab stop with placeholder text
        - $1 - simple tab stop
        - $0 - final cursor position
        - ${1|choice1,choice2|} - choice tab stop (simplified to first choice)
        """
        tab_stops: List[tuple[int, int, str]] = []
        result = []
        offset = 0

        # Pattern: ${number:placeholder} or ${number|choice1,choice2|} or $number
        pattern = r'\$\{(\d+):([^}]*)\}|\$\{(\d+)\|([^}]*)\}|\$(\d+)'

        for match in re.finditer(pattern, text):
            # Add text before the match
            result.append(text[offset:match.start()])

            if match.group(1):  # ${number:placeholder}
                tab_num = int(match.group(1))
                placeholder = match.group(2)
                pos = len(''.join(result))
                tab_stops.append((tab_num, pos, len(placeholder), placeholder))
                result.append(placeholder)
            elif match.group(3):  # ${number|choice1,choice2|}
                tab_num = int(match.group(3))
                choices = match.group(4).split(',')
                placeholder = choices[0] if choices else ""
                pos = len(''.join(result))
                tab_stops.append((tab_num, pos, len(placeholder), placeholder))
                result.append(placeholder)
            elif match.group(5):  # $number
                tab_num = int(match.group(5))
                pos = len(''.join(result))
                tab_stops.append((tab_num, pos, 0, ""))

            offset = match.end()

        # Add remaining text
        result.append(text[offset:])

        # Sort tab stops by number
        tab_stops.sort(key=lambda x: x[0])

        # Convert to (position, length, placeholder) tuples
        simplified_stops = [(pos, length, placeholder) for _, pos, length, placeholder in tab_stops]

        return ''.join(result), simplified_stops

    def insert_snippet(self, snippet_text: str) -> None:
        """Insert snippet and set up tab stops."""
        parsed_text, tab_stops = self.parse_snippet(snippet_text)

        cursor = self.editor.textCursor()
        start_pos = cursor.position()

        # Insert the parsed text
        cursor.insertText(parsed_text)

        # Adjust tab stop positions relative to insertion point
        self.tab_stops = [(start_pos + pos, length, placeholder) for pos, length, placeholder in tab_stops]
        self.current_tab_stop = 0

        if self.tab_stops:
            self.active_snippet = {"start": start_pos, "text": parsed_text}
            self.jump_to_next_tab_stop()
        else:
            self.active_snippet = None

    def jump_to_next_tab_stop(self) -> bool:
        """Jump to next tab stop. Returns True if jumped, False if no more stops."""
        if not self.tab_stops or self.current_tab_stop >= len(self.tab_stops):
            self.active_snippet = None
            return False

        pos, length, placeholder = self.tab_stops[self.current_tab_stop]
        cursor = self.editor.textCursor()
        cursor.setPosition(pos)
        if length > 0:
            cursor.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.current_tab_stop += 1
        return True

    def cancel_snippet(self) -> None:
        """Cancel active snippet."""
        self.active_snippet = None
        self.tab_stops = []
        self.current_tab_stop = 0


class CompletionWidget(QWidget):
    """Enhanced popup widget for displaying LSP completions with documentation preview."""

    # LSP CompletionItemKind mapping to display strings
    COMPLETION_KINDS = {
        1: "Text", 2: "Method", 3: "Function", 4: "Constructor", 5: "Field",
        6: "Variable", 7: "Class", 8: "Interface", 9: "Module", 10: "Property",
        11: "Unit", 12: "Value", 13: "Enum", 14: "Keyword", 15: "Snippet",
        16: "Color", 17: "File", 18: "Reference", 19: "Folder", 20: "EnumMember",
        21: "Constant", 22: "Struct", 23: "Event", 24: "Operator", 25: "TypeParameter"
    }

    # Symbol characters for completion kinds (similar to VS Code)
    KIND_SYMBOLS = {
        1: "abc", 2: "ƒ", 3: "ƒ", 4: "ƒ", 5: "⚬",
        6: "x", 7: "○", 8: "◎", 9: "□", 10: "⚬",
        11: "u", 12: "v", 13: "Ɛ", 14: "‹›", 15: "▭",
        16: "⬜", 17: "📄", 18: "⮕", 19: "📁", 20: "◆",
        21: "◆", 22: "◫", 23: "⚡", 24: "+", 25: "T"
    }

    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor
        self.completion_items: list[dict] = []
        self.completion_prefix = ""
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left side: completion list
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(300)
        self.list_widget.setMaximumHeight(300)
        self.list_widget.itemActivated.connect(self._insert_completion)
        self.list_widget.currentRowChanged.connect(self._update_documentation)
        layout.addWidget(self.list_widget)

        # Right side: documentation preview
        self.doc_frame = QFrame()
        self.doc_frame.setFrameShape(QFrame.StyledPanel)
        self.doc_frame.setMinimumWidth(350)
        self.doc_frame.setMaximumWidth(450)
        self.doc_frame.setMaximumHeight(300)
        doc_layout = QVBoxLayout(self.doc_frame)
        doc_layout.setContentsMargins(8, 8, 8, 8)

        self.doc_label = QLabel()
        self.doc_label.setWordWrap(True)
        self.doc_label.setTextFormat(Qt.TextFormat.RichText)
        self.doc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        doc_layout.addWidget(self.doc_label)

        layout.addWidget(self.doc_frame)

        # Apply VS Code Dark+ styling
        self.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                color: #CCCCCC;
                border: 1px solid #454545;
                outline: none;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 4px 8px;
                border: none;
            }
            QListWidget::item:selected {
                background-color: #094771;
                color: #FFFFFF;
            }
            QListWidget::item:hover {
                background-color: #2A2D2E;
            }
            QFrame {
                background-color: #1E1E1E;
                border: 1px solid #454545;
            }
            QLabel {
                color: #CCCCCC;
                font-size: 12px;
            }
        """)

        self.hide()

    def show_completions(self, items: list[dict], prefix: str = "") -> None:
        """Display completion items filtered by prefix."""
        self.completion_items = items
        self.completion_prefix = prefix
        self.list_widget.clear()

        # Filter items by prefix - prioritize prefix matches at start
        def match_score(item: dict) -> tuple[int, str]:
            label = item.get("label", "").lower()
            prefix_lower = prefix.lower()
            if label.startswith(prefix_lower):
                return (0, label)  # Exact prefix match - highest priority
            elif prefix_lower in label:
                return (1, label)  # Contains prefix
            else:
                return (2, label)  # No match

        filtered_items = [
            item for item in items
            if prefix.lower() in item.get("label", "").lower()
        ]

        # Sort by match quality
        filtered_items.sort(key=match_score)

        if not filtered_items:
            self.hide()
            return

        for item in filtered_items[:50]:  # Limit to 50 items (VS Code shows more than 20)
            label = item.get("label", "")
            kind = item.get("kind", 1)
            detail = item.get("detail", "")

            # Create display text with kind symbol
            kind_symbol = self.KIND_SYMBOLS.get(kind, "○")
            display_text = f"{kind_symbol}  {label}"
            if detail and len(detail) < 40:
                display_text += f"  {detail}"

            list_item = QListWidgetItem(display_text)
            list_item.setData(Qt.ItemDataRole.UserRole, item)

            # Color code by kind (similar to VS Code)
            if kind in {2, 3, 4}:  # Methods/Functions
                list_item.setForeground(QColor("#DCDCAA"))
            elif kind in {7, 8}:  # Class/Interface
                list_item.setForeground(QColor("#4EC9B0"))
            elif kind == 14:  # Keyword
                list_item.setForeground(QColor("#569CD6"))
            elif kind == 15:  # Snippet
                list_item.setForeground(QColor("#D16969"))

            self.list_widget.addItem(list_item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            # Position below cursor
            cursor_rect = self.editor.cursorRect()
            global_pos = self.editor.mapToGlobal(cursor_rect.bottomLeft())
            self.move(global_pos)
            self.show()
            self.raise_()
            self._update_documentation(0)
        else:
            self.hide()

    def _update_documentation(self, row: int) -> None:
        """Update documentation preview for selected item."""
        if row < 0 or row >= self.list_widget.count():
            self.doc_label.setText("")
            return

        item = self.list_widget.item(row)
        completion_data = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not completion_data:
            self.doc_label.setText("")
            return

        # Build documentation HTML
        html_parts = []

        label = completion_data.get("label", "")
        kind = completion_data.get("kind", 1)
        kind_name = self.COMPLETION_KINDS.get(kind, "Symbol")
        detail = completion_data.get("detail", "")
        documentation = completion_data.get("documentation", "")

        # Header with label and kind
        html_parts.append(f'<div style="margin-bottom: 8px;">')
        html_parts.append(f'<span style="color: #4EC9B0; font-weight: bold; font-size: 14px;">{label}</span>')
        html_parts.append(f'<span style="color: #858585; font-size: 11px; margin-left: 8px;">({kind_name})</span>')
        html_parts.append('</div>')

        # Detail (function signature, type info, etc.)
        if detail:
            html_parts.append(f'<div style="margin-bottom: 8px; font-family: monospace; color: #DCDCAA; background-color: #1E1E1E; padding: 4px; border-left: 3px solid #007ACC;">')
            html_parts.append(detail.replace('<', '&lt;').replace('>', '&gt;'))
            html_parts.append('</div>')

        # Documentation text
        if documentation:
            doc_text = documentation
            # Handle dict format (LSP MarkupContent)
            if isinstance(documentation, dict):
                doc_text = documentation.get("value", "")

            # Convert markdown code blocks to styled HTML
            doc_text = str(doc_text).replace('<', '&lt;').replace('>', '&gt;')
            doc_text = re.sub(r'`([^`]+)`', r'<code style="background-color: #1E1E1E; padding: 2px 4px;">\1</code>', doc_text)

            html_parts.append(f'<div style="color: #CCCCCC; line-height: 1.4;">')
            html_parts.append(doc_text)
            html_parts.append('</div>')

        self.doc_label.setText(''.join(html_parts) if html_parts else "No documentation available.")


class InlineFindReplaceBar(QWidget):
    """Lightweight in-editor find/replace bar that hugs the editor viewport."""

    findRequested = Signal(str, bool)
    replaceRequested = Signal(str, str)
    replaceAllRequested = Signal(str, str)
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("inlineFindReplace")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.find_input = QLineEdit(self)
        self.find_input.setPlaceholderText("Find")
        self.find_input.returnPressed.connect(lambda: self.findRequested.emit(self.find_input.text(), True))
        layout.addWidget(self.find_input, 1)

        self.case_checkbox = QCheckBox("Aa", self)
        self.case_checkbox.setToolTip("Match case")
        layout.addWidget(self.case_checkbox)

        self.prev_button = QPushButton("Prev", self)
        self.prev_button.clicked.connect(lambda: self.findRequested.emit(self.find_input.text(), False))
        layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next", self)
        self.next_button.clicked.connect(lambda: self.findRequested.emit(self.find_input.text(), True))
        layout.addWidget(self.next_button)

        self.replace_input = QLineEdit(self)
        self.replace_input.setPlaceholderText("Replace")
        layout.addWidget(self.replace_input, 1)

        self.replace_button = QPushButton("Replace", self)
        self.replace_button.clicked.connect(self._emit_replace)
        layout.addWidget(self.replace_button)

        self.replace_all_button = QPushButton("Replace All", self)
        self.replace_all_button.clicked.connect(self._emit_replace_all)
        layout.addWidget(self.replace_all_button)

        self.close_button = QToolButton(self)
        self.close_button.setText("✕")
        self.close_button.clicked.connect(self.hide)
        self.close_button.clicked.connect(self.closed.emit)
        layout.addWidget(self.close_button)

    def set_query(self, text: str) -> None:
        self.find_input.setText(text)
        self.find_input.selectAll()
        self.find_input.setFocus()

    def set_replace_visible(self, visible: bool) -> None:
        for widget in (self.replace_input, self.replace_button, self.replace_all_button):
            widget.setVisible(visible)

    def current_query(self) -> str:
        return self.find_input.text()

    def current_replacement(self) -> str:
        return self.replace_input.text()

    def case_sensitive(self) -> bool:
        return self.case_checkbox.isChecked()

    def focus_find(self) -> None:
        self.find_input.setFocus()

    def _emit_replace(self) -> None:
        self.replaceRequested.emit(self.find_input.text(), self.replace_input.text())

    def _emit_replace_all(self) -> None:
        self.replaceAllRequested.emit(self.find_input.text(), self.replace_input.text())

    def _insert_completion(self, item: QListWidgetItem) -> None:
        """Insert the selected completion item."""
        completion_data = item.data(Qt.ItemDataRole.UserRole)
        if not completion_data:
            return

        # Check for snippet format
        insert_format = completion_data.get("insertTextFormat", 1)  # 1 = PlainText, 2 = Snippet
        insert_text = completion_data.get("insertText") or completion_data.get("label", "")

        # Remove the prefix that was already typed
        cursor = self.editor.textCursor()
        if self.completion_prefix:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(self.completion_prefix))
            cursor.removeSelectedText()

        # Insert as snippet or plain text
        if insert_format == 2 and hasattr(self.editor, 'snippet_manager'):
            # Insert as snippet with tab stops
            self.editor.snippet_manager.insert_snippet(insert_text)
        else:
            # Insert as plain text
            cursor.insertText(insert_text)
            self.editor.setTextCursor(cursor)

        self.hide()

    def select_next(self) -> None:
        """Select next completion item."""
        current = self.list_widget.currentRow()
        if current < self.list_widget.count() - 1:
            self.list_widget.setCurrentRow(current + 1)

    def select_previous(self) -> None:
        """Select previous completion item."""
        current = self.list_widget.currentRow()
        if current > 0:
            self.list_widget.setCurrentRow(current - 1)

    def accept_current(self) -> None:
        """Accept currently selected completion."""
        current_item = self.list_widget.currentItem()
        if current_item:
            self._insert_completion(current_item)


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
        self.rules.append((re.compile(keywords), self._fmt("keyword")))
        self.rules.append((re.compile(r"#[^\n]*"), self._fmt("comment")))
        self.rules.append((re.compile(r"\b[0-9]+\b"), self._fmt("number")))
        self.rules.append((re.compile(r"\bself\b"), self._fmt("builtin")))
        self.rules.append((re.compile(r"\bclass\s+\w+"), self._fmt("definition")))
        string_fmt = self._fmt("string")
        self.rules.append((re.compile(r"'(?:[^'\\]|\\.)*'"), string_fmt))
        self.rules.append((re.compile(r'"(?:[^"\\]|\\.)*"'), string_fmt))

        # Token-based formats for richer highlighting.
        self._format_keyword = self._fmt("keyword")
        self._format_comment = self._fmt("comment")
        self._format_string = self._fmt("string")
        self._format_number = self._fmt("number")
        self._format_builtin = self._fmt("builtin")
        self._format_definition = self._fmt("definition")
        self._format_function = self._fmt("function")
        self._format_class = self._fmt("class")
        self._format_import = self._fmt("import")
        self._format_literal = self._fmt("literal")
        self._format_dunder = self._fmt("dunder")
        self._format_typehint = self._fmt("typehint")
        self._format_decorator = self._fmt("decorator")
        self._format_variable = self._fmt("variable")
        self._format_operator = self._fmt("operator")

    def set_semantic_tokens(self, tokens: List[SemanticToken]) -> None:
        self._semantic_tokens.clear()
        for token in tokens:
            self._semantic_tokens.setdefault(token.line, []).append(token)
        self.rehighlight()

    def _semantic_format(self, token_type: str) -> QTextCharFormat:
        if self.token_provider:
            return self.token_provider.format_for(token_type)
        return self._fmt("variable")

    def highlightBlock(self, text: str) -> None:  # type: ignore[override]
        block_number = self.currentBlock().blockNumber()
        block_tokens = self._token_cache.get(block_number)

        # Apply semantic tokens first
        line_tokens = self._semantic_tokens.get(block_number, [])
        for token in line_tokens:
            fmt = self._semantic_format(token.token_type)
            self.setFormat(token.start, token.length, fmt)

        # Then apply token cache - this ensures strings, comments, and keywords
        # from Python's tokenizer always get the correct color, even if LSP
        # doesn't send proper semantic tokens for them (e.g., docstrings)
        if block_tokens:
            for start, length, fmt in block_tokens:
                self.setFormat(start, length, fmt)

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
            # Leave the cache empty on malformed code; semantic tokens still apply.
            pass

        self._token_cache_revision = revision
        self.rehighlight()

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
            return self._format_decorator, None

        if name in {"True", "False", "None"}:
            return self._format_literal, pending_definition
        if name.startswith("__") and name.endswith("__"):
            return self._format_dunder, pending_definition
        # import_context removed - module names should use variable color
        if type_hint_context and name[:1].isupper():
            return self._format_typehint, pending_definition
        if name in self._builtins:
            return self._format_builtin, pending_definition
        # Default to variable color for unrecognized names
        return self._format_variable, pending_definition

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
    navigationStateChanged = Signal(bool, bool)
    editNavigationChanged = Signal(bool, bool)
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
        self._selection_stack: list[list[tuple[int, int]]] = []
        self._suppress_stack_reset = False
        self._column_selection_enabled = bool(
            (config or {}).get("editor", {}).get("column_selection_mode", False)
        )
        self._column_anchor: tuple[int, int] | None = None
        editor_config = self.config.get("editor", {}) if self.config else {}
        self._multi_cursor_modifier = editor_config.get("multi_cursor_modifier", "alt").lower()
        self._bracket_selection: list[QTextEdit.ExtraSelection] = []
        self._bracket_scope: tuple[int, int, int] | None = None
        self.breakpoints = BreakpointStore.instance()
        self._language_override: str | None = None
        self._language: str | None = None
        self._semantic_provider: SemanticTokenProvider | None = None
        self._semantic_legends: dict[str, list[str]] = {}
        self._highlighter: QSyntaxHighlighter | None = None
        self._lsp_sync_timer = QTimer(self)
        self._lsp_sync_timer.setSingleShot(True)
        self._lsp_sync_timer.timeout.connect(self._flush_lsp_change)
        self._semantic_timer = QTimer(self)
        self._semantic_timer.setSingleShot(True)
        self._semantic_timer.timeout.connect(self._request_semantic_tokens)
        self._semantic_request_pending = False
        self._last_semantic_revision = -1
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(300)  # 300ms delay
        self._hover_timer.timeout.connect(self._request_hover_at_mouse)
        self._hover_position: QPoint | None = None

        # Auto-completion timer for debouncing
        self._completion_timer = QTimer(self)
        self._completion_timer.setSingleShot(True)

        # IntelliSense configuration from settings
        intellisense_config = self.config.get("intellisense", {}) if self.config else {}
        self._intellisense_enabled = intellisense_config.get("enabled", True)
        self._auto_trigger_enabled = intellisense_config.get("auto_trigger", True)
        debounce_ms = intellisense_config.get("debounce_ms", 150)
        self._completion_timer.setInterval(debounce_ms)
        self._completion_timer.timeout.connect(self._auto_request_completions)

        # Trigger characters from config
        trigger_chars = intellisense_config.get("trigger_characters", ['.', ':', '>', '(', '[', '"', "'", '/', '@'])
        self._trigger_characters = set(trigger_chars) if isinstance(trigger_chars, list) else {'.', ':', '>', '(', '[', '"', "'", '/', '@'}
        self._min_chars_for_completion = intellisense_config.get("min_chars", 1)

        # Auto-closing brackets configuration
        self._auto_close_brackets = editor_config.get("auto_close_brackets", True)
        self._bracket_pairs = {
            '(': ')',
            '[': ']',
            '{': '}',
            '"': '"',
            "'": "'",
        }
        self._word_wrap_enabled = bool(editor_config.get("word_wrap", False))

        self._nav_back_stack: list[tuple[int, int]] = []
        self._nav_forward_stack: list[tuple[int, int]] = []
        self._navigating = False
        self._edit_locations: list[tuple[int, int]] = []
        self._edit_index: int | None = None
        self._last_edit_location: tuple[int, int] | None = None

        wrap_mode = QPlainTextEdit.WidgetWidth if self._word_wrap_enabled else QPlainTextEdit.NoWrap
        self.setLineWrapMode(wrap_mode)

        font_family = self.config.get("font", {}).get("editor_family", "JetBrains Mono") if self.config else "JetBrains Mono"
        font_size = self.config.get("font", {}).get("editor_size", 11) if self.config else 11
        self.setFont(QFont(font_family, font_size))
        self.line_number_area = LineNumberArea(self)

        tab_size = self.config.get("tabs", {}).get("tab_size", 4) if self.config else 4
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" " * tab_size))

        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.cursorPositionChanged.connect(self._update_bracket_match)
        self.cursorPositionChanged.connect(self._record_cursor_history)
        self.selectionChanged.connect(self._reset_selection_stack)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.textChanged.connect(self._notify_lsp_change)
        self.textChanged.connect(self._refresh_semantic_tokens)
        self.textChanged.connect(self._record_edit_location)

        self._update_language_for_context()
        self.folding = FoldingManager(self)
        self.minimap = MiniMap(self)
        self.completion_widget = CompletionWidget(self)
        self.snippet_manager = SnippetManager(self)
        self.find_bar = InlineFindReplaceBar(self)
        self.find_bar.hide()
        self.find_bar.findRequested.connect(self._run_inline_search)
        self.find_bar.replaceRequested.connect(self._replace_current)
        self.find_bar.replaceAllRequested.connect(self._replace_all)
        self.find_bar.closed.connect(self.setFocus)
        self.setMouseTracking(True)  # Enable mouse tracking for hover

        self._install_shortcuts()

        self._update_line_number_area_width(self.blockCount())
        if path and path.exists():
            self._load_file(path)
            self._open_in_lsp()
            # Request semantic tokens immediately on file open for instant highlighting
            # instead of waiting for the delayed timer in _refresh_semantic_tokens()
            self._request_semantic_tokens()
        else:
            # For new/empty files, use the delayed request
            self._refresh_semantic_tokens()

        self._record_position_for_history(initial=True)
    # Editing utilities
    def _install_shortcuts(self) -> None:
        """Ensure core edit commands work even with custom key handling."""

        bindings = [
            (QKeySequence.Undo, self.undo),
            (QKeySequence.Redo, self.redo),
            (QKeySequence.Cut, self.cut),
            (QKeySequence.Copy, self.copy),
            (QKeySequence.Paste, self.paste),
            (QKeySequence.SelectAll, self.selectAll),
            (QKeySequence.Find, lambda: self.show_find_bar()),
            (QKeySequence.Replace, lambda: self.show_find_bar(replace=True)),
            (QKeySequence.FindNext, self.find_next),
            (QKeySequence.FindPrevious, self.find_previous),
        ]

        for sequence, handler in bindings:
            shortcut = QShortcut(sequence, self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)

    def _selected_text_or_word(self) -> str:
        cursor = self.textCursor()
        if cursor.hasSelection():
            return cursor.selectedText()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()

    def show_find_bar(self, *, replace: bool = False, preset: str | None = None) -> None:
        if preset is None:
            preset = self._selected_text_or_word()
        if preset:
            self.find_bar.set_query(preset)
        self.find_bar.set_replace_visible(replace)
        self.find_bar.show()
        self._layout_find_bar()
        self.find_bar.focus_find()

    def hide_find_bar(self) -> None:
        self.find_bar.hide()

    def find_next(self) -> None:
        query = self.find_bar.current_query() or self._selected_text_or_word()
        self.show_find_bar(preset=query)
        self._run_inline_search(query, True)

    def find_previous(self) -> None:
        query = self.find_bar.current_query() or self._selected_text_or_word()
        self.show_find_bar(preset=query)
        self._run_inline_search(query, False)

    def _find_flags(self, forward: bool) -> QTextDocument.FindFlags:
        flags = QTextDocument.FindFlag(0)
        if not forward:
            flags |= QTextDocument.FindBackward
        if self.find_bar.case_sensitive():
            flags |= QTextDocument.FindCaseSensitively
        return flags

    def _run_inline_search(self, text: str, forward: bool = True) -> None:
        if not text:
            return

        flags = self._find_flags(forward)
        cursor = self.textCursor()
        match = self.document().find(text, cursor, flags)
        if match.isNull():
            anchor = QTextCursor(self.document())
            if not forward:
                anchor.movePosition(QTextCursor.MoveOperation.End)
            match = self.document().find(text, anchor, flags)

        if not match.isNull():
            self.setTextCursor(match)

    def _replace_current(self, find_text: str, replace_text: str) -> None:
        if not find_text:
            return
        cursor = self.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == find_text:
            cursor.insertText(replace_text)
            self.setTextCursor(cursor)
        self._run_inline_search(find_text, True)

    def _replace_all(self, find_text: str, replace_text: str) -> None:
        if not find_text:
            return
        cursor = QTextCursor(self.document())
        flags = self._find_flags(True)
        replacements = []
        while True:
            match = self.document().find(find_text, cursor, flags)
            if match.isNull():
                break
            replacements.append(match)
            cursor = match

        # Apply in reverse to keep offsets stable
        for match in reversed(replacements):
            match.insertText(replace_text)

    def toggle_line_comment(self) -> None:
        line_token, _, _ = self._comment_tokens()
        if not line_token:
            # Fallback to block style if no line comment exists
            self.toggle_block_comment()
            return

        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        while cursor.position() <= end:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            text = cursor.selectedText()
            stripped = text.lstrip()
            indent = text[: len(text) - len(stripped)]
            if stripped.startswith(line_token):
                new_text = indent + stripped[len(line_token) :].lstrip()
            else:
                new_text = indent + f"{line_token} {stripped}" if stripped else indent + line_token
            cursor.insertText(new_text)
            end += len(new_text) - len(text)
            if not cursor.movePosition(QTextCursor.MoveOperation.Down):
                break
        cursor.endEditBlock()

    def toggle_block_comment(self) -> None:
        _, block_start, block_end = self._comment_tokens()
        if not (block_start and block_end):
            return
        cursor = self.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        text = cursor.selectedText()
        if text.startswith(block_start) and text.endswith(block_end):
            inner = text[len(block_start) : -len(block_end)]
            cursor.insertText(inner)
        else:
            cursor.insertText(f"{block_start}{text}{block_end}")

    def _comment_tokens(self) -> tuple[str, str, str]:
        language = (self._language or "").lower()
        line_token = "#"
        block_start = "/*"
        block_end = "*/"

        if language in {"python", "shell", "bash"}:
            block_start = block_end = "\"\"\""
        elif language in {"c", "cpp", "javascript", "typescript", "java", "go", "rust", "css"}:
            line_token = "//"
        elif language in {"html", "xml"}:
            line_token = ""
            block_start, block_end = "<!--", "-->"

        return line_token, block_start, block_end

    def expand_emmet_selection(self) -> None:
        abbreviation = self._selected_text_or_word()
        if not abbreviation:
            return

        expansion = self._expand_emmet(abbreviation)
        if not expansion:
            return

        cursor = self.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        indent = self._current_line_indent()
        indented = "\n".join(indent + line if line.strip() else line for line in expansion.split("\n"))
        cursor.insertText(indented)
        self.setTextCursor(cursor)

    def _current_line_indent(self) -> str:
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText()
        return line[: len(line) - len(line.lstrip())]

    def _expand_emmet(self, abbreviation: str) -> str:
        def parse_node(segment: str) -> tuple[str, list[str], str | None, int]:
            body, multiplier = segment, 1
            if "*" in segment:
                base, mult = segment.rsplit("*", 1)
                if mult.isdigit():
                    body, multiplier = base, int(mult)
            tag = re.match(r"[a-zA-Z0-9]+", body)
            name = tag.group(0) if tag else "div"
            remainder = body[len(name) :]
            classes = [part[1:] for part in remainder.split(".") if part.startswith(".")]
            element_id = None
            for part in remainder.split("."):
                if part.startswith("#"):
                    element_id = part[1:]
            return name, classes, element_id, multiplier

        def build_tree(expr: str) -> list[dict]:
            nodes: list[dict] = []
            for sibling in expr.split("+"):
                parts = sibling.split(">", 1)
                head = parts[0]
                children_expr = parts[1] if len(parts) > 1 else None
                name, classes, element_id, multiplier = parse_node(head)
                children = build_tree(children_expr) if children_expr else []
                for _ in range(multiplier):
                    nodes.append({"name": name, "classes": classes, "id": element_id, "children": children})
            return nodes

        def render(nodes: list[dict], depth: int = 0) -> str:
            lines: list[str] = []
            indent = "    " * depth
            for node in nodes:
                attrs = []
                if node["id"]:
                    attrs.append(f'id="{node["id"]}"')
                if node["classes"]:
                    class_attr = " ".join(node["classes"])
                    attrs.append(f'class="{class_attr}"')
                attr_text = f" {' '.join(attrs)}" if attrs else ""
                if node["children"]:
                    lines.append(f"{indent}<{node['name']}{attr_text}>")
                    lines.append(render(node["children"], depth + 1))
                    lines.append(f"{indent}</{node['name']}>")
                else:
                    lines.append(f"{indent}<{node['name']}{attr_text}></{node['name']}>")
            return "\n".join(lines).rstrip("\n")

        try:
            tree = build_tree(abbreviation)
            return render(tree)
        except Exception:
            return ""

    # Highlighting helpers
    def set_language(self, language: str | None) -> None:
        """Explicitly set the editor language and rebuild highlighting."""
        self._language_override = language
        self._update_language_for_context(force=True)

    def _update_language_for_context(self, *, force: bool = False) -> None:
        self._apply_language_change(self._language_for_context(), force=force)

    def _language_for_context(self) -> str:
        if self._language_override:
            return self._language_override
        language = self._language_from_path(self.path)
        return language or "python"

    def _language_from_path(self, path: Path | None = None) -> str | None:
        target = path if path is not None else self.path
        if self.lsp_manager and target:
            return self.lsp_manager.language_for_path(target)
        return None

    def _apply_language_change(self, language: str | None, *, force: bool = False) -> None:
        resolved = (language or "python").lower()
        if not force and self._language == resolved and self._highlighter:
            return

        self._language = resolved
        self._semantic_legends.clear()

        if hasattr(self, "_highlighter") and self._highlighter:
            try:
                self._highlighter.set_semantic_tokens([])  # type: ignore[attr-defined]
            except Exception:
                pass
            self._highlighter.deleteLater()

        highlighter, semantic_provider = create_highlighting(
            self.document(), resolved, self.theme
        )
        self._semantic_provider = semantic_provider
        self._highlighter = highlighter
        self._highlighter.rehighlight()

        # Reset semantic tracking so new providers request fresh tokens
        self._last_semantic_revision = -1
        self._semantic_request_pending = False
        self._refresh_semantic_tokens()

    def set_word_wrap_enabled(self, enabled: bool) -> None:
        """Toggle soft-wrapping of editor lines."""

        self._word_wrap_enabled = bool(enabled)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth if self._word_wrap_enabled else QPlainTextEdit.NoWrap)

    def word_wrap_enabled(self) -> bool:
        return self._word_wrap_enabled

    def _update_document_path(self, path: Path | None) -> None:
        if path == self.path:
            return

        self.path = path
        self._lsp_document_opened = False
        self._document_version = 0
        self._update_language_for_context(force=True)

    def set_path(self, path: Path | None) -> None:
        """Public helper for updating the file path and language mapping."""
        self._update_document_path(path)

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
        self._layout_find_bar()

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

    def _layout_find_bar(self) -> None:
        if not self.find_bar.isVisible():
            return
        bar_height = self.find_bar.sizeHint().height()
        bar_width = min(self.width() - 20, 640)
        rect = self.contentsRect()
        x_pos = rect.right() - bar_width - 8
        y_pos = rect.bottom() - bar_height - 8
        self.find_bar.setGeometry(x_pos, y_pos, bar_width, bar_height)

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
        # VS Code Dark+ gutter background
        gutter_bg = self.theme.editor_color("gutter_background") if self.theme else QColor(30, 30, 30)
        painter.fillRect(event.rect(), gutter_bg)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        # Get current line number for highlighting
        current_line = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                # VS Code Dark+ line number colors: active vs inactive
                if block_number == current_line:
                    line_color = self.theme.editor_color("active_line_number") if self.theme else QColor(198, 198, 198)
                else:
                    line_color = self.theme.editor_color("line_number") if self.theme else QColor(133, 133, 133)
                painter.setPen(line_color)
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    number,
                )
                if self.path:
                    bp = self.breakpoints.get(str(self.path), block_number)
                    if bp:
                        radius = 5
                        color = QColor(200, 80, 80) if bp.enabled else QColor(110, 110, 110)
                        painter.setBrush(color)
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

        # Vertical divider between gutter and code area - VS Code Dark+ style
        gutter_right = self.line_number_area.width() - 1
        divider_color = self.theme.editor_color("gutter_divider") if self.theme else QColor(45, 45, 48)
        painter.setPen(divider_color)
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
            self.breakpoints.toggle_line(str(self.path), block.blockNumber())
            self.line_number_area.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        self._paint_indent_guides()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        multi_modifier = Qt.AltModifier if self._multi_cursor_modifier == "alt" else Qt.ControlModifier
        if self._column_selection_enabled and event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.position().toPoint())
            self._column_anchor = (cursor.blockNumber(), cursor.positionInBlock())
            self.setTextCursor(cursor)
            self._extra_cursors.clear()
            self._highlight_current_line()
            return
        if event.modifiers() & multi_modifier:
            cursor = self.cursorForPosition(event.position().toPoint())
            self._extra_cursors.append(cursor)
            self._highlight_current_line()
            return
        super().mousePressEvent(event)
        self._column_anchor = None
        self._extra_cursors.clear()
        self._highlight_current_line()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        """Track mouse position and trigger hover after 300ms delay."""
        if self._column_selection_enabled and self._column_anchor:
            cursor = self.cursorForPosition(event.position().toPoint())
            self._update_column_selection(cursor)
            return
        super().mouseMoveEvent(event)
        self._hover_position = event.position().toPoint()
        # Restart timer on every mouse movement
        if self._hover_timer.isActive():
            self._hover_timer.stop()
        self._hover_timer.start()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        super().mouseReleaseEvent(event)
        if self._column_selection_enabled and event.button() == Qt.MouseButton.LeftButton:
            self._column_anchor = None

    # File operations
    def _load_file(self, path: Path) -> None:
        self._loading_document = True
        self._update_document_path(path)
        try:
            with path.open("r", encoding="utf-8") as handle:
                self.setPlainText(handle.read())
        finally:
            self._loading_document = False

        # Reset modified flag after loading so autosave prompts only reflect
        # changes made after the document is opened.
        self.document().setModified(False)

        # Explicitly rebuild token cache to ensure syntax highlighting is applied immediately
        # after loading. This is necessary because the highlighter is created before the file
        # is loaded, and setPlainText() may not reliably trigger the contentsChange signal
        # during initial setup.
        if hasattr(self, '_highlighter') and self._highlighter:
            self._highlighter._token_cache_revision = -1
            self._highlighter._rebuild_token_cache()

    def save(self) -> None:
        if not self.path:
            return
        with self.path.open("w", encoding="utf-8") as handle:
            handle.write(self.toPlainText())
        # Saving the document should clear the dirty flag
        self.document().setModified(False)

    def is_dirty(self) -> bool:
        """Return True if the editor has unsaved changes."""

        return bool(self.document().isModified())

    # Indentation helpers
    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.matches(QKeySequence.Find):
            self.show_find_bar()
            return
        if event.matches(QKeySequence.Replace):
            self.show_find_bar(replace=True)
            return
        if event.matches(QKeySequence.FindNext):
            self.find_next()
            return
        if event.matches(QKeySequence.FindPrevious):
            self.find_previous()
            return
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Slash:
            self.toggle_line_comment()
            return
        if event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier) and event.key() == Qt.Key_A:
            self.toggle_block_comment()
            return
        if event.modifiers() == (Qt.ControlModifier | Qt.AltModifier) and event.key() == Qt.Key_E:
            self.expand_emmet_selection()
            return

        # Handle completion widget navigation
        if self.completion_widget.isVisible():
            if event.key() == Qt.Key_Down:
                self.completion_widget.select_next()
                return
            elif event.key() == Qt.Key_Up:
                self.completion_widget.select_previous()
                return
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.completion_widget.accept_current()
                return
            elif event.key() == Qt.Key_Tab:
                # Tab accepts completion and starts snippet navigation if available
                self.completion_widget.accept_current()
                return
            elif event.key() == Qt.Key_Escape:
                self.completion_widget.hide()
                return
            # Allow typing to filter completions
            elif event.text() and event.text().isprintable():
                super().keyPressEvent(event)
                self._trigger_auto_completion(force=False)
                return

        # Handle snippet tab navigation
        if event.key() == Qt.Key_Tab and not event.modifiers():
            if self.snippet_manager.active_snippet:
                if self.snippet_manager.jump_to_next_tab_stop():
                    return
                # No more tab stops, exit snippet mode and continue
                self.snippet_manager.cancel_snippet()

        # Handle snippet escape
        if event.key() == Qt.Key_Escape and self.snippet_manager.active_snippet:
            self.snippet_manager.cancel_snippet()
            return

        # Trigger completions with Ctrl+Space
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key_Space:
            self._request_completions()
            return

        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_K:
            self._request_hover()
            return
        if event.key() == Qt.Key_Escape and self._extra_cursors:
            self._extra_cursors.clear()
            self._highlight_current_line()
            return

        # Handle auto-closing brackets
        if self._auto_close_brackets and event.text() and not event.modifiers():
            char = event.text()
            cursor = self.textCursor()

            # Check if typing a closing bracket that's already there (skip over it)
            if char in self._bracket_pairs.values():
                next_char = self._get_next_char(cursor)
                if next_char == char:
                    cursor.movePosition(QTextCursor.MoveOperation.Right)
                    self.setTextCursor(cursor)
                    return

            # Auto-close opening brackets
            if char in self._bracket_pairs:
                closing_char = self._bracket_pairs[char]

                # If there's a selection, wrap it
                if cursor.hasSelection():
                    selected_text = cursor.selectedText()
                    cursor.insertText(char + selected_text + closing_char)
                    # Move cursor before closing bracket
                    pos = cursor.position()
                    cursor.setPosition(pos - 1)
                    self.setTextCursor(cursor)
                    return
                else:
                    # For quotes, check if we should close them
                    if char in ('"', "'"):
                        # Don't auto-close quotes in the middle of a word
                        prev_char = self._get_prev_char(cursor)
                        next_char = self._get_next_char(cursor)
                        if prev_char.isalnum() or next_char.isalnum():
                            # Let the normal behavior happen
                            super().keyPressEvent(event)
                            return

                    # Insert the pair
                    cursor.insertText(char + closing_char)
                    # Move cursor between the pair
                    cursor.movePosition(QTextCursor.MoveOperation.Left)
                    self.setTextCursor(cursor)
                    return

        # Handle backspace for auto-paired brackets
        if self._auto_close_brackets and event.key() == Qt.Key_Backspace:
            cursor = self.textCursor()
            if not cursor.hasSelection():
                prev_char = self._get_prev_char(cursor)
                next_char = self._get_next_char(cursor)
                # Check if we're between a bracket pair
                if prev_char in self._bracket_pairs and self._bracket_pairs[prev_char] == next_char:
                    # Delete both brackets
                    cursor.deletePreviousChar()
                    cursor.deleteChar()
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

        # Call super to handle the key event first
        super().keyPressEvent(event)

        # Auto-trigger completions after typing
        if self._auto_trigger_enabled and self._intellisense_enabled:
            # Check if this was a printable character or trigger character
            if event.text():
                self._trigger_auto_completion()

    def _trigger_auto_completion(self, force: bool = False) -> None:
        """Trigger auto-completion with debouncing."""
        if not self._auto_trigger_enabled and not force:
            return

        # Get the character that was just typed
        cursor = self.textCursor()
        pos = cursor.position()

        # Get text before cursor to check for trigger characters
        cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, 1)
        last_char = cursor.selectedText()

        # Reset cursor position
        cursor = self.textCursor()

        # Check if this is a trigger character
        is_trigger_char = last_char in self._trigger_characters

        # Get current word prefix
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        prefix = cursor.selectedText()

        # Trigger completion if:
        # 1. It's a trigger character (immediate trigger)
        # 2. We have enough characters typed
        # 3. Force flag is set
        if is_trigger_char:
            # Immediate trigger for trigger characters
            self._completion_timer.stop()
            self._auto_request_completions()
        elif force or len(prefix) >= self._min_chars_for_completion:
            # Debounced trigger for regular typing
            if self._completion_timer.isActive():
                self._completion_timer.stop()
            self._completion_timer.start()
        else:
            # Hide completions if prefix is too short
            self.completion_widget.hide()

    def _auto_request_completions(self) -> None:
        """Auto-triggered completion request (called after debounce)."""
        # Don't trigger if already showing completions (to avoid flickering)
        # unless this is a new trigger
        self._request_completions()

    # Highlight current line and diagnostics
    def _highlight_current_line(self) -> None:
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            # VS Code Dark+ current line highlight color - subtle background overlay
            line_color = (
                self.theme.editor_color("current_line")
                if self.theme
                else QColor(0x2A, 0x2D, 0x2E)
            )
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
        color = (
            self.theme.editor_color("bracket_match")
            if self.theme
            else QColor(80, 120, 200, 120)
        )
        selection.format.setBackground(color)
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
            color = (
                self.theme.editor_color("multi_cursor")
                if self.theme
                else QColor(90, 90, 120, 80)
            )
            sel.format.setBackground(color)
            selections.append(sel)
        return selections

    def _sync_extra_cursors(self) -> None:
        synced: list[QTextCursor] = []
        for cursor in self._extra_cursors:
            clone = QTextCursor(self.document())
            clone.setPosition(cursor.anchor())
            clone.setPosition(cursor.position(), QTextCursor.MoveMode.KeepAnchor)
            synced.append(clone)
        self._extra_cursors = synced
        self._highlight_current_line()

    def _reset_selection_stack(self) -> None:
        if not self._suppress_stack_reset:
            self._selection_stack.clear()

    def _all_cursors(self) -> list[QTextCursor]:
        return [self.textCursor(), *self._extra_cursors]

    def _capture_selection_state(self) -> list[tuple[int, int]]:
        return [
            (cur.selectionStart(), cur.selectionEnd())
            if cur.hasSelection()
            else (cur.position(), cur.position())
            for cur in self._all_cursors()
        ]

    def _apply_selection_state(self, ranges: list[tuple[int, int]]) -> None:
        self._suppress_stack_reset = True
        try:
            self._extra_cursors = []
            for index, (start, end) in enumerate(ranges):
                doc_length = len(self.toPlainText())
                start = max(0, min(start, doc_length))
                end = max(0, min(end, doc_length))
                cursor = QTextCursor(self.document())
                cursor.setPosition(start)
                if end != start:
                    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                if index == 0:
                    self.setTextCursor(cursor)
                else:
                    self._extra_cursors.append(cursor)
            self._highlight_current_line()
        finally:
            self._suppress_stack_reset = False

    def _range_for_cursor(self, cursor: QTextCursor, *, line_fallback: bool = True) -> tuple[int, int]:
        if cursor.hasSelection():
            return (min(cursor.selectionStart(), cursor.selectionEnd()), max(cursor.selectionStart(), cursor.selectionEnd()))
        if line_fallback:
            block = cursor.block()
            return block.position(), block.position() + block.length()
        pos = cursor.position()
        return pos, pos

    def _string_range_for_cursor(self, cursor: QTextCursor) -> tuple[int, int] | None:
        block = cursor.block()
        text = block.text()
        col = cursor.positionInBlock()
        left_candidates = [(text.rfind("\"", 0, col), "\""), (text.rfind("'", 0, col), "'")]
        left_candidates = [(idx, ch) for idx, ch in left_candidates if idx != -1]
        if not left_candidates:
            return None
        left_idx, quote_char = max(left_candidates, key=lambda item: item[0])
        right_idx = text.find(quote_char, max(col, left_idx + 1))
        if right_idx == -1:
            return None
        start = block.position() + left_idx
        end = block.position() + right_idx + 1
        if not (start <= cursor.position() <= end):
            return None
        return start, end

    def _block_range_for_cursor(self, cursor: QTextCursor) -> tuple[int, int]:
        block = cursor.block()
        start_block = block
        while start_block.previous().isValid() and start_block.previous().text().strip():
            start_block = start_block.previous()
        end_block = block
        while end_block.next().isValid() and end_block.next().text().strip():
            end_block = end_block.next()
        return start_block.position(), end_block.position() + end_block.length()

    def _selection_levels_for_cursor(self, cursor: QTextCursor) -> list[tuple[int, int]]:
        levels: list[tuple[int, int]] = []

        word_cursor = QTextCursor(cursor)
        word_cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        if word_cursor.selectedText():
            levels.append((word_cursor.selectionStart(), word_cursor.selectionEnd()))

        string_range = self._string_range_for_cursor(cursor)
        if string_range:
            levels.append(string_range)

        line_cursor = QTextCursor(cursor)
        line_cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        levels.append((line_cursor.selectionStart(), line_cursor.selectionEnd()))

        levels.append(self._block_range_for_cursor(cursor))

        doc_cursor = QTextCursor(cursor)
        doc_cursor.select(QTextCursor.SelectionType.Document)
        levels.append((doc_cursor.selectionStart(), doc_cursor.selectionEnd()))
        return levels

    def _expand_range(self, cursor: QTextCursor) -> tuple[int, int]:
        levels = self._selection_levels_for_cursor(cursor)
        current = self._range_for_cursor(cursor, line_fallback=False)
        for idx, level in enumerate(levels):
            if level == current:
                return levels[min(idx + 1, len(levels) - 1)]
        return levels[0]

    def expand_selection(self) -> None:
        self._selection_stack.append(self._capture_selection_state())
        expanded = [self._expand_range(cur) for cur in self._all_cursors()]
        self._apply_selection_state(expanded)

    def shrink_selection(self) -> None:
        if not self._selection_stack:
            return
        previous = self._selection_stack.pop()
        self._apply_selection_state(previous)

    def _cursor_for_block_column(self, block_index: int, column: int) -> QTextCursor:
        block = self.document().findBlockByNumber(block_index)
        column = max(0, min(column, len(block.text())))
        cursor = QTextCursor(self.document())
        cursor.setPosition(block.position() + column)
        return cursor

    def _update_column_selection(self, target_cursor: QTextCursor) -> None:
        if not self._column_anchor:
            return
        anchor_line, anchor_col = self._column_anchor
        current_line = target_cursor.blockNumber()
        current_col = target_cursor.positionInBlock()
        line_start, line_end = sorted((anchor_line, current_line))
        col_start, col_end = sorted((anchor_col, current_col))
        ranges: list[tuple[int, int]] = []
        for line in range(line_start, line_end + 1):
            start_cursor = self._cursor_for_block_column(line, col_start)
            end_cursor = self._cursor_for_block_column(line, col_end)
            start_pos = start_cursor.position()
            end_pos = end_cursor.position()
            if end_pos == start_pos and col_end != col_start:
                end_cursor.movePosition(
                    QTextCursor.MoveOperation.Right,
                    QTextCursor.MoveMode.KeepAnchor,
                    col_end - col_start,
                )
                end_pos = end_cursor.position()
            ranges.append((min(start_pos, end_pos), max(start_pos, end_pos)))
        self._apply_selection_state(ranges)

    def toggle_column_selection(self, enabled: bool | None = None) -> None:
        self._column_selection_enabled = (not self._column_selection_enabled) if enabled is None else bool(enabled)
        if not self._column_selection_enabled:
            self._column_anchor = None
            self._extra_cursors.clear()
            self._highlight_current_line()

    def _merge_ranges(self, ranges: list[tuple[int, int]]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        if not ranges:
            return [], []
        sorted_ranges = sorted(ranges, key=lambda pair: pair[0])
        merged: list[list[int]] = [[sorted_ranges[0][0], sorted_ranges[0][1]]]
        for start, end in sorted_ranges[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1][1] = max(last_end, end)
            else:
                merged.append([start, end])
        merged_tuples = [(start, end) for start, end in merged]
        mapping: list[tuple[int, int]] = []
        for start, end in ranges:
            for merged_start, merged_end in merged_tuples:
                if merged_start <= start and end <= merged_end:
                    mapping.append((merged_start, merged_end))
                    break
            else:
                mapping.append((start, end))
        return merged_tuples, mapping

    def _selection_or_line_ranges(self) -> list[tuple[int, int]]:
        return [self._range_for_cursor(cur) for cur in self._all_cursors()]

    def _position_for_line(self, lines: list[str], line_index: int) -> int:
        return sum(len(line) for line in lines[:line_index])

    def _positions_for_lines(self, lines: list[str], start_line: int, end_line: int) -> tuple[int, int]:
        start_pos = self._position_for_line(lines, start_line)
        end_pos = self._position_for_line(lines, end_line + 1)
        return start_pos, end_pos

    def _apply_text_and_selections(self, new_text: str, selections: list[tuple[int, int]]) -> None:
        cursor = self.textCursor()
        cursor.beginEditBlock()
        self.setPlainText(new_text)
        cursor.endEditBlock()
        self._apply_selection_state(selections)
        self._selection_stack.clear()

    def duplicate_selections(self) -> None:
        ranges = self._selection_or_line_ranges()
        merged, mapping = self._merge_ranges(ranges)
        if not merged:
            return
        text = self.toPlainText()
        new_text = text
        insertion_map: dict[tuple[int, int], tuple[int, int]] = {}
        for start, end in sorted(merged, reverse=True):
            segment = text[start:end]
            new_text = new_text[:end] + segment + new_text[end:]
            insertion_map[(start, end)] = (end, end + len(segment))
        selections = [insertion_map[m] for m in mapping]
        self._apply_text_and_selections(new_text, selections)

    def copy_lines_up(self) -> None:
        ranges = self._selection_or_line_ranges()
        merged, mapping = self._merge_ranges(ranges)
        if not merged:
            return
        text = self.toPlainText()
        new_text = text
        insertion_map: dict[tuple[int, int], tuple[int, int]] = {}
        for start, end in sorted(merged, reverse=True):
            segment = text[start:end]
            new_text = new_text[:start] + segment + new_text[start:]
            insertion_map[(start, end)] = (start, start + len(segment))
        selections = [insertion_map[m] for m in mapping]
        self._apply_text_and_selections(new_text, selections)

    def copy_lines_down(self) -> None:
        ranges = self._selection_or_line_ranges()
        merged, mapping = self._merge_ranges(ranges)
        if not merged:
            return
        text = self.toPlainText()
        new_text = text
        insertion_map: dict[tuple[int, int], tuple[int, int]] = {}
        for start, end in sorted(merged, reverse=True):
            segment = text[start:end]
            new_text = new_text[:end] + segment + new_text[end:]
            insertion_map[(start, end)] = (end, end + len(segment))
        selections = [insertion_map[m] for m in mapping]
        self._apply_text_and_selections(new_text, selections)

    def _line_ranges_from_cursors(self) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        line_ranges: list[tuple[int, int]] = []
        for start, end in self._selection_or_line_ranges():
            start_block = self.document().findBlock(start)
            end_block = self.document().findBlock(max(start, end - 1))
            line_ranges.append((start_block.blockNumber(), end_block.blockNumber()))
        return self._merge_ranges(line_ranges)

    def move_lines_up(self) -> None:
        merged, mapping = self._line_ranges_from_cursors()
        lines = self.toPlainText().splitlines(keepends=True)
        if not merged or not lines:
            return
        new_lines = list(lines)
        new_locations: dict[tuple[int, int], tuple[int, int]] = {}
        for start_line, end_line in merged:
            if start_line == 0:
                new_locations[(start_line, end_line)] = (start_line, end_line)
                continue
            segment = new_lines[start_line : end_line + 1]
            del new_lines[start_line : end_line + 1]
            insert_pos = start_line - 1
            new_lines[insert_pos:insert_pos] = segment
            new_locations[(start_line, end_line)] = (insert_pos, insert_pos + len(segment) - 1)
        new_text = "".join(new_lines)
        selections = []
        for original_range in mapping:
            new_start, new_end = new_locations.get(original_range, original_range)
            selections.append(self._positions_for_lines(new_lines, new_start, new_end))
        self._apply_text_and_selections(new_text, selections)

    def move_lines_down(self) -> None:
        merged, mapping = self._line_ranges_from_cursors()
        lines = self.toPlainText().splitlines(keepends=True)
        if not merged or not lines:
            return
        new_lines = list(lines)
        new_locations: dict[tuple[int, int], tuple[int, int]] = {}
        for start_line, end_line in sorted(merged, reverse=True):
            if end_line >= len(new_lines) - 1:
                new_locations[(start_line, end_line)] = (start_line, end_line)
                continue
            segment = new_lines[start_line : end_line + 1]
            del new_lines[start_line : end_line + 1]
            insert_pos = min(len(new_lines), start_line + 1)
            new_lines[insert_pos:insert_pos] = segment
            new_locations[(start_line, end_line)] = (insert_pos, insert_pos + len(segment) - 1)
        new_text = "".join(new_lines)
        selections = []
        for original_range in mapping:
            new_start, new_end = new_locations.get(original_range, original_range)
            selections.append(self._positions_for_lines(new_lines, new_start, new_end))
        self._apply_text_and_selections(new_text, selections)

    def _clone_cursor_to_line(self, cursor: QTextCursor, target_line: int) -> QTextCursor:
        target_block = self.document().findBlockByNumber(target_line)
        base_block = cursor.block()
        column = cursor.positionInBlock()
        target_column = min(column, len(target_block.text()))
        new_cursor = QTextCursor(self.document())
        new_cursor.setPosition(target_block.position() + target_column)
        if cursor.hasSelection() and base_block.blockNumber() == self.document().findBlock(cursor.selectionEnd()).blockNumber():
            sel_start_col = cursor.selectionStart() - base_block.position()
            sel_end_col = cursor.selectionEnd() - base_block.position()
            start = target_block.position() + min(sel_start_col, len(target_block.text()))
            end = target_block.position() + min(sel_end_col, len(target_block.text()))
            new_cursor.setPosition(start)
            new_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        return new_cursor

    def _add_vertical_cursors(self, offset: int) -> None:
        new_cursors: list[QTextCursor] = []
        for cursor in self._all_cursors():
            target_line = cursor.block().blockNumber() + offset
            if target_line < 0 or target_line >= self.document().blockCount():
                continue
            new_cursors.append(self._clone_cursor_to_line(cursor, target_line))
        if not new_cursors:
            return
        self._extra_cursors.extend(new_cursors)
        self._highlight_current_line()

    def add_cursor_above(self) -> None:
        self._add_vertical_cursors(-1)

    def add_cursor_below(self) -> None:
        self._add_vertical_cursors(1)

    def add_cursors_to_line_ends(self) -> None:
        merged, _ = self._line_ranges_from_cursors()
        if not merged:
            return
        cursors: list[QTextCursor] = []
        for start_line, end_line in merged:
            for line in range(start_line, end_line + 1):
                block = self.document().findBlockByNumber(line)
                cursor = QTextCursor(self.document())
                cursor.setPosition(block.position() + len(block.text()))
                cursors.append(cursor)
        if not cursors:
            return
        self.setTextCursor(cursors[0])
        self._extra_cursors = cursors[1:]
        self._highlight_current_line()

    def _occurrence_text(self) -> str:
        cursor = self.textCursor()
        if cursor.hasSelection():
            return cursor.selectedText()
        word_cursor = QTextCursor(cursor)
        word_cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return word_cursor.selectedText()

    def _existing_ranges(self) -> set[tuple[int, int]]:
        ranges: set[tuple[int, int]] = set()
        for cursor in self._all_cursors():
            if cursor.hasSelection():
                ranges.add((min(cursor.selectionStart(), cursor.selectionEnd()), max(cursor.selectionStart(), cursor.selectionEnd())))
            else:
                pos = cursor.position()
                ranges.add((pos, pos))
        return ranges

    def _add_occurrence_cursor(self, direction: int) -> None:
        needle = self._occurrence_text()
        if not needle:
            return
        text = self.toPlainText()
        current_range = self._range_for_cursor(self.textCursor())
        start_pos = current_range[1] if direction > 0 else max(0, current_range[0] - 1)
        if direction > 0:
            index = text.find(needle, start_pos)
        else:
            index = text.rfind(needle, 0, start_pos)
        if index == -1:
            return
        new_range = (index, index + len(needle))
        if new_range in self._existing_ranges():
            return
        new_cursor = QTextCursor(self.document())
        new_cursor.setPosition(new_range[0])
        new_cursor.setPosition(new_range[1], QTextCursor.MoveMode.KeepAnchor)
        self._extra_cursors.append(new_cursor)
        self._highlight_current_line()

    def add_cursor_to_next_occurrence(self) -> None:
        self._add_occurrence_cursor(1)

    def add_cursor_to_previous_occurrence(self) -> None:
        self._add_occurrence_cursor(-1)

    def select_all_occurrences(self) -> None:
        needle = self._occurrence_text()
        if not needle:
            return
        text = self.toPlainText()
        ranges: list[tuple[int, int]] = []
        start = 0
        while True:
            index = text.find(needle, start)
            if index == -1:
                break
            ranges.append((index, index + len(needle)))
            start = index + len(needle)
        if not ranges:
            return
        self._apply_selection_state(ranges)

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
        if self._loading_document or self._semantic_request_pending:
            return

        # Only request if document content has actually changed
        current_revision = self.document().revision()
        if current_revision == self._last_semantic_revision:
            return

        language = self._language or self._language_for_context()
        if not (self.lsp_manager and self.path and language):
            self._highlighter.set_semantic_tokens([])
            self._last_semantic_revision = current_revision
            return

        if not self._lsp_document_opened:
            self._open_in_lsp()

        try:
            if self.lsp_manager.supports_semantic_tokens(self.path, language=language):
                if self.lsp_manager.request_semantic_tokens(
                    self.path,
                    callback=partial(self._apply_semantic_tokens, language),
                    range_params=self._visible_range_params(),
                    language=language,
                ):
                    self._semantic_request_pending = True
                    return
        except RecursionError:
            return

        # No semantic tokens available, but mark this revision as processed
        if language:
            self._semantic_legends.pop(language, None)
        self._highlighter.set_semantic_tokens([])
        self._last_semantic_revision = current_revision

    def _apply_semantic_tokens(self, language: str, result: dict, legend: list[str]) -> None:
        # Clear the pending flag
        self._semantic_request_pending = False

        # Check if highlighter still exists (may be deleted if editor closed)
        if not hasattr(self, '_highlighter') or self._highlighter is None:
            return

        if language != self._language:
            return

        self._semantic_legends[language] = legend or []
        active_legend = self._semantic_legends.get(language, [])

        tokens = SemanticTokenProvider.from_lsp(result, active_legend)
        if not tokens and self._semantic_provider:
            tokens = self._semantic_provider.custom_tokens(self.toPlainText())
        # set_semantic_tokens already calls rehighlight(), don't call it again
        self._highlighter.set_semantic_tokens(tokens)

        # Record the revision we just processed to avoid redundant requests
        self._last_semantic_revision = self.document().revision()

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

    def _request_hover_at_mouse(self) -> None:
        """Request hover info at the stored mouse position."""
        if not (self.lsp_manager and self.path and self._hover_position):
            return

        cursor = self.cursorForPosition(self._hover_position)
        position = {"line": cursor.blockNumber(), "character": cursor.columnNumber()}

        def _show_hover(message: dict) -> None:
            contents = message.get("result", {})
            value = ""
            if isinstance(contents, dict):
                value = contents.get("contents", "")
            elif isinstance(contents, str):
                value = contents
            if value and self._hover_position:
                # Show tooltip at the mouse position
                QToolTip.showText(self.mapToGlobal(self._hover_position), str(value))

        self.lsp_manager.request_hover(str(self.path), position, callback=_show_hover)

    def _request_completions(self) -> None:
        """Request completions from LSP at current cursor position."""
        if not (self.lsp_manager and self.path):
            return

        cursor = self.textCursor()
        position = {"line": cursor.blockNumber(), "character": cursor.columnNumber()}

        # Get the current word prefix for filtering
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        prefix = cursor.selectedText()

        def _show_completions(message: dict) -> None:
            result = message.get("result", {})
            items = []

            # Handle both CompletionList and list of CompletionItems
            if isinstance(result, dict):
                items = result.get("items", [])
            elif isinstance(result, list):
                items = result

            if items:
                self.completion_widget.show_completions(items, prefix)

        self.lsp_manager.request_completions(str(self.path), position, callback=_show_completions)

    def _get_prev_char(self, cursor: QTextCursor) -> str:
        """Get the character before the cursor position."""
        if cursor.position() == 0:
            return ""
        prev_cursor = QTextCursor(cursor)
        prev_cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, 1)
        return prev_cursor.selectedText()

    def _get_next_char(self, cursor: QTextCursor) -> str:
        """Get the character after the cursor position."""
        if cursor.atEnd():
            return ""
        next_cursor = QTextCursor(cursor)
        next_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
        return next_cursor.selectedText()

    # Navigation helpers -------------------------------------------------
    def _record_position_for_history(self, initial: bool = False) -> None:
        if self._navigating:
            return
        cursor = self.textCursor()
        location = (cursor.blockNumber(), cursor.positionInBlock())
        if self._nav_back_stack and self._nav_back_stack[-1] == location and not initial:
            return
        self._nav_back_stack.append(location)
        self._nav_back_stack = self._nav_back_stack[-200:]
        if not initial:
            self._nav_forward_stack.clear()
        self.navigationStateChanged.emit(self.can_go_back(), self.can_go_forward())

    def _record_cursor_history(self) -> None:
        self._record_position_for_history(initial=False)

    def _record_edit_location(self) -> None:
        cursor = self.textCursor()
        location = (cursor.blockNumber(), cursor.positionInBlock())
        if self._edit_locations and self._edit_locations[-1] == location:
            return
        self._edit_locations.append(location)
        self._edit_locations = self._edit_locations[-200:]
        self._edit_index = len(self._edit_locations) - 1
        self._last_edit_location = location
        self.editNavigationChanged.emit(self.has_previous_change(), self.has_next_change())

    def can_go_back(self) -> bool:
        return len(self._nav_back_stack) > 1

    def can_go_forward(self) -> bool:
        return bool(self._nav_forward_stack)

    def go_back(self) -> None:
        if not self.can_go_back():
            return
        current = self._nav_back_stack.pop()
        target = self._nav_back_stack[-1]
        self._nav_forward_stack.append(current)
        self._move_to_location(target)
        self.navigationStateChanged.emit(self.can_go_back(), self.can_go_forward())

    def go_forward(self) -> None:
        if not self.can_go_forward():
            return
        target = self._nav_forward_stack.pop()
        self._nav_back_stack.append(target)
        self._move_to_location(target)
        self.navigationStateChanged.emit(self.can_go_back(), self.can_go_forward())

    def go_to_last_edit(self) -> None:
        if not self._last_edit_location:
            return
        self._move_to_location(self._last_edit_location)

    def has_previous_change(self) -> bool:
        return self._edit_index is not None and self._edit_index > 0

    def has_next_change(self) -> bool:
        return self._edit_index is not None and self._edit_index < len(self._edit_locations) - 1

    def previous_change(self) -> None:
        if not self.has_previous_change():
            return
        assert self._edit_index is not None
        self._edit_index -= 1
        self._move_to_location(self._edit_locations[self._edit_index])
        self.editNavigationChanged.emit(self.has_previous_change(), self.has_next_change())

    def next_change(self) -> None:
        if not self.has_next_change():
            return
        assert self._edit_index is not None
        self._edit_index += 1
        self._move_to_location(self._edit_locations[self._edit_index])
        self.editNavigationChanged.emit(self.has_previous_change(), self.has_next_change())

    def go_to_line_column(self, line: int, column: int = 0) -> None:
        line = max(1, line)
        column = max(0, column)
        block = self.document().findBlockByNumber(line - 1)
        if not block.isValid():
            return
        position = block.position() + min(column, len(block.text()))
        self._set_cursor_position(position)

    def jump_to_matching_bracket(self) -> None:
        match_position = self._find_matching_bracket_position()
        if match_position is None:
            return
        self._set_cursor_position(match_position)

    def _move_to_location(self, location: tuple[int, int]) -> None:
        block_number, column = location
        block = self.document().findBlockByNumber(max(block_number, 0))
        if not block.isValid():
            return
        position = block.position() + min(column, len(block.text()))
        self._set_cursor_position(position)

    def _set_cursor_position(self, position: int) -> None:
        self._navigating = True
        cursor = self.textCursor()
        cursor.setPosition(max(0, min(position, len(self.toPlainText()))))
        self.setTextCursor(cursor)
        self.centerCursor()
        self._navigating = False

    def _find_matching_bracket_position(self) -> int | None:
        text = self.toPlainText()
        if not text:
            return None
        brackets = {'(': ')', '[': ']', '{': '}', ')': '(', ']': '[', '}': '{'}
        cursor = self.textCursor()
        pos = cursor.position()
        char = text[pos - 1] if pos > 0 and text[pos - 1] in brackets else (text[pos] if pos < len(text) and text[pos] in brackets else "")
        if not char:
            return None
        target = brackets[char]
        if char in "([{":
            depth = 1
            i = pos
            while i < len(text):
                c = text[i]
                if c == char:
                    depth += 1
                elif c == target:
                    depth -= 1
                    if depth == 0:
                        return i
                i += 1
        else:
            depth = 1
            i = pos - 2
            while i >= 0:
                c = text[i]
                if c == char:
                    depth += 1
                elif c == target:
                    depth -= 1
                    if depth == 0:
                        return i
                i -= 1
        return None

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
