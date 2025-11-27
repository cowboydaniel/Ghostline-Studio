"""Agent responsible for proposing and applying refactors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ghostline.agents.base_agent import AgentResult, BaseAgent
from ghostline.ai.planner import LongHorizonPlanner
from ghostline.ai.workspace_memory import WorkspaceMemory
from ghostline.semantic.graph import SemanticGraph


@dataclass
class PatchProposal:
    description: str
    files: list[str]
    risk: str = "medium"


class RefactorAgent(BaseAgent):
    """Suggest refactors and coordinate evolution plans."""

    def __init__(
        self,
        memory: WorkspaceMemory,
        graph: SemanticGraph,
        planner: LongHorizonPlanner | None = None,
        shared_context=None,
    ) -> None:
        super().__init__("refactor", shared_context)
        self.memory = memory
        self.graph = graph
        self.planner = planner or LongHorizonPlanner(memory, graph)

    def run(self, task: str) -> AgentResult:
        proposals = self._propose_from_task(task)
        roadmap = self.planner.forecast_moves()
        patches = [proposal.description for proposal in proposals]
        patches.extend([f"Roadmap: {card.title}" for card in roadmap])
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=f"Refactor proposals ready for '{task}'",
            patches=patches,
            insights=[card.summary for card in roadmap],
        )

    def _propose_from_task(self, task: str) -> list[PatchProposal]:
        """Create lightweight patch suggestions from semantic graph data."""

        hotspots = sorted(self.graph.module_churn().items(), key=lambda item: item[1], reverse=True)[:3]
        proposals: list[PatchProposal] = []
        for module, _ in hotspots:
            proposals.append(
                PatchProposal(
                    description=f"Split high-churn module {module} for task '{task}'",
                    files=[f"{module}.py"],
                    risk="high",
                )
            )
        if not proposals:
            proposals.append(PatchProposal(description=f"Codemod sweep aligned to '{task}'", files=[]))
        return proposals

    def propose_evolution_branches(self, themes: Iterable[str]) -> list[str]:
        branches: list[str] = []
        for theme in themes:
            branches.append(f"evolve/{theme.replace(' ', '_').lower()}")
        return branches
