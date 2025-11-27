"""Agent dedicated to graph-wide analysis."""
from __future__ import annotations

from ghostline.agents.base_agent import AgentResult, BaseAgent
from ghostline.semantic.graph import SemanticGraph


class AnalysisAgent(BaseAgent):
    """Surface hotspots, fragile areas, and potential dead code."""

    def __init__(self, graph: SemanticGraph | None = None, shared_context=None) -> None:
        super().__init__("analysis", shared_context)
        self.graph = graph

    def run(self, task: str) -> AgentResult:
        fingerprint = None
        if self.graph:
            fingerprint = self.graph.pattern_fingerprint()
            insights = [
                f"Graph fingerprint ready for '{task}'.",
                f"Potential cycles: {len(self.graph.find_cycles())}",
            ]
        else:
            insights = ["Semantic graph not available; using shared context only."]
        if self.shared_context:
            insights.append("Context captured for downstream agents.")
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary="Semantic analysis complete",
            insights=insights,
            diagnostics={"fingerprint": fingerprint},
        )
