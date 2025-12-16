"""Semantic token support for the code editor.

This is a deliberately simple, safe implementation. It restores:

- A `SemanticToken` dataclass that the highlighter understands.
- A `SemanticTokenProvider` that can:
  * produce custom tokens using lightweight, language-aware overrides
  * translate LSP `documentSemanticTokens` into our flat tokens.

No regex wizardry, no recursion tricks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

from PySide6.QtGui import QColor, QFont, QTextCharFormat

from ghostline.core.theme import ThemeManager


@dataclass
class SemanticToken:
    line: int
    start: int
    length: int
    token_type: str


class SemanticTokenProvider:
    """Turn LSP semantic tokens plus optional custom rules into
    simple line based tokens for the syntax highlighter.
    """

    LANGUAGE_FORMAT_OVERRIDES: Mapping[str, Dict[str, tuple[str, bool] | str]] = {
        # Doc-comment tokens are often emitted separately from regular comments
        "python": {"comment.documentation": "comment"},
        "typescript": {"comment.documentation": "comment", "annotation": "decorator"},
        "rust": {"comment.documentation": "comment"},
    }

    def __init__(
        self,
        language: str,
        theme: ThemeManager | None = None,
        *,
        format_overrides: Mapping[str, tuple[str, bool] | str] | None = None,
        custom_token_factories: Mapping[str, Any] | None = None,
    ) -> None:
        self.language = language
        self.theme = theme or ThemeManager()
        self._format_overrides: dict[str, tuple[str, bool] | str] = {}
        self._format_overrides.update(self.LANGUAGE_FORMAT_OVERRIDES.get(language, {}))
        if format_overrides:
            self._format_overrides.update(format_overrides)
        self._custom_token_factory = None
        if custom_token_factories and language in custom_token_factories:
            self._custom_token_factory = custom_token_factories[language]
        elif language in self._default_custom_factories():
            self._custom_token_factory = self._default_custom_factories()[language]

        self._formats = self._build_formats()

    def _build_formats(self) -> dict[str, QTextCharFormat]:
        """Precompute QTextCharFormats for known token types.

        Maps LSP semantic tokens to VS Code Dark+ colors.
        """

        def _fmt(color: QColor, bold: bool = False) -> QTextCharFormat:
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            return fmt

        formats = {
            # Types, classes, interfaces → #4EC9B0 (cyan/teal)
            "namespace": _fmt(self.theme.syntax_color("import")),
            "type": _fmt(self.theme.syntax_color("class")),
            "class": _fmt(self.theme.syntax_color("class")),
            "enum": _fmt(self.theme.syntax_color("class")),
            "interface": _fmt(self.theme.syntax_color("class")),
            "struct": _fmt(self.theme.syntax_color("class")),
            "typeParameter": _fmt(self.theme.syntax_color("class")),

            # Functions and methods → #DCDCAA (yellow)
            "function": _fmt(self.theme.syntax_color("function")),
            "method": _fmt(self.theme.syntax_color("function")),

            # Variables, parameters, properties → #9CDCFE (light blue)
            "parameter": _fmt(self.theme.syntax_color("variable")),
            "variable": _fmt(self.theme.syntax_color("variable")),
            "property": _fmt(self.theme.syntax_color("variable")),

            # Constants and enum members → #4FC1FF (bright blue)
            "enumMember": _fmt(self.theme.syntax_color("constant")),
            "event": _fmt(self.theme.syntax_color("constant")),

            # Keywords and modifiers → #569CD6 (blue) or #C586C0 (magenta)
            "keyword": _fmt(self.theme.syntax_color("keyword")),
            "modifier": _fmt(self.theme.syntax_color("keyword")),
            "macro": _fmt(self.theme.syntax_color("decorator")),

            # Strings, numbers, comments
            "comment": _fmt(self.theme.syntax_color("comment")),
            "string": _fmt(self.theme.syntax_color("string")),
            "number": _fmt(self.theme.syntax_color("number")),
            "regexp": _fmt(self.theme.syntax_color("string")),

            # Operators → #D4D4D4 (default foreground)
            "operator": _fmt(self.theme.syntax_color("operator")),

            # Decorators → #C586C0 (magenta)
            "decorator": _fmt(self.theme.syntax_color("decorator")),
        }

        for token_type, override in self._format_overrides.items():
            if isinstance(override, QTextCharFormat):
                formats[token_type] = override
                continue
            color_key: str
            bold = False
            if isinstance(override, tuple):
                color_key, bold = override
            else:
                color_key = override
            formats[token_type] = _fmt(self.theme.syntax_color(color_key), bold=bold)

        return formats

    def format_for(self, token_type: str) -> QTextCharFormat:
        """Return a QTextCharFormat for a semantic token type."""
        if token_type in self._formats:
            return self._formats[token_type]
        return self._formats.setdefault("default", self._build_default_format())

    def _build_default_format(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        if self.theme:
            fmt.setForeground(self.theme.syntax_color("variable"))
        return fmt

    def custom_tokens(self, text: str) -> List[SemanticToken]:
        """Extra tokens beyond what LSP provides.

        For now this returns an empty list on purpose:
        - avoids heavy regex work
        - avoids any chance of re-entrancy or recursion during shutdown

        We can add smarter rules later (f-strings, TODO markers, etc)
        once the rest of the editor is rock solid.
        """
        if callable(self._custom_token_factory):
            return self._custom_token_factory(text)
        return []

    @staticmethod
    def from_lsp(result: Dict[str, Any], legend: List[str]) -> List[SemanticToken]:
        """Convert an LSP documentSemanticTokens result into SemanticToken objects.

        The LSP format is a flat integer array:

            [deltaLine, deltaStart, length, tokenType, tokenModifiers, ...]

        Values are relative to the previous token.
        """
        data = result.get("data") or []
        tokens: List[SemanticToken] = []

        line = 0
        col = 0

        it = iter(data)
        # Consume 5 ints at a time: dl, ds, len, type_idx, mods
        for delta_line, delta_start, length, token_type_idx, _mods in zip(it, it, it, it, it):
            delta_line = int(delta_line)
            delta_start = int(delta_start)
            length = int(length)
            token_type_idx = int(token_type_idx)

            line += delta_line
            if delta_line:
                col = 0
            col += delta_start

            if 0 <= token_type_idx < len(legend):
                token_type = legend[token_type_idx]
            else:
                token_type = "default"

            tokens.append(
                SemanticToken(
                    line=line,
                    start=col,
                    length=length,
                    token_type=token_type,
                )
            )

        return tokens

    @staticmethod
    def _default_custom_factories() -> dict[str, Any]:
        def decorator_tokens(text: str) -> list[SemanticToken]:
            tokens: list[SemanticToken] = []
            for line_no, line in enumerate(text.splitlines()):
                stripped = line.lstrip()
                if stripped.startswith("@"):  # Python, TS, etc.
                    start = len(line) - len(stripped)
                    tokens.append(
                        SemanticToken(
                            line=line_no,
                            start=start,
                            length=len(stripped.split()[0]),
                            token_type="decorator",
                        )
                    )
            return tokens

        def doc_comment_tokens(prefixes: tuple[str, ...]) -> Any:
            def _factory(text: str) -> list[SemanticToken]:
                tokens: list[SemanticToken] = []
                for line_no, line in enumerate(text.splitlines()):
                    stripped = line.lstrip()
                    for prefix in prefixes:
                        if stripped.startswith(prefix):
                            start = len(line) - len(stripped)
                            length = len(stripped)
                            tokens.append(
                                SemanticToken(
                                    line=line_no,
                                    start=start,
                                    length=length,
                                    token_type="comment.documentation",
                                )
                            )
                            break
                return tokens

            return _factory

        return {
            "python": decorator_tokens,
            "typescript": decorator_tokens,
            "rust": doc_comment_tokens(("//!", "///")),
        }


__all__ = ["SemanticToken", "SemanticTokenProvider"]


def semantic_tokens_from_lsp(
    result: Dict[str, Any],
    legend: List[str],
) -> List[SemanticToken]:
    """Small helper used by the editor to decode LSP tokens."""
    return SemanticTokenProvider.from_lsp(result, legend)
