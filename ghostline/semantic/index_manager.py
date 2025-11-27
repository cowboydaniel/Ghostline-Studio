"""Semantic indexing orchestrator."""
from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any, Callable, Iterable

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

    def record_runtime_event(self, observation: Any) -> None:
        """Merge runtime observations into the semantic graph."""

        try:
            self.graph.annotate_runtime(observation)
            path_value = getattr(observation, "path", None)
            if path_value:
                self._notify(Path(path_value))
        except Exception:  # noqa: BLE001
            logger.exception("Failed to merge runtime observation")

    def get_graph_snapshot(self) -> dict:
        """Return a lightweight, serializable snapshot of the semantic graph."""

        workspace = self.workspace_provider()
        root = Path(workspace) if workspace else None

        def _format_path(path: Path) -> str:
            if root:
                try:
                    return str(path.relative_to(root))
                except ValueError:
                    pass
            return str(path)

        def _add_node(
            collection: dict[str, dict], node_id: str, node_type: str, label: str, file_path: Path | None, span: tuple[int, int] | None
        ) -> dict[str, dict]:
            if node_id in collection:
                return collection
            collection[node_id] = {
                "id": node_id,
                "type": node_type,
                "label": label,
                "file": str(file_path) if file_path else None,
                "line": span[0] - 1 if span else None,
            }
            return collection

        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        edge_keys: set[tuple[str, str, str]] = set()
        files_seen: set[Path] = set()

        for node in self.graph.nodes():
            formatted_path = _format_path(node.file)
            file_id = f"file:{formatted_path}"
            if node.file not in files_seen:
                files_seen.add(node.file)
                _add_node(nodes, file_id, "file", node.file.name, node.file, None)

            module_id = f"module:{formatted_path}"
            _add_node(nodes, module_id, "module", node.file.stem, node.file, None)
            edge_key = (module_id, file_id, "contains")
            if edge_key not in edge_keys:
                edge_keys.add(edge_key)
                edges.append({"source": module_id, "target": file_id, "type": "contains"})

            if node.kind != "module":
                symbol_prefix = "func" if node.kind == "function" else node.kind
                symbol_id = f"{symbol_prefix}:{formatted_path}:{node.name}"
                _add_node(nodes, symbol_id, node.kind, node.name, node.file, node.span)
                symbol_edge_key = (file_id, symbol_id, "contains")
                if symbol_edge_key not in edge_keys:
                    edge_keys.add(symbol_edge_key)
                    edges.append({"source": file_id, "target": symbol_id, "type": "contains"})

        def _node_id_for(graph_node: GraphNode) -> str:
            formatted_path = _format_path(graph_node.file)
            if graph_node.kind == "module":
                return f"module:{formatted_path}"
            prefix = "func" if graph_node.kind == "function" else graph_node.kind
            return f"{prefix}:{formatted_path}:{graph_node.name}"

        for edge in self.graph.edges():
            src_id = _node_id_for(edge.source)
            tgt_id = _node_id_for(edge.target)
            if src_id not in nodes:
                _add_node(nodes, src_id, edge.source.kind, edge.source.name, edge.source.file, edge.source.span)
            if tgt_id not in nodes:
                _add_node(nodes, tgt_id, edge.target.kind, edge.target.name, edge.target.file, edge.target.span)
            edge_key = (src_id, tgt_id, edge.relation)
            if edge_key not in edge_keys:
                edge_keys.add(edge_key)
                edges.append({"source": src_id, "target": tgt_id, "type": edge.relation})

        return {"nodes": list(nodes.values()), "edges": edges}


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

