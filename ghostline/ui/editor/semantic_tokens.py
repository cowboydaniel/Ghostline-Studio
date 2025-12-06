"""Semantic token helpers for the Ghostline editor.

Provides a lightweight regex-based provider for Python code when the
language server does not expose semantic token support.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

from PySide6.QtGui import QColor, QTextCharFormat

from ghostline.core.theme import ThemeManager


# Precompiled pattern for Python f-strings.
# Use inline (?s) flag instead of passing re.DOTALL to avoid RegexFlag recursion issues on Python 3.12.
FSTRING_PATTERN = re.compile(r"(?s)f(['\"])(?:(?!\1).|\\.)*?\1")


@dataclass
class SemanticToken:
    """Describe a semantic token inside the editor document."""

    line: int
    start: int
    length: int
    token_type: str


class SemanticTokenProvider:
    """Generate semantic tokens from LSP data or a custom tokenizer."""

    _COLOR_KEYS: dict[str, str] = {
        "function": "function",
        "class": "class",
        "dunder": "dunder",
        "import": "import",
        "type": "typehint",
        "typehint": "typehint",
        "docstring": "literal",
        "interpolation": "literal",
        "literal": "literal",
    }

    def __init__(self, theme: ThemeManager | None = None) -> None:
        self.theme = theme
        self._format_cache: dict[str, QTextCharFormat] = {}

    # Formatting helpers
    def format_for(self, token_type: str) -> QTextCharFormat:
        """Return a text format for a given semantic token type."""

        color_key = self._COLOR_KEYS.get(token_type, "definition")
        if color_key in self._format_cache:
            return self._format_cache[color_key]
        fmt = QTextCharFormat()
        fmt.setForeground(self.theme.syntax_color(color_key) if self.theme else QColor())
        if token_type in {"function", "class"}:
            fmt.setFontWeight(600)
        self._format_cache[color_key] = fmt
        return fmt

    # LSP decoding
    @staticmethod
    def from_lsp(data: dict, legend: Sequence[str]) -> list[SemanticToken]:
        """Decode an LSP semanticTokens/full response."""

        values: Sequence[int] = data.get("data", []) if isinstance(data, dict) else []
        tokens: list[SemanticToken] = []
        line = 0
        char = 0
        for idx in range(0, len(values), 5):
            delta_line, delta_start, length, token_type_idx, _modifiers = values[idx : idx + 5]
            line += delta_line
            char = char + delta_start if delta_line == 0 else delta_start
            token_type = legend[token_type_idx] if token_type_idx < len(legend) else ""
            tokens.append(SemanticToken(line=line, start=char, length=length, token_type=token_type))
        return tokens

    # Custom tokenization for Python
    def custom_tokens(self, text: str) -> list[SemanticToken]:
        """Produce a basic semantic token set for Python code.

        This is intentionally defensive: if anything inside the regex-based
        logic misbehaves (including RecursionError on Python 3.12), we just
        fall back to no semantic tokens rather than crashing the editor.
        """
        try:
            tokens: list[SemanticToken] = []
            lines = text.splitlines(keepends=True)

            for lineno, line in enumerate(lines):
                tokens.extend(self._function_and_class_tokens(lineno, line))
                tokens.extend(self._dunder_tokens(lineno, line))
                tokens.extend(self._import_tokens(lineno, line))
                tokens.extend(self._type_hint_tokens(lineno, line))

            tokens.extend(self._docstring_tokens(text))
            tokens.extend(self._fstring_tokens(text))
            return tokens
        except RecursionError:
            return []
        except Exception:
            return []

    def _function_and_class_tokens(self, lineno: int, line: str) -> list[SemanticToken]:
        matches: list[SemanticToken] = []
        for pattern, token_type in (
            (r"^\s*def\s+([A-Za-z_][\w]*)", "function"),
            (r"^\s*class\s+([A-Za-z_][\w]*)", "class"),
        ):
            try:
                for match in re.finditer(pattern, line):
                    name = match.group(1)
                    matches.append(
                        SemanticToken(
                            line=lineno,
                            start=match.start(1),
                            length=len(name),
                            token_type=token_type,
                        )
                    )
            except RecursionError:
                # If the regex engine gets into trouble, skip this line.
                continue
            except Exception:
                continue
        return matches

    def _dunder_tokens(self, lineno: int, line: str) -> list[SemanticToken]:
        tokens: list[SemanticToken] = []
        for match in re.finditer(r"__\w+__", line):
            tokens.append(
                SemanticToken(line=lineno, start=match.start(), length=match.end() - match.start(), token_type="dunder")
            )
        return tokens

    def _import_tokens(self, lineno: int, line: str) -> list[SemanticToken]:
        tokens: list[SemanticToken] = []
        import_match = re.match(r"\s*(from\s+([\w\.]+)\s+import|import\s+(.+))", line)
        if not import_match:
            return tokens
        module_section = import_match.group(2) or import_match.group(3) or ""
        for module in [part.strip() for part in module_section.split(",") if part.strip()]:
            start = line.find(module)
            if start != -1:
                tokens.append(SemanticToken(line=lineno, start=start, length=len(module), token_type="import"))
        return tokens

    def _type_hint_tokens(self, lineno: int, line: str) -> list[SemanticToken]:
        tokens: list[SemanticToken] = []
        for pattern in (r":\s*([A-Za-z_][\w\.|\[\]]*)", r"->\s*([A-Za-z_][\w\.|\[\]]*)"):
            for match in re.finditer(pattern, line):
                hint = match.group(1)
                tokens.append(SemanticToken(line=lineno, start=match.start(1), length=len(hint), token_type="type"))
        return tokens

    def _docstring_tokens(self, text: str) -> list[SemanticToken]:
        tokens: list[SemanticToken] = []
        docstring_pattern = re.compile(r'("""|\'\'\')[\s\S]*?\1')
        for match in docstring_pattern.finditer(text):
            start, end = match.span()
            tokens.extend(self._split_multiline_token(start, end, "docstring", text))
        return tokens

    def _fstring_tokens(self, text: str):
        """Return semantic tokens for f-strings in the given text.

        This version uses a precompiled regex and avoids passing RegexFlag
        objects directly to re.compile, which was causing RecursionError
        on Python 3.12.
        """
        tokens = []
        try:
            for match in FSTRING_PATTERN.finditer(text):
                start = match.start()
                end = match.end()
                tokens.append(
                    SemanticToken(
                        start=start,
                        length=end - start,
                        token_type="stringInterpolation",
                        modifiers=[],
                    )
                )
        except RecursionError:
            # If the regex engine misbehaves, just skip f-string tokens
            return []
        except Exception:
            # Be defensive: never let highlighting crash the editor
            return []
        return tokens

    def _split_multiline_token(self, start: int, end: int, token_type: str, text: str) -> list[SemanticToken]:
        tokens: list[SemanticToken] = []
        running = 0
        for lineno, line in enumerate(text.splitlines(keepends=True)):
            line_start = running
            line_end = running + len(line)
            overlap_start = max(start, line_start)
            overlap_end = min(end, line_end)
            if overlap_start < overlap_end:
                tokens.append(
                    SemanticToken(
                        line=lineno,
                        start=overlap_start - line_start,
                        length=overlap_end - overlap_start,
                        token_type=token_type,
                    )
                )
            running = line_end
        return tokens
