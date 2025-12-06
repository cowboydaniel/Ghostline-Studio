"""Editor UI helpers such as semantic token providers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .semantic_tokens import SemanticToken, SemanticTokenProvider

if TYPE_CHECKING:  # pragma: no cover - only used for static analysis
    from .EditorWidget import EditorWidget

__all__ = ["SemanticToken", "SemanticTokenProvider", "EditorWidget"]


def __getattr__(name: str):
    """Lazily import heavy editor widgets to avoid circular imports."""

    if name == "EditorWidget":
        from .EditorWidget import EditorWidget

        return EditorWidget
    raise AttributeError(f"module 'ghostline.ui.editor' has no attribute {name!r}")
