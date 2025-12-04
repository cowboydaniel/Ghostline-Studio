"""Rich chat panel that exposes workspace-aware context controls."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QAction,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QStyle,
    QTextEdit,
    QToolButton,
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
        self.insert_handler = insert_handler
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        title = QLabel(f"<b>{role}</b>", self)
        layout.addWidget(title)

        preamble = QLabel("\n".join([chunk.title for chunk in context or []]), self)
        preamble.setWordWrap(True)
        if context:
            layout.addWidget(preamble)

        self._content_layout = QVBoxLayout()
        layout.addLayout(self._content_layout)
        self.set_text(text)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                item.layout().deleteLater()

    def set_text(self, text: str) -> None:
        self._clear_content()
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
            if self.insert_handler:
                insert_btn = QPushButton("Insert at cursor", self)
                insert_btn.clicked.connect(lambda _=None, b=block: self.insert_handler(b))
                btn_row.addWidget(insert_btn)
            self._content_layout.addWidget(code_edit)
            self._content_layout.addLayout(btn_row)

        if not rendered_code:
            body = QTextEdit(text, self)
            body.setReadOnly(True)
            self._content_layout.addWidget(body)


class _AIRequestWorker(QObject):
    """Background worker to prevent blocking the UI thread."""

    finished = Signal(str, str)
    failed = Signal(str)
    partial = Signal(str)

    def __init__(self, client: AIClient, prompt: str, context: str | None) -> None:
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.context = context

    @Slot()
    def run(self) -> None:
        try:
            text = ""
            for chunk in self.client.stream(self.prompt, context=self.context):
                text += chunk
                self.partial.emit(chunk)
            self.finished.emit(self.prompt, text)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class AIChatPanel(QWidget):
    def __init__(self, client: AIClient, context_engine: ContextEngine | None = None, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.context_engine = context_engine
        self._active_thread: QThread | None = None
        self._active_worker: _AIRequestWorker | None = None
        self._active_response_card: _MessageCard | None = None
        self._active_response_text: str = ""
        self.workspace_active = False
        self.active_document_provider = None
        self.open_documents_provider = None
        self.command_adapter = None
        self.insert_handler = None
        self._last_chunks: list[ContextChunk] = []

        self.instructions = QTextEdit(self)
        self.instructions.setPlaceholderText("Optional: add custom instructions, tone, or constraints")
        self.instructions.setMaximumHeight(80)

        self.status_label = QLabel("AI: Idle (no workspace)", self)
        self.status_label.setAlignment(Qt.AlignLeft)

        self.advanced_button = QToolButton(self)
        self.advanced_button.setText("Advanced")
        self.advanced_button.setPopupMode(QToolButton.MenuButtonPopup)
        advanced_menu = QMenu(self.advanced_button)
        instructions_action = advanced_menu.addAction("Settings")
        instructions_action.triggered.connect(self._open_instructions_dialog)
        self.advanced_button.setMenu(advanced_menu)

        self.tools_button = QToolButton(self)
        self.tools_button.setText("Tools")
        self.tools_button.setPopupMode(QToolButton.InstantPopup)
        tools_menu = QMenu(self.tools_button)
        self.context_action = QAction("Preview Context", self)
        self.context_action.triggered.connect(self._refresh_context_view)
        self.pin_action = QAction("Pin active", self)
        self.pin_action.triggered.connect(self._pin_active_document)
        self.unpin_action = QAction("Unpin all", self)
        self.unpin_action.triggered.connect(self._clear_pins)
        self.active_flag_action = QAction("Mark Active Document", self)
        self.active_flag_action.setCheckable(True)
        tools_menu.addActions(
            [
                self.context_action,
                self.pin_action,
                self.unpin_action,
                self.active_flag_action,
            ]
        )
        self.tools_button.setMenu(tools_menu)

        self.transcript_list = QListWidget(self)

        self.context_preview = QTextEdit(self)
        self.context_preview.setReadOnly(True)
        self.context_preview.setPlaceholderText("Context that will be sent with your prompt")

        self.context_list = QListWidget(self)
        self.pinned_list = QListWidget(self)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Ask anything")
        self.input.returnPressed.connect(self._send)

        self.input_bar = QFrame(self)
        self.input_bar.setObjectName("chatInputBar")
        self.input_bar.setStyleSheet(
            """
            #chatInputBar {
                border: 1px solid palette(mid);
                border-radius: 18px;
                background: palette(base);
            }
            QLabel#chatShortcutHint {
                color: palette(mid);
                font-size: 11px;
            }
            """
        )
        input_layout = QHBoxLayout(self.input_bar)
        input_layout.setContentsMargins(12, 6, 12, 6)
        input_layout.setSpacing(8)

        self.mic_button = QToolButton(self.input_bar)
        self.mic_button.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))
        self.mic_button.setToolTip("Start voice input")
        self.mic_button.setCheckable(True)

        self.shortcut_hint = QLabel("Enter to send", self.input_bar)
        self.shortcut_hint.setObjectName("chatShortcutHint")

        self.send_button = QToolButton(self.input_bar)
        self.send_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.send_button.setToolTip("Send")
        self.send_button.clicked.connect(self._send)

        input_layout.addWidget(self.mic_button)
        input_layout.addWidget(self.input, 1)
        input_layout.addWidget(self.shortcut_hint)
        input_layout.addWidget(self.send_button)

        context_box = QGroupBox("Context sources", self)
        context_layout = QVBoxLayout(context_box)
        context_layout.setContentsMargins(6, 6, 6, 6)
        context_layout.addWidget(QLabel("Pinned", context_box))
        context_layout.addWidget(self.pinned_list)
        context_layout.addWidget(QLabel("Planned context", context_box))
        context_layout.addWidget(self.context_list)
        context_layout.addWidget(QLabel("Preview", context_box))
        context_layout.addWidget(self.context_preview)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self.status_label)
        top_bar.addStretch()
        top_bar.addWidget(self.tools_button)
        top_bar.addWidget(self.advanced_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(top_bar)
        layout.addWidget(self.transcript_list)
        layout.addWidget(context_box)
        layout.addStretch()
        layout.addWidget(self.input_bar)

    def set_active_document_provider(self, provider) -> None:
        self.active_document_provider = provider

    def set_open_documents_provider(self, provider) -> None:
        self.open_documents_provider = provider

    def set_insert_handler(self, handler) -> None:
        self.insert_handler = handler

    def set_command_adapter(self, adapter) -> None:
        self.command_adapter = adapter

    def _append(
        self, role: str, text: str, context: list[ContextChunk] | None = None
    ) -> _MessageCard:
        card = _MessageCard(role, text, context, insert_handler=self.insert_handler, parent=self)
        item = QListWidgetItem(self.transcript_list)
        item.setSizeHint(card.sizeHint())
        self.transcript_list.addItem(item)
        self.transcript_list.setItemWidget(item, card)
        return card

    def _set_busy(self, busy: bool) -> None:
        enabled = not busy and self.workspace_active
        self.input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.mic_button.setEnabled(enabled)
        self.tools_button.setEnabled(enabled)
        for action in (
            self.context_action,
            self.pin_action,
            self.unpin_action,
            self.active_flag_action,
        ):
            action.setEnabled(enabled)
        status = "AI: Working..." if busy else ("AI: Ready" if self.workspace_active else "AI: Idle (no workspace)")
        self.status_label.setText(status)

    @Slot(str, str)
    def _on_worker_finished(self, prompt: str, text: str) -> None:
        if not self._active_thread or not self._active_worker:
            return
        if self._active_response_card:
            self._active_response_card.set_text(text)
        else:
            self._append("AI", text, context=self._last_chunks)
        self._active_response_text = text
        if self.command_adapter:
            self.command_adapter.handle_response(text)
        self._cleanup_thread(self._active_thread, self._active_worker)
        self._set_busy(False)
        self.input.clear()
        self._active_response_card = None
        self._active_response_text = ""

    @Slot(str)
    def _on_worker_failed(self, error: str) -> None:
        if not self._active_thread or not self._active_worker:
            return
        message = f"Error: {error}"
        if self._active_response_card:
            self._active_response_card.set_text(message)
        else:
            self._append("AI", message)
        self._active_response_text = ""
        self._cleanup_thread(self._active_thread, self._active_worker)
        self._set_busy(False)
        self._active_response_card = None

    def _cleanup_thread(self, thread: QThread, worker: _AIRequestWorker) -> None:
        worker.deleteLater()
        thread.quit()
        thread.wait()
        thread.deleteLater()
        if self._active_thread is thread:
            self._active_thread = None
        if self._active_worker is worker:
            self._active_worker = None

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
        worker.finished.connect(self._on_worker_finished, Qt.QueuedConnection)
        worker.failed.connect(self._on_worker_failed, Qt.QueuedConnection)
        worker.partial.connect(self._on_worker_partial, Qt.QueuedConnection)
        thread.start()
        self._active_thread = thread
        self._active_worker = worker
        self._active_response_card = self._append("AI", "", context=self._last_chunks)
        self._active_response_text = ""

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

    def _open_instructions_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("AI Instructions")
        layout = QVBoxLayout(dialog)
        helper = QLabel("Optional: add custom instructions, tone, or constraints", dialog)
        helper.setWordWrap(True)
        editor = QTextEdit(dialog)
        editor.setPlainText(self.instructions.toPlainText())
        editor.setPlaceholderText(self.instructions.placeholderText())
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(helper)
        layout.addWidget(editor)
        layout.addWidget(buttons)

        if dialog.exec():
            self.instructions.setPlainText(editor.toPlainText())

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

    @Slot(str)
    def _on_worker_partial(self, delta: str) -> None:
        if not self._active_response_card:
            return
        self._active_response_text += delta
        self._active_response_card.set_text(self._active_response_text)

