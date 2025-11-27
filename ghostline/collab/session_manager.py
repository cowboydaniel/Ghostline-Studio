"""Session orchestration for collaborative editing."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Signal

from ghostline.collab.crdt_engine import CRDTEngine, RemoteCursor
from ghostline.collab.shared_workspace import SharedWorkspace


class SessionManager(QObject):
    session_joined = Signal(str)
    session_left = Signal(str)
    presence_changed = Signal(list)

    def __init__(self, engine: CRDTEngine | None = None, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine or CRDTEngine()
        self.transport: Callable[[str], None] | None = None
        self.shared_workspace: SharedWorkspace | None = None

    def create_session(self, session_id: str) -> None:
        self.session_joined.emit(session_id)

    def join_session(self, session_id: str) -> None:
        self.session_joined.emit(session_id)

    def leave_session(self, session_id: str) -> None:
        self.session_left.emit(session_id)

    def apply_remote_patch(self, patch: str) -> str:
        text = self.engine.apply_remote_patch(patch)
        self._notify_presence()
        return text

    def set_shared_workspace(self, shared: SharedWorkspace) -> None:
        self.shared_workspace = shared

    def broadcast_shared_state(self) -> None:
        if self.shared_workspace:
            self.shared_workspace.broadcast_build_queue()

    def update_remote_cursor(self, user: str, position: int, color: str = "#00aaff") -> None:
        self.engine.set_remote_cursor(RemoteCursor(user, position, color))
        self._notify_presence()

    def _notify_presence(self) -> None:
        self.presence_changed.emit(self.engine.participants())
