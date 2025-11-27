"""Minimal CRDT engine placeholder for collaborative editing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class RemoteCursor:
    user: str
    position: int
    color: str = "#00aaff"


class CRDTEngine:
    def __init__(self) -> None:
        self.buffers: dict[str, list[str]] = {}
        self.remote_cursors: list[RemoteCursor] = []
        self.user_history: dict[str, list[str]] = {}
        self.diagnostics: list[str] = []
        self.semantic_events: list[str] = []
        self.task_queue: list[str] = []
        self.patch_proposals: list[str] = []

    def apply_local_change(self, file_id: str, text: str, user: str | None = None) -> list[Tuple[int, str]]:
        self.buffers[file_id] = list(text)
        if user:
            self.user_history.setdefault(user, []).append(text)
        return []

    def undo(self, user: str) -> str | None:
        history = self.user_history.get(user, [])
        if history:
            history.pop()
            return history[-1] if history else ""
        return None

    def apply_remote_patch(self, file_id: str, patch: str) -> str:
        self.buffers[file_id] = list(patch)
        return "".join(self.buffers[file_id])

    def set_remote_cursor(self, cursor: RemoteCursor) -> None:
        self.remote_cursors.append(cursor)

    def participants(self) -> List[str]:
        return [cursor.user for cursor in self.remote_cursors]

    def share_diagnostic(self, message: str) -> None:
        self.diagnostics.append(message)

    def share_semantic_event(self, node: str) -> None:
        self.semantic_events.append(node)

    def enqueue_task(self, task: str) -> None:
        self.task_queue.append(task)

    def propose_patch(self, description: str) -> None:
        self.patch_proposals.append(description)

    def resolve_conflicts(self) -> dict[str, list[str]]:
        """Return a combined view of collaborative layers."""

        return {
            "buffers": list(self.buffers.keys()),
            "tasks": list(self.task_queue),
            "patches": list(self.patch_proposals),
            "semantics": list(self.semantic_events),
        }
