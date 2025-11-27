"""Base classes for Ghostline's multi-agent system."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class AgentResult:
    """Standard envelope for agent outcomes."""

    agent_name: str
    success: bool
    summary: str
    patches: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


class SharedContext(Protocol):
    """Lightweight protocol for shared context providers."""

    def snapshot(self) -> dict[str, Any]:
        ...


class BaseAgent:
    """Common contract for specialised agents."""

    def __init__(self, name: str, shared_context: SharedContext | None = None) -> None:
        self.name = name
        self.shared_context = shared_context

    def run(self, task: str) -> AgentResult:  # pragma: no cover - interface method
        raise NotImplementedError

    def describe_context(self) -> dict[str, Any]:
        if not self.shared_context:
            return {}
        return self.shared_context.snapshot()
