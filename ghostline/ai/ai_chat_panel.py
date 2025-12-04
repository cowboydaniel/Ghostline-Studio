"""Rich chat panel that exposes workspace-aware context controls."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ghostline.ai.ai_client import AIClient
from ghostline.ai.context_engine import ContextChunk, ContextEngine


class _MessageCard(QWidget):
    """Render a chat message with code block controls and context info."""

    def __init__(
        self,
        role: str,
        text: str,
        context: list[ContextChunk] | None = None,
        insert_handler=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        title = QLabel(f"<b>{role}</b>", self)
        layout.addWidget(title)

        preamble = QLabel("\n".join([chunk.title for chunk in context or []]), self)
        preamble.setWordWrap(True)
        if context:
            layout.addWidget(preamble)

        code_blocks = re.findall(r"```(?:[\w#+-]+)?\n(.*?)```", text, flags=re.DOTALL)
        rendered_code = False
        for block in code_blocks:
            rendered_code = True
            code_edit = QTextEdit(block.strip(), self)
            code_edit.setReadOnly(True)
            btn_row = QHBoxLayout()
            copy_btn = QPushButton("Copy", self)
            copy_btn.clicked.connect(lambda _=None, b=block: QApplication.clipboard().setText(b))
            btn_row.addWidget(copy_btn)
            if insert_handler:
                insert_btn = QPushButton("Insert at cursor", self)
                insert_btn.clicked.connect(lambda _=None, b=block: insert_handler(b))
                btn_row.addWidget(insert_btn)
            layout.addWidget(code_edit)
            layout.addLayout(btn_row)

        if not rendered_code:
            body = QTextEdit(text, self)
            body.setReadOnly(True)
            layout.addWidget(body)


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
    def __init__(self, client: AIClient, context_engine: ContextEngine | None = None, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.context_engine = context_engine
        self._active_thread: QThread | None = None
        self.workspace_active = False
        self.active_document_provider = None
        self.open_documents_provider = None
        self.command_adapter = None
        self.insert_handler = None
        self._last_chunks: list[ContextChunk] = []

        self.status_label = QLabel("AI: Idle (no workspace)", self)
        self.status_label.setAlignment(Qt.AlignLeft)

        self.transcript_list = QListWidget(self)

        self.instructions = QTextEdit(self)
        self.instructions.setPlaceholderText("Optional: add custom instructions, tone, or constraints")
        self.instructions.setMaximumHeight(80)

        self.context_preview = QTextEdit(self)
        self.context_preview.setReadOnly(True)
        self.context_preview.setPlaceholderText("Context that will be sent with your prompt")

        self.context_list = QListWidget(self)
        self.pinned_list = QListWidget(self)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Ask Ghostline AI...")
        self.input.returnPressed.connect(self._send)

        self.send_button = QPushButton("Ask", self)
        self.send_button.clicked.connect(self._send)

        self.context_button = QPushButton("Preview Context", self)
        self.context_button.clicked.connect(self._refresh_context_view)

        self.pin_button = QPushButton("Pin active", self)
        self.pin_button.clicked.connect(self._pin_active_document)
        self.unpin_button = QPushButton("Unpin all", self)
        self.unpin_button.clicked.connect(self._clear_pins)
        self.active_flag = QPushButton("Mark Active Document", self)
        self.active_flag.setCheckable(True)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input)
        input_row.addWidget(self.send_button)
        input_row.addWidget(self.context_button)
        input_row.addWidget(self.pin_button)
        input_row.addWidget(self.unpin_button)
        input_row.addWidget(self.active_flag)

        context_box = QGroupBox("Context sources", self)
        context_layout = QVBoxLayout(context_box)
        context_layout.setContentsMargins(6, 6, 6, 6)
        context_layout.addWidget(QLabel("Pinned", context_box))
        context_layout.addWidget(self.pinned_list)
        context_layout.addWidget(QLabel("Planned context", context_box))
        context_layout.addWidget(self.context_list)
        context_layout.addWidget(QLabel("Preview", context_box))
        context_layout.addWidget(self.context_preview)

        instructions_box = QGroupBox("Instructions", self)
        instructions_layout = QVBoxLayout(instructions_box)
        instructions_layout.setContentsMargins(6, 6, 6, 6)
        instructions_layout.addWidget(self.instructions)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.status_label)
        layout.addWidget(instructions_box)
        layout.addWidget(self.transcript_list)
        layout.addLayout(input_row)
        layout.addWidget(context_box)

    def set_active_document_provider(self, provider) -> None:
        self.active_document_provider = provider

    def set_open_documents_provider(self, provider) -> None:
        self.open_documents_provider = provider

    def set_insert_handler(self, handler) -> None:
        self.insert_handler = handler

    def set_command_adapter(self, adapter) -> None:
        self.command_adapter = adapter

    def _append(self, role: str, text: str, context: list[ContextChunk] | None = None) -> None:
        card = _MessageCard(role, text, context, insert_handler=self.insert_handler, parent=self)
        item = QListWidgetItem(self.transcript_list)
        item.setSizeHint(card.sizeHint())
        self.transcript_list.addItem(item)
        self.transcript_list.setItemWidget(item, card)

    def _set_busy(self, busy: bool) -> None:
        enabled = not busy and self.workspace_active
        self.input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.context_button.setEnabled(enabled)
        self.pin_button.setEnabled(enabled)
        self.unpin_button.setEnabled(enabled)
        self.active_flag.setEnabled(enabled)
        status = "AI: Working..." if busy else ("AI: Ready" if self.workspace_active else "AI: Idle (no workspace)")
        self.status_label.setText(status)

    def _handle_response(self, thread: QThread, worker: _AIRequestWorker, prompt: str, text: str) -> None:
        self._append("AI", text, context=self._last_chunks)
        if self.command_adapter:
            self.command_adapter.handle_response(text)
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

    def _gather_context(self, prompt: str) -> tuple[str | None, list[ContextChunk]]:
        instructions = self.instructions.toPlainText().strip()
        if self.context_engine and self.workspace_active:
            active = self.active_document_provider() if self.active_document_provider else None
            open_docs = self.open_documents_provider() if self.open_documents_provider else None
            context, chunks = self.context_engine.build_context(
                prompt,
                instructions=instructions,
                active_document=active,
                open_documents=open_docs,
            )
            self._show_context_sources(chunks, context)
            return context, chunks
        self._show_context_sources([], instructions)
        return instructions or None, []

    def _start_request(self, prompt: str, context: str | None) -> None:
        if self._active_thread:
            return

        self._append("You", prompt, context=self._last_chunks)
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
        context, chunks = self._gather_context(prompt)
        self._last_chunks = chunks
        self._start_request(prompt, context)

    def _refresh_context_view(self) -> None:
        prompt = self.input.text().strip()
        context, chunks = self._gather_context(prompt) if prompt else (None, [])
        self._last_chunks = chunks
        if context is not None:
            self.context_preview.setPlainText(context)

    def _pin_active_document(self) -> None:
        if not self.context_engine or not self.active_document_provider:
            return
        active = self.active_document_provider()
        if not active:
            return
        path, text = active
        path_obj = Path(path) if path else None
        title = f"Pinned: {path_obj.name}" if path_obj else "Pinned document"
        self.context_engine.pin_context(ContextChunk(title, text, path_obj, "Pinned manually"))
        self._refresh_context_view()

    def _clear_pins(self) -> None:
        if not self.context_engine:
            return
        for pinned in list(self.context_engine.pinned()):
            self.context_engine.unpin(pinned.title)
        self._refresh_context_view()

    def _show_context_sources(self, chunks: list[ContextChunk], context: str | None) -> None:
        self.context_list.clear()
        for chunk in chunks:
            label = chunk.title
            if chunk.reason:
                label += f" — {chunk.reason}"
            QListWidgetItem(label, self.context_list)
        self.pinned_list.clear()
        if self.context_engine:
            for pinned in self.context_engine.pinned():
                QListWidgetItem(pinned.title, self.pinned_list)
        if context is not None:
            self.context_preview.setPlainText(context)

    def set_workspace_active(self, active: bool) -> None:
        self.workspace_active = active
        label = "AI: Ready" if active else "AI: Idle (no workspace)"
        self.status_label.setText(label)
        self._set_busy(False)

