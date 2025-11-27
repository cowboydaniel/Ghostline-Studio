"""Coordinator for Ghostline's internal multi-agent system."""
from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from ghostline.agents.analysis_agent import AnalysisAgent
from ghostline.agents.base_agent import AgentResult, BaseAgent, SharedContext
from ghostline.agents.refactor_agent import RefactorAgent
from ghostline.agents.verification_agent import VerificationAgent
from ghostline.ai.workspace_memory import WorkspaceMemory
from ghostline.semantic.graph import SemanticGraph

logger = logging.getLogger(__name__)


class AgentManager:
    """Coordinates specialised agents and aggregates their outputs."""

    def __init__(
        self,
        memory: WorkspaceMemory,
        graph: SemanticGraph,
        shared_context: SharedContext | None = None,
        max_workers: int = 4,
    ) -> None:
        self.memory = memory
        self.graph = graph
        self.shared_context = shared_context or _WorkspaceSharedContext(memory, graph)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.agents: list[BaseAgent] = [
            AnalysisAgent(graph, shared_context=self.shared_context),
            RefactorAgent(memory, graph, shared_context=self.shared_context),
            VerificationAgent(graph, shared_context=self.shared_context),
        ]
        self.workspace_active = False

    def register_agent(self, agent: BaseAgent) -> None:
        self.agents.append(agent)

    def coordinate(self, task: str) -> list[AgentResult]:
        """Run all agents in parallel for a given task description."""

        futures: list[Future[AgentResult]] = []
        for agent in self.agents:
            futures.append(self.executor.submit(agent.run, task))
        results: list[AgentResult] = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001
                logger.exception("Agent execution failed: %s", exc)
                results.append(
                    AgentResult(
                        agent_name="agent-error",
                        success=False,
                        summary=str(exc),
                        diagnostics={"exception": repr(exc)},
                    )
                )
        return results

    def propose_plan(self, task: str) -> dict[str, list[str]]:
        """Return a grouped summary of agent outputs for UI consumption."""

        results = self.coordinate(task)
        plan: dict[str, list[str]] = {"patches": [], "insights": [], "conflicts": []}
        for result in results:
            plan["patches"].extend(result.patches)
            plan["insights"].extend(result.insights)
            plan["conflicts"].extend(result.conflicts)
        return plan

    def set_workspace_active(self, active: bool) -> None:
        self.workspace_active = active

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False)

    def agent_status(self) -> list[str]:
        """Return brief status snapshots for the Multi-Agent Console UI."""

        state = "ready" if self.workspace_active else "idle"
        return [f"{agent.__class__.__name__}: {state}" for agent in self.agents]


class _WorkspaceSharedContext:
    """Share workspace memory and graph fingerprints across agents."""

    def __init__(self, memory: WorkspaceMemory, graph: SemanticGraph) -> None:
        self.memory = memory
        self.graph = graph

    def snapshot(self) -> dict[str, list[str] | str]:
        return {
            "memory": self.memory.snapshot(),
            "graph": self.graph.pattern_fingerprint(),
        }
