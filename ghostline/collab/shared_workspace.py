"""Shared workspace coordination for collaborative sessions."""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

from ghostline.build.build_manager import BuildManager
from ghostline.testing.test_manager import TestManager
from ghostline.semantic.index_manager import SemanticIndexManager


@dataclass
class SharedState:
    build_queue: list[str] = field(default_factory=list)
    test_status: dict[str, str] = field(default_factory=dict)
    semantic_updates: list[str] = field(default_factory=list)
    agent_outputs: list[str] = field(default_factory=list)


class SharedWorkspace(QObject):
    """Synchronises builds, tests, and semantic indexes across users."""

    build_queue_changed = Signal(list)
    test_state_changed = Signal(dict)
    semantic_changed = Signal(list)
    agent_outputs_changed = Signal(list)

    def __init__(
        self,
        build_manager: BuildManager,
        test_manager: TestManager,
        index_manager: SemanticIndexManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.state = SharedState()
        self.build_manager = build_manager
        self.test_manager = test_manager
        self.index_manager = index_manager

    def broadcast_build_queue(self) -> None:
        self.state.build_queue = list(self.build_manager.tasks)
        self.build_queue_changed.emit(self.state.build_queue)

    def update_test_state(self, name: str, status: str) -> None:
        self.state.test_status[name] = status
        self.test_state_changed.emit(dict(self.state.test_status))

    def record_semantic_update(self, path: str) -> None:
        self.state.semantic_updates.append(path)
        self.semantic_changed.emit(list(self.state.semantic_updates))

    def publish_agent_output(self, message: str) -> None:
        self.state.agent_outputs.append(message)
        self.agent_outputs_changed.emit(list(self.state.agent_outputs))
