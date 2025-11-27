"""Collaboration panel with presence and chat."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QPushButton, QTextEdit, QVBoxLayout, QWidget, QDockWidget

from ghostline.collab.crdt_engine import CRDTEngine
from ghostline.collab.transport import WebSocketTransport


class CollabPanel(QDockWidget):
    def __init__(self, engine: CRDTEngine, transport: WebSocketTransport, parent=None) -> None:
        super().__init__("Collaboration", parent)
        self.engine = engine
        self.transport = transport
        self.users = QListWidget(self)
        self.chat = QTextEdit(self)
        self.chat.setReadOnly(True)
        self.follow_button = QPushButton("Follow mode")
        self.follow_button.setCheckable(True)
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(lambda: self.transport.connect("ws://example"))

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.users)
        layout.addWidget(self.chat)
        layout.addWidget(self.follow_button)
        layout.addWidget(self.connect_button)
        self.setWidget(content)

        self.transport.message_received.connect(self._on_message)
        self.transport.connection_changed.connect(self._on_connection)

    def _on_message(self, event: str, payload: dict) -> None:
        self.chat.append(f"{event}: {payload}")
        if event == "presence":
            self._refresh_users(payload.get("users", []))

    def _refresh_users(self, users: list[str]) -> None:
        self.users.clear()
        for user in users:
            self.users.addItem(QListWidgetItem(user))

    def _on_connection(self, state: str) -> None:
        self.chat.append(f"Connection {state}")

