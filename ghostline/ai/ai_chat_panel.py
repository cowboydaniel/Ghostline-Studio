"""Simple chat-like panel for AI responses."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ghostline.ai.ai_client import AIClient


class AIChatPanel(QWidget):
    def __init__(self, client: AIClient, parent=None) -> None:
        super().__init__(parent)
        self.client = client

        self.status_label = QLabel("Idle (no workspace)", self)
        self.status_label.setAlignment(Qt.AlignLeft)
        self.transcript = QTextEdit(self)
        self.transcript.setReadOnly(True)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Ask Ghostline AI...")
        self.input.returnPressed.connect(self._send)

        self.send_button = QPushButton("Send", self)
        self.send_button.clicked.connect(self._send)

        self.context_button = QPushButton("Send with context", self)
        self.context_button.clicked.connect(self._send_with_context)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input)
        input_row.addWidget(self.send_button)
        input_row.addWidget(self.context_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.status_label)
        layout.addWidget(self.transcript)
        layout.addLayout(input_row)

        self.context_provider = None
        self.workspace_active = False

    def set_context_provider(self, provider) -> None:
        self.context_provider = provider

    def _append(self, role: str, text: str) -> None:
        self.transcript.append(f"<b>{role}:</b> {text}")

    def _send(self) -> None:
        prompt = self.input.text().strip()
        if not prompt:
            return
        self._append("You", prompt)
        response = self.client.send(prompt)
        self._append("AI", response.text)
        self.input.clear()

    def _send_with_context(self) -> None:
        prompt = self.input.text().strip()
        context = self.context_provider() if self.context_provider else None
        if not prompt:
            return
        self._append("You", prompt)
        response = self.client.send(prompt, context=context)
        self._append("AI", response.text)
        self.input.clear()

    def set_workspace_active(self, active: bool) -> None:
        self.workspace_active = active
        label = "Ready" if active else "Idle (no workspace)"
        self.status_label.setText(label)
        self.input.setEnabled(active)
        self.send_button.setEnabled(active)
        self.context_button.setEnabled(active)

