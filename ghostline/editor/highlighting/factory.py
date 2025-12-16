"""Factory helpers for creating syntax highlighters and semantic providers."""
from __future__ import annotations

from typing import Tuple

from PySide6.QtGui import QSyntaxHighlighter, QTextDocument

from ghostline.core.theme import ThemeManager
from ghostline.ui.editor.semantic_tokens import SemanticTokenProvider

# NOTE: We keep the imports inside the factory function to avoid
# circular imports with the editor module during initialization.


def create_highlighting(
    document: QTextDocument,
    language: str | None,
    theme: ThemeManager | None = None,
) -> Tuple[QSyntaxHighlighter, SemanticTokenProvider]:
    """Create a syntax highlighter and semantic token provider for a language.

    Parameters
    ----------
    document:
        The QTextDocument the highlighter should attach to.
    language:
        Language identifier used to tailor providers/highlighters.
    theme:
        The theme manager to drive colors.
    """
    normalized = (language or "python").lower()
    semantic_provider = SemanticTokenProvider(normalized, theme=theme)

    # Lazy import to avoid circular dependency when CodeEditor pulls the factory.
    from ghostline.editor.code_editor import PythonHighlighter

    highlighter = PythonHighlighter(
        document,
        theme,
        token_provider=semantic_provider,
    )
    return highlighter, semantic_provider


__all__ = ["create_highlighting"]
