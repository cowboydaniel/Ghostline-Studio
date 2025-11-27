"""Simple chat-like panel for AI responses."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
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

        self.transcript = QTextEdit(self)
        self.transcript.setReadOnly(True)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Ask Ghostline AI...")
        self.input.returnPressed.connect(self._send)

        send_button = QPushButton("Send", self)
        send_button.clicked.connect(self._send)

        context_button = QPushButton("Send with context", self)
        context_button.clicked.connect(self._send_with_context)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input)
        input_row.addWidget(send_button)
        input_row.addWidget(context_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.transcript)
        layout.addLayout(input_row)

        self.context_provider = None

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

