"""Semantic indexing orchestrator."""
from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Callable, Iterable

from ghostline.core.threads import BackgroundWorkers
from ghostline.semantic.graph import GraphEdge, GraphNode, SemanticGraph

logger = logging.getLogger(__name__)


class SemanticIndexManager:
    """Builds and updates a semantic graph of the workspace."""

    def __init__(self, workspace_provider: Callable[[], str | None], workers: BackgroundWorkers | None = None) -> None:
        self.workspace_provider = workspace_provider
        self.workers = workers or BackgroundWorkers()
        self.graph = SemanticGraph()
        self._observers: list[Callable[[Path], None]] = []
        self._recent_paths: list[Path] = []

    def register_observer(self, callback: Callable[[Path], None]) -> None:
        self._observers.append(callback)

    def _notify(self, path: Path) -> None:
        self._recent_paths.append(path)
        self._recent_paths = self._recent_paths[-20:]
        for cb in self._observers:
            cb(path)

    def reindex(self, paths: Iterable[str] | None = None) -> None:
        workspace = self.workspace_provider()
        targets = [Path(p) for p in paths] if paths else [Path(workspace)] if workspace else []
        for path in targets:
            if path.exists():
                self.workers.submit(f"semantic:{path}", self._index_path, path)

    def handle_file_event(self, event_type: str, path: str) -> None:
        """Schedule incremental updates based on filesystem events."""

        logger.debug("Semantic index received %s for %s", event_type, path)
        if event_type in {"modified", "created"}:
            self.reindex([path])
        elif event_type == "deleted":
            self._remove_file(Path(path))

    def _index_path(self, path: Path) -> None:
        if path.is_dir():
            for child in path.rglob("*.py"):
                self._index_file(child)
        else:
            self._index_file(path)
        self._notify(path)

    def _index_file(self, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Failed to read %s", path)
            return
        try:
            tree = ast.parse(content)
        except SyntaxError:
            logger.debug("Skipping non-parseable file %s", path)
            return
        visitor = _ASTVisitor(path, self.graph)
        visitor.visit(tree)

    def _remove_file(self, path: Path) -> None:
        nodes_to_remove = [node for node in self.graph.nodes() if node.file == path]
        for node in nodes_to_remove:
            self.graph._nodes.discard(node)
        self.graph._edges = {edge for edge in self.graph.edges() if edge.source.file != path and edge.target.file != path}

    def recent_paths(self) -> list[Path]:
        """Return recently indexed paths for UI and AI consumers."""

        return list(self._recent_paths)

    def shutdown(self) -> None:
        self.workers.shutdown()


class _ASTVisitor(ast.NodeVisitor):
    """Populate the semantic graph using a Python AST."""

    def __init__(self, file_path: Path, graph: SemanticGraph) -> None:
        self.file_path = file_path
        self.graph = graph

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # type: ignore[override]
        func_node = GraphNode(node.name, "function", self.file_path, (node.lineno, node.end_lineno))
        self.graph.add_node(func_node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # type: ignore[override]
        class_node = GraphNode(node.name, "class", self.file_path, (node.lineno, node.end_lineno))
        self.graph.add_node(class_node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # type: ignore[override]
        for alias in node.names:
            target = GraphNode(alias.name, "module", self.file_path)
            self.graph.add_edge(GraphEdge(self._module_node(), target, "imports"))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # type: ignore[override]
        module = node.module or ""
        target = GraphNode(module, "module", self.file_path)
        self.graph.add_edge(GraphEdge(self._module_node(), target, "imports"))

    def visit_Call(self, node: ast.Call) -> None:  # type: ignore[override]
        if isinstance(node.func, ast.Name):
            source = self._module_node()
            target = GraphNode(node.func.id, "function", self.file_path)
            self.graph.add_edge(GraphEdge(source, target, "calls"))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # type: ignore[override]
        for target in node.targets:
            if isinstance(target, ast.Name):
                variable = GraphNode(target.id, "variable", self.file_path, (node.lineno, node.end_lineno))
                self.graph.add_node(variable)
        self.generic_visit(node)

    def _module_node(self) -> GraphNode:
        return GraphNode(self.file_path.stem, "module", self.file_path)

