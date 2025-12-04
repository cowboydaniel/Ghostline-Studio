"""Rich chat panel that exposes workspace-aware context controls."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot, QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QStackedLayout,
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
        self._busy: bool = False
        self.active_document_provider = None
        self.open_documents_provider = None
        self.command_adapter = None
        self.insert_handler = None
        self._last_chunks: list[ContextChunk] = []
        self._current_context_text: str = ""
        self._current_pins: list[ContextChunk] = []

        self.setObjectName("aiChatPanel")
        self.setStyleSheet(
            """
            #aiChatPanel {
                background: palette(base);
                border-radius: 12px;
            }
            #chatTopBar {
                background: transparent;
            }
            QListWidget#chatTranscript {
                border: none;
                background: transparent;
            }
            QLabel#chatShortcutHint {
                color: palette(mid);
                font-size: 11px;
            }
            QLabel#pinnedBadge {
                padding: 2px 6px;
                border-radius: 8px;
                background: palette(highlight);
                color: palette(bright-text);
                font-weight: 600;
            }
            #chatInputBar {
                border: 1px solid palette(mid);
                border-radius: 18px;
                background: palette(base);
            }
            """
        )

        self.instructions = QTextEdit(self)
        self.instructions.setPlaceholderText("Optional: add custom instructions, tone, or constraints")
        self.instructions.hide()

        self.status_indicator = QLabel(self)
        self.status_indicator.setObjectName("statusIndicator")
        self.status_indicator.setFixedSize(12, 12)
        self.status_indicator.setToolTip("AI assistant status")
        self._refresh_status_indicator()

        def _style_toolbar_button(button: QToolButton) -> None:
            button.setAutoRaise(True)
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setFixedSize(32, 32)
            button.setIconSize(QSize(18, 18))

        self.mode_button = QToolButton(self)
        _style_toolbar_button(self.mode_button)
        self.mode_button.setText("Agents")
        self.mode_button.setIcon(
            QIcon.fromTheme(
                "system-users",
                self.style().standardIcon(QStyle.SP_FileDialogListView),
            )
        )
        self.mode_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.mode_button.setToolTip("Select agent or mode")
        mode_menu = QMenu(self.mode_button)
        mode_menu.addAction("General")
        mode_menu.addAction("Code")
        mode_menu.addSeparator()
        self.instructions_action = mode_menu.addAction("Instructions…")
        self.instructions_action.triggered.connect(self._open_instructions_dialog)
        self.mode_button.setMenu(mode_menu)

        self.new_chat_button = QToolButton(self)
        _style_toolbar_button(self.new_chat_button)
        self.new_chat_button.setIcon(
            QIcon.fromTheme(
                "list-add",
                self.style().standardIcon(QStyle.SP_FileDialogNewFolder),
            )
        )
        self.new_chat_button.setToolTip("Start a new chat")
        self.new_chat_button.clicked.connect(self._reset_chat)

        self.history_button = QToolButton(self)
        _style_toolbar_button(self.history_button)
        self.history_button.setIcon(
            QIcon.fromTheme(
                "document-open-recent",
                self.style().standardIcon(QStyle.SP_FileDialogInfoView),
            )
        )
        self.history_button.setToolTip("Chat history")
        self.history_button.clicked.connect(self._show_history_placeholder)

        self.pinned_badge = QLabel("0", self)
        self.pinned_badge.setObjectName("pinnedBadge")
        self.pinned_badge.setVisible(False)

        self.tools_button = QToolButton(self)
        _style_toolbar_button(self.tools_button)
        self.tools_button.setIcon(
            QIcon.fromTheme(
                "preferences-system",
                self.style().standardIcon(QStyle.SP_FileDialogDetailedView),
            )
        )
        self.tools_button.setPopupMode(QToolButton.InstantPopup)
        self.tools_button.setToolTip("Context and tools")
        tools_menu = QMenu(self.tools_button)
        self.context_action = QAction("Preview Context", self)
        self.context_action.triggered.connect(self._open_context_dialog)
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

        self.overflow_button = QToolButton(self)
        _style_toolbar_button(self.overflow_button)
        self.overflow_button.setPopupMode(QToolButton.InstantPopup)
        self.overflow_button.setIcon(
            QIcon.fromTheme(
                "open-menu-symbolic",
                self.style().standardIcon(QStyle.SP_ToolBarHorizontalExtensionButton),
            )
        )
        self.overflow_button.setToolTip("More actions")
        overflow_menu = QMenu(self.overflow_button)
        overflow_menu.addAction(self.instructions_action)
        overflow_menu.addSeparator()
        overflow_menu.addAction(self.context_action)
        overflow_menu.addAction(self.pin_action)
        overflow_menu.addAction(self.unpin_action)
        overflow_menu.addAction(self.active_flag_action)
        self.overflow_button.setMenu(overflow_menu)

        top_bar = QFrame(self)
        top_bar.setObjectName("chatTopBar")
        top_bar.setFrameShape(QFrame.NoFrame)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(6, 6, 6, 6)
        top_layout.setSpacing(10)
        top_layout.addStretch()
        top_layout.addWidget(self.pinned_badge)
        top_layout.addWidget(self.status_indicator, 0, Qt.AlignVCenter)
        top_layout.addWidget(self.mode_button)
        top_layout.addWidget(self.new_chat_button)
        top_layout.addWidget(self.history_button)
        top_layout.addWidget(self.tools_button)
        top_layout.addWidget(self.overflow_button)

        self.placeholder = QWidget(self)
        placeholder_layout = QVBoxLayout(self.placeholder)
        placeholder_layout.setAlignment(Qt.AlignCenter)
        logo = QLabel("👻", self.placeholder)
        logo.setStyleSheet("font-size: 42px;")
        title = QLabel("Ghostline Studio", self.placeholder)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        subtitle = QLabel("Your AI teammate is ready to collaborate.", self.placeholder)
        subtitle.setStyleSheet("color: palette(mid);")
        placeholder_hint = QLabel("// Chat bubbles will appear here soon", self.placeholder)
        placeholder_hint.setStyleSheet("color: palette(mid);")
        placeholder_layout.addWidget(logo, 0, Qt.AlignHCenter)
        placeholder_layout.addWidget(title, 0, Qt.AlignHCenter)
        placeholder_layout.addWidget(subtitle, 0, Qt.AlignHCenter)
        placeholder_layout.addSpacing(12)
        placeholder_layout.addWidget(placeholder_hint, 0, Qt.AlignHCenter)

        self.transcript_list = QListWidget(self)
        self.transcript_list.setObjectName("chatTranscript")
        self.transcript_list.setFrameShape(QFrame.NoFrame)
        self.transcript_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.transcript_stack = QStackedLayout()
        self.transcript_stack.addWidget(self.placeholder)
        self.transcript_stack.addWidget(self.transcript_list)

        transcript_container = QFrame(self)
        transcript_container.setLayout(self.transcript_stack)

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(top_bar)
        layout.addWidget(transcript_container, 1)
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
        self.transcript_stack.setCurrentWidget(self.transcript_list)
        return card

    def _reset_chat(self) -> None:
        if self._active_thread:
            return
        self.transcript_list.clear()
        self._active_response_card = None
        self._active_response_text = ""
        self.transcript_stack.setCurrentWidget(self.placeholder)

    def _show_history_placeholder(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Chat history")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Chat history will appear here soon.", dialog))
        buttons = QDialogButtonBox(QDialogButtonBox.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _set_busy(self, busy: bool) -> None:
        enabled = not busy and self.workspace_active
        self.input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.mic_button.setEnabled(enabled)
        for button in (
            self.mode_button,
            self.new_chat_button,
            self.history_button,
            self.tools_button,
            self.overflow_button,
        ):
            button.setEnabled(enabled)
        for action in (
            self.instructions_action,
            self.context_action,
            self.pin_action,
            self.unpin_action,
            self.active_flag_action,
        ):
            action.setEnabled(enabled)
        self._busy = busy
        self._refresh_status_indicator()

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
            self._update_context_state(chunks, context, instructions)
            return context, chunks
        self._update_context_state([], instructions or None, instructions)
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

    def _open_context_dialog(self) -> None:
        prompt = self.input.text().strip()
        context, chunks = self._gather_context(prompt)
        preview_text = context or self._current_context_text

        dialog = QDialog(self)
        dialog.setWindowTitle("Context preview")
        layout = QVBoxLayout(dialog)

        chunk_list = QListWidget(dialog)
        chunk_list.setSelectionMode(QListWidget.NoSelection)
        chunk_list.setFocusPolicy(Qt.NoFocus)
        for chunk in chunks:
            label = chunk.title
            if chunk.reason:
                label += f" — {chunk.reason}"
            QListWidgetItem(label, chunk_list)
        if not chunks:
            QListWidgetItem("No contextual documents selected yet", chunk_list)
        layout.addWidget(QLabel("Context sources", dialog))
        layout.addWidget(chunk_list)

        pinned_list = QListWidget(dialog)
        pinned_list.setSelectionMode(QListWidget.NoSelection)
        pinned_list.setFocusPolicy(Qt.NoFocus)
        for pinned in self._current_pins:
            QListWidgetItem(pinned.title, pinned_list)
        if not self._current_pins:
            QListWidgetItem("No pinned documents", pinned_list)
        layout.addWidget(QLabel("Pinned", dialog))
        layout.addWidget(pinned_list)

        preview = QTextEdit(dialog)
        preview.setReadOnly(True)
        preview.setPlainText(preview_text)
        layout.addWidget(QLabel("Preview", dialog))
        layout.addWidget(preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.exec()

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
        self._gather_context(self.input.text().strip())

    def _clear_pins(self) -> None:
        if not self.context_engine:
            return
        for pinned in list(self.context_engine.pinned()):
            self.context_engine.unpin(pinned.title)
        self._gather_context(self.input.text().strip())

    def _update_context_state(
        self, chunks: list[ContextChunk], context: str | None, instructions: str | None = None
    ) -> None:
        self._last_chunks = chunks
        self._current_context_text = context or instructions or ""
        if self.context_engine:
            self._current_pins = list(self.context_engine.pinned())
        else:
            self._current_pins = []
        self._update_pinned_badge(len(self._current_pins))

    def set_workspace_active(self, active: bool) -> None:
        self.workspace_active = active
        self._set_busy(False)

    def _refresh_status_indicator(self) -> None:
        ready = self.workspace_active and not self._busy
        color = "#34c759" if ready else "#9e9e9e"
        radius = self.status_indicator.height() // 2
        self.status_indicator.setStyleSheet(
            f"#statusIndicator {{ background-color: {color}; border-radius: {radius}px; }}"
        )
        tooltip = "AI Ready" if ready else ("AI Busy" if self.workspace_active else "AI Offline")
        self.status_indicator.setToolTip(tooltip)

    def _update_pinned_badge(self, count: int) -> None:
        self.pinned_badge.setText(str(count))
        self.pinned_badge.setVisible(count > 0)

    @Slot(str)
    def _on_worker_partial(self, delta: str) -> None:
        if not self._active_response_card:
            return
        self._active_response_text += delta
        self._active_response_card.set_text(self._active_response_text)

