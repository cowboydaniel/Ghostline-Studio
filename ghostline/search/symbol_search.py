"""Symbol search helpers leveraging the LSP manager."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

from ghostline.lang.lsp_manager import LSPManager


@dataclass
class SymbolResult:
    name: str
    kind: str
    file: str
    line: int


class SymbolSearcher:
    def __init__(self, lsp: LSPManager) -> None:
        self.lsp = lsp

    def document_symbols(self, path: str, callback: Callable[[List[SymbolResult]], None]) -> None:
        def _handle(resp: dict) -> None:
            symbols = []
            for entry in resp.get("result", []) or []:
                rng = entry.get("range", entry.get("location", {}).get("range", {}))
                start = rng.get("start", {})
                symbols.append(SymbolResult(entry.get("name", ""), str(entry.get("kind", "")), path, start.get("line", 0)))
            callback(symbols)

        client = self.lsp._get_client(self.lsp._language_for_file(path) or "")
        if client:
            request_id = client.send_request(
                "textDocument/documentSymbol",
                {"textDocument": {"uri": Path(path).resolve().as_uri()}},
            )
            self.lsp._pending[request_id] = _handle

    def workspace_symbols(self, query: str, callback: Callable[[List[SymbolResult]], None]) -> None:
        def _handle(resp: dict) -> None:
            symbols = []
            for entry in resp.get("result", []) or []:
                loc = entry.get("location", {})
                uri = loc.get("uri", "")
                rng = loc.get("range", {})
                start = rng.get("start", {})
                symbols.append(SymbolResult(entry.get("name", ""), str(entry.get("kind", "")), uri.replace("file://", ""), start.get("line", 0)))
            callback(symbols)

        client = self.lsp._get_client("python") or next(iter(self.lsp.clients.get(self.lsp.workspace_manager.current_workspace or "", {}).values()), None)
        if client:
            request_id = client.send_request("workspace/symbol", {"query": query})
            self.lsp._pending[request_id] = _handle
