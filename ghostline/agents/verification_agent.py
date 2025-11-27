"""Agent validating patches and suggesting alternatives."""
from __future__ import annotations

from ghostline.agents.base_agent import AgentResult, BaseAgent
from ghostline.semantic.graph import SemanticGraph


class VerificationAgent(BaseAgent):
    """Ensure proposed patches and plans are conflict-aware."""

    def __init__(self, graph: SemanticGraph | None = None, shared_context=None) -> None:
        super().__init__("verification", shared_context)
        self.graph = graph

    def run(self, task: str) -> AgentResult:
        conflicts: list[str] = []
        if self.graph:
            cycles = self.graph.find_cycles()
            if cycles:
                conflicts.append(f"Cycle detected affecting {len(cycles)} paths")
        suggestions = [
            "Run formatter before applying patches",
            "Schedule fast tests after refactors",
        ]
        summary = "Verification complete"
        if conflicts:
            summary += " with conflicts"
        return AgentResult(
            agent_name=self.name,
            success=not conflicts,
            summary=summary,
            conflicts=conflicts,
            insights=suggestions,
        )
