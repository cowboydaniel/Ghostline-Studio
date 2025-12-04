"""Simple chat-like panel for AI responses."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
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


class _AIRequestWorker(QObject):
    """Background worker to prevent blocking the UI thread."""

    finished = Signal(str, str)
    failed = Signal(str)

    def __init__(self, client: AIClient, prompt: str, context: str | None) -> None:
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.context = context

    @Slot()
    def run(self) -> None:
        try:
            response = self.client.send(self.prompt, context=self.context)
            self.finished.emit(self.prompt, response.text)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class AIChatPanel(QWidget):
    def __init__(self, client: AIClient, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self._active_thread: QThread | None = None

        self.status_label = QLabel("AI: Idle (no workspace)", self)
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

    def _set_busy(self, busy: bool) -> None:
        self.input.setEnabled(not busy and self.workspace_active)
        self.send_button.setEnabled(not busy and self.workspace_active)
        self.context_button.setEnabled(not busy and self.workspace_active)
        status = "AI: Working..." if busy else ("AI: Ready" if self.workspace_active else "AI: Idle (no workspace)")
        self.status_label.setText(status)

    def _handle_response(self, thread: QThread, worker: _AIRequestWorker, prompt: str, text: str) -> None:
        self._append("AI", text)
        self._cleanup_thread(thread, worker)
        self._set_busy(False)
        self.input.clear()

    def _handle_error(self, thread: QThread, worker: _AIRequestWorker, error: str) -> None:
        self._append("AI", f"Error: {error}")
        self._cleanup_thread(thread, worker)
        self._set_busy(False)

    def _cleanup_thread(self, thread: QThread, worker: _AIRequestWorker) -> None:
        worker.deleteLater()
        thread.quit()
        thread.wait()
        thread.deleteLater()
        if self._active_thread is thread:
            self._active_thread = None

    def _start_request(self, prompt: str, context: str | None) -> None:
        if self._active_thread:
            return

        self._append("You", prompt)
        self._set_busy(True)

        thread = QThread(self)
        worker = _AIRequestWorker(self.client, prompt, context)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda p, text: self._handle_response(thread, worker, p, text))
        worker.failed.connect(lambda error: self._handle_error(thread, worker, error))
        thread.start()
        self._active_thread = thread

    def _send(self) -> None:
        prompt = self.input.text().strip()
        if not prompt:
            return
        self._start_request(prompt, None)

    def _send_with_context(self) -> None:
        prompt = self.input.text().strip()
        context = self.context_provider() if self.context_provider else None
        if not prompt:
            return
        self._start_request(prompt, context)

    def set_workspace_active(self, active: bool) -> None:
        self.workspace_active = active
        label = "AI: Ready" if active else "AI: Idle (no workspace)"
        self.status_label.setText(label)
        self.input.setEnabled(active)
        self.send_button.setEnabled(active)
        self.context_button.setEnabled(active)

