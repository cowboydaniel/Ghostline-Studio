"""Symbol search helpers leveraging the LSP manager."""
from __future__ import annotations

from dataclasses import dataclass
import ast
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
            return

        symbols = self._python_symbols(Path(path))
        callback(symbols)

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

        workspace_key = str(self.lsp.workspace_manager.current_workspace or "")
        client = self.lsp._get_client("python") or next(iter(self.lsp.clients.get(workspace_key, {}).values()), None)
        if client:
            request_id = client.send_request("workspace/symbol", {"query": query})
            self.lsp._pending[request_id] = _handle
            return

        root = self.lsp.workspace_manager.current_workspace
        if not root:
            callback([])
            return
        results: list[SymbolResult] = []
        for path in root.rglob("*.py"):
            for symbol in self._python_symbols(path):
                if query.lower() in symbol.name.lower():
                    results.append(symbol)
                    if len(results) >= 100:
                        callback(results)
                        return
        callback(results)

    def _python_symbols(self, path: Path) -> List[SymbolResult]:
        symbols: list[SymbolResult] = []
        if not path.exists():
            return symbols
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            return symbols

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef):  # type: ignore[override]
                symbols.append(SymbolResult(node.name, "function", str(path), node.lineno - 1))
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):  # type: ignore[override]
                symbols.append(SymbolResult(node.name, "function", str(path), node.lineno - 1))
                self.generic_visit(node)

            def visit_ClassDef(self, node: ast.ClassDef):  # type: ignore[override]
                symbols.append(SymbolResult(node.name, "class", str(path), node.lineno - 1))
                self.generic_visit(node)

        Visitor().visit(tree)
        return symbols
