"""Semantic token support for the code editor.

This is a deliberately simple, safe implementation. It restores:

- A `SemanticToken` dataclass that the highlighter understands.
- A `SemanticTokenProvider` that can:
  * produce custom tokens (currently none)
  * translate LSP `documentSemanticTokens` into our flat tokens.

No regex wizardry, no recursion tricks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

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

    def __init__(self, language: str, theme: ThemeManager | None = None) -> None:
        self.language = language
        self.theme = theme
        self._formats = self._build_formats()

    def _build_formats(self) -> dict[str, QTextCharFormat]:
        """Precompute QTextCharFormats for known token types."""

        def _fmt(color: QColor, bold: bool = False) -> QTextCharFormat:
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            return fmt

        if not self.theme:
            return {}

        return {
            "namespace": _fmt(self.theme.syntax_color("import")),
            "type": _fmt(self.theme.syntax_color("typehint"), True),
            "class": _fmt(self.theme.syntax_color("class"), True),
            "enum": _fmt(self.theme.syntax_color("class"), True),
            "interface": _fmt(self.theme.syntax_color("class"), True),
            "struct": _fmt(self.theme.syntax_color("class"), True),
            "typeParameter": _fmt(self.theme.syntax_color("typehint")),
            "parameter": _fmt(self.theme.syntax_color("definition")),
            "variable": _fmt(self.theme.syntax_color("definition")),
            "property": _fmt(self.theme.syntax_color("definition")),
            "enumMember": _fmt(self.theme.syntax_color("literal")),
            "event": _fmt(self.theme.syntax_color("definition")),
            "function": _fmt(self.theme.syntax_color("function"), True),
            "method": _fmt(self.theme.syntax_color("function"), True),
            "macro": _fmt(self.theme.syntax_color("definition")),
            "keyword": _fmt(self.theme.syntax_color("keyword"), True),
            "modifier": _fmt(self.theme.syntax_color("keyword")),
            "comment": _fmt(self.theme.syntax_color("comment")),
            "string": _fmt(self.theme.syntax_color("string")),
            "number": _fmt(self.theme.syntax_color("number")),
            "regexp": _fmt(self.theme.syntax_color("string")),
            "operator": _fmt(self.theme.syntax_color("keyword")),
        }

    def format_for(self, token_type: str) -> QTextCharFormat:
        """Return a QTextCharFormat for a semantic token type."""
        if token_type in self._formats:
            return self._formats[token_type]
        if self.theme:
            return self._formats.setdefault("default", self._build_default_format())
        return QTextCharFormat()

    def _build_default_format(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        if self.theme:
            fmt.setForeground(self.theme.syntax_color("definition"))
        return fmt

    def custom_tokens(self, text: str) -> List[SemanticToken]:
        """Extra tokens beyond what LSP provides.

        For now this returns an empty list on purpose:
        - avoids heavy regex work
        - avoids any chance of re-entrancy or recursion during shutdown

        We can add smarter rules later (f-strings, TODO markers, etc)
        once the rest of the editor is rock solid.
        """
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


__all__ = ["SemanticToken", "SemanticTokenProvider"]


def semantic_tokens_from_lsp(
    result: Dict[str, Any],
    legend: List[str],
) -> List[SemanticToken]:
    """Small helper used by the editor to decode LSP tokens."""
    return SemanticTokenProvider.from_lsp(result, legend)
