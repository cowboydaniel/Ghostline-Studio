"""Long-horizon planning agent for Ghostline Studio."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from ghostline.semantic.graph import SemanticGraph
from ghostline.ai.workspace_memory import WorkspaceMemory


@dataclass
class RoadmapCard:
    """Represents a proposed migration or refactor."""

    title: str
    summary: str
    difficulty: str = "medium"
    steps: list[str] = field(default_factory=list)
    related_modules: list[str] = field(default_factory=list)


class LongHorizonPlanner:
    """Learns the project's long-term shape and proposes migrations."""

    def __init__(self, memory: WorkspaceMemory, graph: SemanticGraph) -> None:
        self.memory = memory
        self.graph = graph
        self.cards: list[RoadmapCard] = []

    def analyse_history(self, commit_messages: Iterable[str]) -> None:
        """Store patterns from recent commits for predictive planning."""

        for message in commit_messages:
            self.memory.remember_pattern("commit_messages", message)
        self.memory.remember_pattern("graph_fingerprint", self.graph.pattern_fingerprint())

    def forecast_moves(self) -> list[RoadmapCard]:
        """Infer likely future refactors from semantic patterns."""

        churn = self.graph.module_churn()
        hotspots = sorted(churn.items(), key=lambda item: item[1], reverse=True)[:3]
        steps = [f"Audit high-churn module {name}" for name, _ in hotspots]
        card = RoadmapCard(
            title="Stabilise high-churn modules",
            summary="Modules with heavy symbol counts may benefit from splitting or renaming.",
            difficulty="medium",
            steps=steps,
            related_modules=[name for name, _ in hotspots],
        )
        self.cards = [card]
        return self.cards

    def propose_action_tree(self, refactor_hint: str) -> RoadmapCard:
        """Return a roadmap card with interconnected steps."""

        steps = [
            f"Evaluate current usages of {refactor_hint}",
            f"Draft extraction plan for {refactor_hint}",
            "Coordinate test updates with testing panel",
            "Schedule rollout across branches",
        ]
        card = RoadmapCard(
            title=f"Plan: {refactor_hint}",
            summary="Multi-step action tree prepared by the planner.",
            difficulty="high",
            steps=steps,
            related_modules=list(self.graph.module_map().keys()),
        )
        self.cards.append(card)
        return card

    def propose_evolution(self, target: str) -> list[RoadmapCard]:
        """Draft phased migrations for long-horizon evolution."""

        migrations = [
            RoadmapCard(
                title=f"Phase 1: audit {target}",
                summary="Collect metrics and guardrails before migration.",
                difficulty="medium",
                steps=["Capture runtime traces", "Pin failing tests", "Freeze API contracts"],
            ),
            RoadmapCard(
                title=f"Phase 2: modernise {target}",
                summary="Introduce async/class conversions where low risk.",
                difficulty="high",
                steps=["Convert blocking flows to async", "Extract brittle functions into classes", "Add compatibility shims"],
            ),
        ]
        self.cards.extend(migrations)
        return migrations

    def roadmap_feed(self) -> str:
        """Return text suitable for rendering inside roadmap UI panels."""

        if not self.cards:
            return "Planner has not produced roadmap cards yet."
        lines: list[str] = []
        for card in self.cards:
            lines.append(f"- {card.title} [{card.difficulty}]")
            for step in card.steps:
                lines.append(f"  • {step}")
        return "\n".join(lines)

    def record_outcome(self, card: RoadmapCard, accepted: bool) -> None:
        """Store planner feedback into workspace memory."""

        event = {
            "card": card.title,
            "accepted": accepted,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.memory.append_event("roadmap", event)
