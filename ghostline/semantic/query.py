"""Semantic query helpers for navigation and analysis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ghostline.semantic.graph import GraphNode, SemanticGraph


@dataclass
class NavigationResult:
    """Describe a semantic navigation target."""

    label: str
    node: GraphNode


class SemanticQueryEngine:
    """Runs higher-level graph queries."""

    def __init__(self, graph: SemanticGraph) -> None:
        self.graph = graph

    def find_usages(self, symbol: str) -> list[GraphNode]:
        return list(self.graph.references(symbol))

    def architecture_map(self) -> dict[str, set[str]]:
        return self.graph.module_map()

    def find_cycles(self) -> list[list[GraphNode]]:
        return self.graph.find_cycles()

    def find_related_functions(self, target: str) -> list[NavigationResult]:
        results: list[NavigationResult] = []
        for node in self.graph.references(target):
            if node.kind == "function":
                results.append(NavigationResult(f"Function {node.name}", node))
        return results

    def search_by_kind(self, kind: str) -> Iterable[GraphNode]:
        return [node for node in self.graph.nodes() if node.kind == kind]

