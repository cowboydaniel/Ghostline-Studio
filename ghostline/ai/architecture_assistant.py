"""AI-driven architecture assistant stubs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ghostline.ai.ai_client import AIClient
from ghostline.semantic.query import SemanticQueryEngine


@dataclass
class ArchitectureInsight:
    title: str
    detail: str
    severity: str = "info"
    fix_hint: str | None = None


class ArchitectureAssistant:
    """Combines semantic graph data and AI hints for architecture guidance."""

    def __init__(self, client: AIClient, query: SemanticQueryEngine) -> None:
        self.client = client
        self.query = query

    def detect_code_smells(self) -> list[ArchitectureInsight]:
        cycles = self.query.find_cycles()
        insights: list[ArchitectureInsight] = []
        if cycles:
            formatted = ", ".join([" -> ".join([n.name for n in c]) for c in cycles])
            insights.append(
                ArchitectureInsight(
                    "Circular dependencies detected",
                    f"Potential cycles: {formatted}",
                    severity="warning",
                    fix_hint="Consider breaking imports or introducing interfaces.",
                )
            )
        unused_modules = [m for m, deps in self.query.architecture_map().items() if not deps]
        for module in unused_modules:
            insights.append(
                ArchitectureInsight(
                    f"Unused module {module}",
                    "No outbound imports detected; verify if this module is still needed.",
                    severity="info",
                )
            )
        return insights

    def suggest_boundaries(self) -> list[ArchitectureInsight]:
        prompt = "Suggest modular boundaries and layering for the current project."
        response = self.client.send(prompt)
        return [ArchitectureInsight("Module boundaries", response.text, severity="info")]

    def generate_sequence_diagram(self, function_name: str) -> str:
        related = self.query.find_related_functions(function_name)
        calls = "\n".join([f"{function_name} -> {r.node.name}" for r in related]) or "No calls recorded"
        return f"sequenceDiagram\n{calls}"

    def propose_refactors(self) -> Iterable[ArchitectureInsight]:
        prompt = "Provide a concise refactor plan with multi-file diffs for architecture improvements."
        response = self.client.send(prompt)
        return [ArchitectureInsight("Refactor plan", response.text, severity="info")]

