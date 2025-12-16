"""Shared syntax highlighting helpers and language-specific lexers."""
from __future__ import annotations

import re
from typing import Iterable, List, Pattern

from PySide6.QtGui import QFont, QTextCharFormat, QTextDocument, QSyntaxHighlighter

from ghostline.core.theme import ThemeManager
from ghostline.ui.editor.semantic_tokens import SemanticToken, SemanticTokenProvider


class RegexHighlighter(QSyntaxHighlighter):
    """Base class for regex-driven syntax highlighters with semantic overlays."""

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
        self.rules: list[tuple[Pattern[str], QTextCharFormat]] = []
        self._block_comment_tokens: tuple[str, str] | None = None
        self._semantic_tokens: dict[int, list[SemanticToken]] = {}
        self._comment_format = self._fmt("comment")

    def _fmt(self, color_key: str, *, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(self.theme.syntax_color(color_key))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        return fmt

    def add_keyword_rule(self, keywords: Iterable[str], fmt: QTextCharFormat) -> None:
        pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b"
        self.add_rule(pattern, fmt)

    def add_rule(self, pattern: str, fmt: QTextCharFormat) -> None:
        self.rules.append((re.compile(pattern), fmt))

    def set_block_comment(self, start: str, end: str) -> None:
        self._block_comment_tokens = (start, end)

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
        self.setCurrentBlockState(0)
        block_number = self.currentBlock().blockNumber()

        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                if end > start:
                    self.setFormat(start, end - start, fmt)

        self._apply_block_comments(text)

        for token in self._semantic_tokens.get(block_number, []):
            fmt = self._semantic_format(token.token_type)
            self.setFormat(token.start, token.length, fmt)

    def _apply_block_comments(self, text: str) -> None:
        if not self._block_comment_tokens:
            return

        start_token, end_token = self._block_comment_tokens
        start_index = 0 if self.previousBlockState() == 1 else text.find(start_token)

        while start_index >= 0:
            end_index = text.find(end_token, start_index + len(start_token))
            if end_index == -1:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + len(end_token)
            if comment_length > 0:
                self.setFormat(start_index, comment_length, self._comment_format)
            if end_index == -1:
                break
            start_index = text.find(start_token, start_index + comment_length)


class TypeScriptHighlighter(RegexHighlighter):
    """Highlighter for TypeScript and JavaScript files."""

    def __init__(
        self,
        document: QTextDocument,
        theme: ThemeManager | None,
        *,
        token_provider: SemanticTokenProvider | None = None,
    ) -> None:
        super().__init__(document, theme, token_provider=token_provider)
        self._build_rules()

    def _build_rules(self) -> None:
        keyword_fmt = self._fmt("keyword")
        string_fmt = self._fmt("string")
        number_fmt = self._fmt("number")
        builtin_fmt = self._fmt("builtin")
        decorator_fmt = self._fmt("decorator")
        type_fmt = self._fmt("typehint")

        keywords = {
            "abstract",
            "any",
            "as",
            "async",
            "await",
            "boolean",
            "break",
            "case",
            "catch",
            "class",
            "const",
            "continue",
            "debugger",
            "default",
            "delete",
            "do",
            "else",
            "enum",
            "export",
            "extends",
            "false",
            "finally",
            "for",
            "from",
            "function",
            "get",
            "if",
            "implements",
            "import",
            "in",
            "instanceof",
            "interface",
            "keyof",
            "let",
            "module",
            "namespace",
            "new",
            "null",
            "number",
            "object",
            "package",
            "private",
            "protected",
            "public",
            "readonly",
            "require",
            "return",
            "set",
            "static",
            "string",
            "super",
            "switch",
            "symbol",
            "this",
            "throw",
            "true",
            "try",
            "type",
            "typeof",
            "undefined",
            "var",
            "void",
            "while",
            "with",
            "yield",
        }

        builtins = {
            "Array",
            "Boolean",
            "Date",
            "JSON",
            "Map",
            "Math",
            "Number",
            "Object",
            "Promise",
            "RegExp",
            "Set",
            "String",
            "Symbol",
        }

        self.add_keyword_rule(keywords, keyword_fmt)
        self.add_rule(r"//[^\n]*", self._comment_format)
        self.set_block_comment("/*", "*/")
        self.add_rule(r"'(?:[^'\\]|\\.)*'", string_fmt)
        self.add_rule(r'"(?:[^"\\]|\\.)*"', string_fmt)
        self.add_rule(r"(?s)`(?:[^`\\]|\\.)*`", string_fmt)
        self.add_rule(r"\b0[xob][0-9a-fA-F]+\b|\b\d+(?:\.\d+)?(?:e[+-]?\d+)?\b", number_fmt)
        self.add_keyword_rule(builtins, builtin_fmt)
        self.add_rule(r"@[_A-Za-z][\w.]*", decorator_fmt)
        self.add_rule(r"\b[A-Z][A-Za-z0-9_]*\b", type_fmt)


class CCppHighlighter(RegexHighlighter):
    """Highlighter for C and C++ source files."""

    def __init__(
        self,
        document: QTextDocument,
        theme: ThemeManager | None,
        *,
        token_provider: SemanticTokenProvider | None = None,
    ) -> None:
        super().__init__(document, theme, token_provider=token_provider)
        self._build_rules()

    def _build_rules(self) -> None:
        keyword_fmt = self._fmt("keyword")
        string_fmt = self._fmt("string")
        number_fmt = self._fmt("number")
        type_fmt = self._fmt("typehint")
        decorator_fmt = self._fmt("decorator")

        keywords = {
            "alignas",
            "alignof",
            "asm",
            "auto",
            "bool",
            "break",
            "case",
            "catch",
            "char",
            "class",
            "const",
            "constexpr",
            "continue",
            "decltype",
            "default",
            "delete",
            "do",
            "double",
            "else",
            "enum",
            "explicit",
            "export",
            "extern",
            "float",
            "for",
            "friend",
            "goto",
            "if",
            "inline",
            "int",
            "long",
            "mutable",
            "namespace",
            "new",
            "noexcept",
            "nullptr",
            "operator",
            "override",
            "private",
            "protected",
            "public",
            "register",
            "reinterpret_cast",
            "return",
            "short",
            "signed",
            "sizeof",
            "static",
            "static_cast",
            "struct",
            "switch",
            "template",
            "this",
            "thread_local",
            "throw",
            "try",
            "typedef",
            "typename",
            "union",
            "unsigned",
            "using",
            "virtual",
            "void",
            "volatile",
            "while",
        }

        self.add_keyword_rule(keywords, keyword_fmt)
        self.add_rule(r"//[^\n]*", self._comment_format)
        self.set_block_comment("/*", "*/")
        self.add_rule(r"'(?:[^'\\]|\\.)'", string_fmt)
        self.add_rule(r'"(?:[^"\\]|\\.)*"', string_fmt)
        self.add_rule(r"\b0[xob][0-9A-Fa-f]+\b|\b\d+(?:\.\d+)?(?:e[+-]?\d+)?\b", number_fmt)
        self.add_rule(r"\b[A-Z][A-Za-z0-9_]*\b", type_fmt)
        self.add_rule(r"^\s*#\s*\w+", decorator_fmt)


class JavaHighlighter(RegexHighlighter):
    """Highlighter for Java source files."""

    def __init__(
        self,
        document: QTextDocument,
        theme: ThemeManager | None,
        *,
        token_provider: SemanticTokenProvider | None = None,
    ) -> None:
        super().__init__(document, theme, token_provider=token_provider)
        self._build_rules()

    def _build_rules(self) -> None:
        keyword_fmt = self._fmt("keyword")
        string_fmt = self._fmt("string")
        number_fmt = self._fmt("number")
        decorator_fmt = self._fmt("decorator")
        type_fmt = self._fmt("typehint")

        keywords = {
            "abstract",
            "assert",
            "boolean",
            "break",
            "byte",
            "case",
            "catch",
            "char",
            "class",
            "const",
            "continue",
            "default",
            "do",
            "double",
            "else",
            "enum",
            "extends",
            "final",
            "finally",
            "float",
            "for",
            "if",
            "implements",
            "import",
            "instanceof",
            "int",
            "interface",
            "long",
            "native",
            "new",
            "package",
            "private",
            "protected",
            "public",
            "return",
            "short",
            "static",
            "strictfp",
            "super",
            "switch",
            "synchronized",
            "this",
            "throw",
            "throws",
            "transient",
            "try",
            "void",
            "volatile",
            "while",
        }

        self.add_keyword_rule(keywords, keyword_fmt)
        self.add_rule(r"//[^\n]*", self._comment_format)
        self.set_block_comment("/*", "*/")
        self.add_rule(r"'(?:[^'\\]|\\.)'", string_fmt)
        self.add_rule(r'"(?:[^"\\]|\\.)*"', string_fmt)
        self.add_rule(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[fFdDlL]?\b", number_fmt)
        self.add_rule(r"@[_A-Za-z][\w.]*", decorator_fmt)
        self.add_rule(r"\b[A-Z][A-Za-z0-9_]*\b", type_fmt)


class RustHighlighter(RegexHighlighter):
    """Highlighter for Rust source files."""

    def __init__(
        self,
        document: QTextDocument,
        theme: ThemeManager | None,
        *,
        token_provider: SemanticTokenProvider | None = None,
    ) -> None:
        super().__init__(document, theme, token_provider=token_provider)
        self._build_rules()

    def _build_rules(self) -> None:
        keyword_fmt = self._fmt("keyword")
        string_fmt = self._fmt("string")
        number_fmt = self._fmt("number")
        macro_fmt = self._fmt("decorator")
        type_fmt = self._fmt("typehint")

        keywords = {
            "as",
            "async",
            "await",
            "break",
            "const",
            "continue",
            "crate",
            "dyn",
            "else",
            "enum",
            "extern",
            "false",
            "fn",
            "for",
            "if",
            "impl",
            "in",
            "let",
            "loop",
            "match",
            "mod",
            "move",
            "mut",
            "pub",
            "ref",
            "return",
            "self",
            "Self",
            "static",
            "struct",
            "super",
            "trait",
            "true",
            "type",
            "unsafe",
            "use",
            "where",
            "while",
            "yield",
        }

        self.add_keyword_rule(keywords, keyword_fmt)
        self.add_rule(r"//[^\n]*", self._comment_format)
        self.set_block_comment("/*", "*/")
        self.add_rule(r"(?s)r#*\".*?\"#*", string_fmt)
        self.add_rule(r'"(?:[^"\\]|\\.)*"', string_fmt)
        self.add_rule(r"'(?:[^'\\]|\\.)'", string_fmt)
        self.add_rule(r"\b0[xob][0-9A-Fa-f]+\b|\b\d+(?:\.\d+)?(?:e[+-]?\d+)?\b", number_fmt)
        self.add_rule(r"\b[A-Z][A-Za-z0-9_]*\b", type_fmt)
        self.add_rule(r"\b\w+!", macro_fmt)
        self.add_rule(r"'[_A-Za-z][\w]*", macro_fmt)
        self.add_rule(r"#\[[^\]]*\]", macro_fmt)


__all__ = [
    "RegexHighlighter",
    "TypeScriptHighlighter",
    "CCppHighlighter",
    "JavaHighlighter",
    "RustHighlighter",
]
