"""Transport abstraction for collaborative editing."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class WebSocketTransport(QObject):
    message_received = Signal(str, dict)
    connection_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.connected = False

    def connect(self, url: str) -> None:
        self.connected = True
        self.connection_changed.emit("connected")

    def disconnect(self) -> None:
        self.connected = False
        self.connection_changed.emit("disconnected")

    def send_event(self, event: str, payload: dict | None = None) -> None:
        if self.connected:
            self.message_received.emit(event, payload or {})

