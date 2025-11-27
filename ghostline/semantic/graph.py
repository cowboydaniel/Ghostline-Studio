"""Semantic graph representing workspace knowledge."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


@dataclass(frozen=True)
class GraphNode:
    """Node inside the semantic graph."""

    name: str
    kind: str
    file: Path
    span: Tuple[int, int] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    """Edge connecting two nodes with a semantic relationship."""

    source: GraphNode
    target: GraphNode
    relation: str


class SemanticGraph:
    """Lightweight in-memory knowledge graph built from workspace symbols."""

    def __init__(self) -> None:
        self._nodes: Set[GraphNode] = set()
        self._edges: Set[GraphEdge] = set()
        self._by_name: Dict[str, Set[GraphNode]] = {}

    def add_node(self, node: GraphNode) -> None:
        self._nodes.add(node)
        self._by_name.setdefault(node.name, set()).add(node)

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.source not in self._nodes:
            self.add_node(edge.source)
        if edge.target not in self._nodes:
            self.add_node(edge.target)
        self._edges.add(edge)

    def nodes(self) -> Set[GraphNode]:
        return set(self._nodes)

    def edges(self) -> Set[GraphEdge]:
        return set(self._edges)

    def references(self, symbol: str) -> Set[GraphNode]:
        return self._by_name.get(symbol, set())

    def neighbours(self, node: GraphNode, relation: str | None = None) -> List[GraphNode]:
        neighbours: list[GraphNode] = []
        for edge in self._edges:
            if edge.source == node and (relation is None or edge.relation == relation):
                neighbours.append(edge.target)
        return neighbours

    def definition_edges(self) -> Iterable[GraphEdge]:
        return [edge for edge in self._edges if edge.relation == "defines"]

    def import_edges(self) -> Iterable[GraphEdge]:
        return [edge for edge in self._edges if edge.relation == "imports"]

    def call_edges(self) -> Iterable[GraphEdge]:
        return [edge for edge in self._edges if edge.relation == "calls"]

    def find_cycles(self) -> list[list[GraphNode]]:
        """Return simple cycles using a depth-first traversal."""

        visited: Set[GraphNode] = set()
        stack: list[GraphNode] = []
        cycles: list[list[GraphNode]] = []

        def dfs(node: GraphNode) -> None:
            visited.add(node)
            stack.append(node)
            for neighbor in self.neighbours(node):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in stack:
                    index = stack.index(neighbor)
                    cycles.append(stack[index:].copy())
            stack.pop()

        for node in list(self._nodes):
            if node not in visited:
                dfs(node)
        return cycles

    def module_map(self) -> dict[str, set[str]]:
        """Return adjacency map for modules and their imports."""

        modules: dict[str, set[str]] = {}
        for edge in self.import_edges():
            src = edge.source.file.stem
            dst = edge.target.file.stem
            modules.setdefault(src, set()).add(dst)
        return modules

    def module_churn(self) -> dict[str, int]:
        """Estimate churn based on how many symbols a module defines."""

        churn: dict[str, int] = {}
        for node in self._nodes:
            if node.kind in {"function", "class"}:
                churn[node.file.stem] = churn.get(node.file.stem, 0) + 1
        return churn

    def pattern_fingerprint(self) -> str:
        """Summarise the graph for long-horizon planners."""

        modules = sorted(self.module_map().keys())
        cycles = ["->".join(node.name for node in cycle) for cycle in self.find_cycles()]
        imports = sorted({edge.target.name for edge in self.import_edges()})
        return "\n".join(
            [
                f"Modules: {', '.join(modules)}",
                f"Imports: {', '.join(imports)}",
                f"Cycles: {', '.join(cycles)}" if cycles else "Cycles: none",
            ]
        )

