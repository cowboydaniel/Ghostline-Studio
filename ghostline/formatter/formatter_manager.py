"""Auto-formatting integration."""
from __future__ import annotations

from pathlib import Path

from ghostline.lang.lsp_manager import LSPManager


class FormatterManager:
    def __init__(self, lsp_manager: LSPManager | None = None) -> None:
        self.lsp_manager = lsp_manager

    def format_document(self, path: Path | None, text: str) -> str:
        if not path:
            return self._cleanup_whitespace(text)
        formatted = self._format_via_lsp(path, text)
        return formatted if formatted is not None else self._cleanup_whitespace(text)

    def _format_via_lsp(self, path: Path, text: str) -> str | None:
        try:
            client = self.lsp_manager._get_client(self.lsp_manager._language_for_file(str(path)), "formatter") if self.lsp_manager else None
        except Exception:
            client = None
        if not client:
            return None
        try:
            response = client.send_request(
                "textDocument/formatting",
                {"textDocument": {"uri": path.resolve().as_uri()}, "options": {"tabSize": 4, "insertSpaces": True}},
            )
            if isinstance(response, dict) and "result" in response:
                edits = response.get("result") or []
                if edits:
                    return "\n".join([line.rstrip() for line in text.splitlines()])
        except Exception:
            return None
        return None

    def _cleanup_whitespace(self, text: str) -> str:
        return "\n".join(line.rstrip() for line in text.splitlines()) + ("\n" if text.endswith("\n") else "")
