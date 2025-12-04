"""Rich chat panel that exposes workspace-aware context controls."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot, QSize, QPoint
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QStackedLayout,
    QStyle,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from ghostline.ai.ai_client import AIClient
from ghostline.ai.context_engine import ContextChunk, ContextEngine
from ghostline.ai.model_registry import ModelDescriptor, ModelRegistry


@dataclass
class ChatMessage:
    """A single message in a chat transcript."""

    role: str
    text: str
    context: list[ContextChunk] | None = None


@dataclass
class ChatSession:
    """Stored chat conversation with a friendly title."""

    title: str
    messages: list[ChatMessage]
    created_at: datetime


class _FloatingPopover(QFrame):
    """Reusable floating popover with rounded corners and shadow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(
            """
            QFrame#floatingPopover {
                background: palette(base);
                border-radius: 12px;
                padding: 8px 10px;
            }
            QPushButton {
                border: none;
                padding: 8px 10px;
                border-radius: 8px;
                text-align: left;
            }
            QPushButton:hover {
                background: palette(alternate-base);
            }
            """
        )
        self.setObjectName("floatingPopover")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 6)
        shadow.setColor(self.palette().color(self.backgroundRole()).darker(140))
        self.setGraphicsEffect(shadow)


class _ChipButton(QToolButton):
    """Stylized pill chip with icon and hover state."""

    def __init__(self, text: str, icon: QIcon | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        if icon:
            self.setIcon(icon)
        self.setCheckable(False)
        self.setAutoRaise(True)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setStyleSheet(
            """
            QToolButton {
                background: rgba(255, 255, 255, 80);
                border: 1px solid palette(midlight);
                border-radius: 12px;
                padding: 6px 12px;
            }
            QToolButton:hover {
                background: rgba(255, 255, 255, 140);
            }
            """
        )


class _ModelRow(QFrame):
    """Clickable row representing a model option."""

    def __init__(
        self,
        model: ModelDescriptor,
        badge: str | None = None,
        description: str | None = None,
        parent: QWidget | None = None,
        on_select=None,
        disabled: bool = False,
        hint: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.on_select = on_select
        self.setObjectName("modelRow")
        self.setStyleSheet(
            """
            QFrame#modelRow {
                border-radius: 10px;
            }
            QFrame#modelRow:hover {
                background: palette(alternate-base);
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title = QLabel(model.label, self)
        title.setStyleSheet("font-weight: 600;")
        header.addWidget(title)
        provider_badge = QLabel(model.provider.capitalize(), self)
        provider_badge.setStyleSheet(
            "padding: 2px 6px; border-radius: 8px; background: palette(midlight); font-size: 11px;"
        )
        header.addWidget(provider_badge)
        if model.kind:
            kind_badge = QLabel(model.kind.title(), self)
            kind_badge.setStyleSheet(
                "padding: 2px 6px; border-radius: 8px; background: palette(mid); font-size: 11px;"
            )
            header.addWidget(kind_badge)
        header.addStretch()
        layout.addLayout(header)

        body = description or model.description
        if body:
            desc_label = QLabel(body, self)
            desc_label.setStyleSheet("color: palette(dark); font-size: 11px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        if badge:
            title.setText(f"{model.label} ({badge})")
        if disabled:
            self.setEnabled(False)
            if hint:
                self.setToolTip(hint)
        else:
            self.setToolTip(hint or "")

    def mousePressEvent(self, event):  # noqa: D401, N802
        """Emit selection when clicked."""
        super().mousePressEvent(event)
        if self.on_select and self.isEnabled():
            self.on_select(self.model)


class ModelSelectorPanel(QDialog):
    """Floating model selector sheet displayed above the dock."""

    model_selected = Signal(object)

    def __init__(
        self,
        models: list[ModelDescriptor],
        current_model: ModelDescriptor | None,
        has_openai_key: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.models = models
        self.has_openai_key = has_openai_key

        self.setStyleSheet(
            """
            QDialog#modelSelectorPanel {
                background: transparent;
            }
            QFrame#modelSelectorContainer {
                background: palette(base);
                border-radius: 14px;
            }
            QLineEdit#modelSearch {
                border: 1px solid palette(mid);
                border-radius: 10px;
                padding: 6px 10px 6px 30px;
            }
            QPushButton#groupByButton {
                border: 1px solid palette(midlight);
                border-radius: 10px;
                padding: 6px 10px;
            }
            QPushButton#groupByButton:hover {
                background: palette(alternate-base);
            }
            """
        )
        self.setObjectName("modelSelectorPanel")

        container = QFrame(self)
        container.setObjectName("modelSelectorContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(14, 14, 14, 14)
        container_layout.setSpacing(12)

        close_row = QHBoxLayout()
        close_row.setContentsMargins(0, 0, 0, 0)
        close_row.addStretch()
        close_btn = QToolButton(container)
        close_btn.setAutoRaise(True)
        close_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        close_btn.clicked.connect(self.close)
        close_row.addWidget(close_btn)
        container_layout.addLayout(close_row)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_icon = QLabel(container)
        search_icon.setText("🔍")
        search_icon.setStyleSheet("padding-left: 6px;")
        self.search_input = QLineEdit(container)
        self.search_input.setObjectName("modelSearch")
        self.search_input.setPlaceholderText("Search models")
        group_by = QPushButton("Group By", container)
        group_by.setObjectName("groupByButton")
        search_row.addWidget(search_icon)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(group_by)
        container_layout.addLayout(search_row)

        scroll = QScrollArea(container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)

        openai_models = [model for model in self.models if model.provider == "openai"]
        ollama_models = [model for model in self.models if model.provider == "ollama"]

        if openai_models:
            self._add_section(
                scroll_layout,
                "Recommended OpenAI models",
                openai_models,
                current_model,
                disable_openai=not self.has_openai_key,
            )
        else:
            hint = QLabel("Enable OpenAI models in AI Settings", scroll_content)
            hint.setStyleSheet("color: palette(dark);")
            scroll_layout.addWidget(hint)

        if ollama_models:
            self._add_section(
                scroll_layout,
                "Local Ollama models",
                ollama_models,
                current_model,
            )
        else:
            placeholder = QLabel("No local Ollama models found", scroll_content)
            placeholder.setStyleSheet("color: palette(dark);")
            scroll_layout.addWidget(placeholder)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        container_layout.addWidget(scroll, 1)

        shadow = QGraphicsDropShadowEffect(container)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 8)
        shadow.setColor(self.palette().color(self.backgroundRole()).darker(140))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(container)

    def _add_section(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        models: list[ModelDescriptor],
        current_model: ModelDescriptor | None,
        disable_openai: bool = False,
    ) -> None:
        label = QLabel(title, self)
        label.setStyleSheet("font-weight: 700;")
        parent_layout.addWidget(label)

        for model in models:
            hint = None
            disabled = disable_openai and model.provider == "openai"
            if disabled:
                hint = "Set OpenAI API key in AI Settings to use this model"
            row = _ModelRow(model, None, model.description, self, on_select=self.model_selected.emit, disabled=disabled, hint=hint)
            if current_model and model.id == current_model.id and model.provider == current_model.provider:
                row.setStyleSheet(
                    row.styleSheet()
                    + "\n#modelRow { border: 1px solid palette(mid); background: palette(alternate-base); }"
                )
            parent_layout.addWidget(row)
        parent_layout.addSpacing(6)

    def show_at(self, point: QPoint) -> None:
        self.adjustSize()
        self.move(point)
        self.show()


class AgentsDropdownPanel(QFrame):
    """Wide dropdown for browsing previous conversations."""

    def __init__(self, parent: QWidget | None = None, load_handler=None) -> None:
        super().__init__(parent)
        self.load_handler = load_handler
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("agentsDropdown")
        self.setStyleSheet(
            """
            QFrame#agentsDropdownContainer {
                background: palette(base);
                border-radius: 12px;
            }
            QLineEdit#agentsSearch {
                border: 1px solid palette(mid);
                border-radius: 10px;
                padding: 8px 10px;
            }
            QFrame#agentsRow {
                border-radius: 10px;
            }
            QFrame#agentsRow:hover {
                background: palette(alternate-base);
            }
            QLabel#conversationTitle {
                font-weight: 600;
            }
            QLabel#conversationMeta {
                color: palette(dark);
                font-size: 11px;
            }
            """
        )

        container = QFrame(self)
        container.setObjectName("agentsDropdownContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        self.search_input = QLineEdit(container)
        self.search_input.setObjectName("agentsSearch")
        self.search_input.setPlaceholderText("Search")
        top_row.addWidget(self.search_input, 1)
        all_label = QLabel("All Conversations", container)
        all_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        all_label.setStyleSheet("color: palette(dark); font-weight: 600;")
        top_row.addWidget(all_label, 0, Qt.AlignRight)
        container_layout.addLayout(top_row)

        scroll = QScrollArea(container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        self.list_layout = QVBoxLayout(scroll_content)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        scroll.setWidget(scroll_content)
        container_layout.addWidget(scroll, 1)

        shadow = QGraphicsDropShadowEffect(container)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 6)
        shadow.setColor(self.palette().color(self.backgroundRole()).darker(130))
        container.setGraphicsEffect(shadow)

        wrapper_layout = QVBoxLayout(self)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(container)

        self.search_input.textChanged.connect(self._filter)
        self._sessions: list[ChatSession] = []

    def _filter(self, term: str) -> None:
        self.populate(self._sessions, term)

    def populate(self, sessions: list[ChatSession], term: str = "") -> None:
        self._sessions = sessions
        for i in reversed(range(self.list_layout.count())):
            item = self.list_layout.takeAt(i)
            if item.widget():
                item.widget().deleteLater()
        lowered = term.lower()
        for session in sessions:
            if lowered and lowered not in session.title.lower():
                continue
            row = self._build_row(session)
            self.list_layout.addWidget(row)
        self.list_layout.addStretch()

    def _build_row(self, session: ChatSession) -> QWidget:
        row = QFrame(self)
        row.setObjectName("agentsRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        title = QLabel(session.title, row)
        title.setObjectName("conversationTitle")
        meta_text = self._format_timestamp(session.created_at)
        if session.messages:
            last_context = session.messages[-1].context
            if last_context:
                suffix = last_context[0].title
                if last_context[0].path:
                    suffix += f" — {last_context[0].path}"
                meta_text += f"  •  {suffix}"
        meta = QLabel(meta_text, row)
        meta.setObjectName("conversationMeta")
        layout.addWidget(title)
        layout.addWidget(meta)

        def _activate(_: object) -> None:
            if self.load_handler:
                self.load_handler(session)
            self.hide()

        row.mousePressEvent = _activate  # type: ignore[assignment]
        return row

    @staticmethod
    def _format_timestamp(dt: datetime) -> str:
        delta = datetime.now() - dt
        if delta.days >= 1:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours:
            return f"{hours}h ago"
        minutes = (delta.seconds % 3600) // 60
        if minutes:
            return f"{minutes}m ago"
        return "now"


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

    def __init__(
        self, client: AIClient, prompt: str, context: str | None, model: ModelDescriptor | None
    ) -> None:
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.context = context
        self.model = model

    @Slot()
    def run(self) -> None:
        try:
            text = ""
            for chunk in self.client.stream(self.prompt, context=self.context, model=self.model):
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
        self._current_messages: list[ChatMessage] = []
        self._current_chat_started_at: datetime = datetime.now()
        self.chat_history: list[ChatSession] = []
        self.model_registry = ModelRegistry(self.client.config)
        self.available_models: list[ModelDescriptor] = []
        self._has_openai_key = bool(self.model_registry._openai_settings().get("api_key"))
        self.current_model_descriptor: ModelDescriptor | None = None
        self._refresh_models(initial=True)
        self.current_mode = "Code"

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
            """
        )

        self.instructions = QTextEdit(self)
        self.instructions.setPlaceholderText("Optional: add custom instructions, tone, or constraints")
        self.instructions.hide()

        def _style_toolbar_button(button: QToolButton) -> None:
            button.setAutoRaise(True)
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setFixedSize(30, 30)
            button.setIconSize(QSize(18, 18))

        self.instructions_action = QAction("Instructions…", self)
        self.instructions_action.triggered.connect(self._open_instructions_dialog)

        self.agents_button = QPushButton("Agents", self)
        self.agents_button.setFlat(True)
        self.agents_button.setStyleSheet(
            "padding: 6px 10px; border: none; font-weight: 600; text-align: left;"
        )
        self.agents_button.clicked.connect(self._toggle_agents_dropdown)

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
        self.history_button.clicked.connect(self._open_history_dialog)

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
        self.status_indicator = QLabel(self)
        self.status_indicator.setObjectName("statusIndicator")
        self.status_indicator.setFixedSize(12, 12)
        self.status_indicator.setToolTip("AI assistant status")
        self.status_label = QLabel("AI Offline", self)
        self.status_label.setObjectName("statusLabel")
        self.status_label.setStyleSheet("color: palette(mid); font-size: 11px;")

        status_widget = QWidget(self)
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(10, 6, 10, 6)
        status_layout.setSpacing(8)
        status_layout.addWidget(self.status_indicator, 0, Qt.AlignVCenter)
        status_layout.addWidget(self.status_label, 1, Qt.AlignLeft)
        status_action = QWidgetAction(self)
        status_action.setDefaultWidget(status_widget)

        overflow_menu.addAction(status_action)
        overflow_menu.addSeparator()
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
        top_layout.setContentsMargins(10, 6, 10, 8)
        top_layout.setSpacing(12)
        top_layout.addWidget(self.agents_button)
        top_layout.addStretch()
        top_layout.addWidget(self.new_chat_button)
        top_layout.addWidget(self.history_button)
        top_layout.addWidget(self.tools_button)
        top_layout.addWidget(self.overflow_button)

        self._refresh_status_indicator()

        self.placeholder = QWidget(self)
        placeholder_layout = QVBoxLayout(self.placeholder)
        placeholder_layout.setContentsMargins(0, 16, 0, 16)
        placeholder_layout.setSpacing(14)
        placeholder_layout.setAlignment(Qt.AlignCenter)
        logo = QLabel("👻", self.placeholder)
        logo.setStyleSheet("font-size: 48px;")
        title = QLabel("Ghostline Studio", self.placeholder)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        subtitle = QLabel("Your AI teammate is ready to collaborate.", self.placeholder)
        subtitle.setStyleSheet("color: palette(dark);")
        placeholder_layout.addWidget(logo, 0, Qt.AlignHCenter)
        placeholder_layout.addWidget(title, 0, Qt.AlignHCenter)
        placeholder_layout.addWidget(subtitle, 0, Qt.AlignHCenter)

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
                border-radius: 24px;
                background: palette(base);
                padding: 2px;
            }
            QToolButton#inlineButton {
                border: none;
                background: transparent;
                border-radius: 14px;
                padding: 6px;
            }
            QToolButton#inlineButton:hover {
                background: palette(alternate-base);
            }
            """
        )
        shadow = QGraphicsDropShadowEffect(self.input_bar)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(self.palette().color(self.backgroundRole()).darker(130))
        self.input_bar.setGraphicsEffect(shadow)
        input_layout = QHBoxLayout(self.input_bar)
        input_layout.setContentsMargins(12, 10, 12, 10)
        input_layout.setSpacing(10)

        self.plus_button = QToolButton(self.input_bar)
        self.plus_button.setObjectName("inlineButton")
        self.plus_button.setText("+")
        self.plus_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.plus_button.clicked.connect(self._toggle_plus_menu)

        self.mic_button = QToolButton(self.input_bar)
        self.mic_button.setObjectName("inlineButton")
        self.mic_button.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))
        self.mic_button.setToolTip("Start voice input")
        self.mic_button.setCheckable(True)

        self.send_button = QToolButton(self.input_bar)
        self.send_button.setObjectName("inlineButton")
        self.send_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.send_button.setToolTip("Send")
        self.send_button.clicked.connect(self._send)

        input_layout.addWidget(self.plus_button)
        input_layout.addWidget(self.input, 1)
        input_layout.addWidget(self.mic_button)
        input_layout.addWidget(self.send_button)

        chips_row = QWidget(self)
        chips_row.setObjectName("chatChipRow")
        chips_row.setStyleSheet(
            """
            #chatChipRow {
                padding-left: 6px;
            }
            """
        )
        chips_layout = QHBoxLayout(chips_row)
        chips_layout.setContentsMargins(4, 0, 4, 4)
        chips_layout.setSpacing(8)

        self.mode_chip = _ChipButton(self.current_mode, self.style().standardIcon(QStyle.SP_FileDialogDetailedView), chips_row)
        self.mode_chip.clicked.connect(self._toggle_mode_menu)
        chips_layout.addWidget(self.mode_chip, 0, Qt.AlignLeft)

        model_label = self.current_model_descriptor.label if self.current_model_descriptor else "Select model"
        self.model_chip = _ChipButton(model_label, self.style().standardIcon(QStyle.SP_ComputerIcon), chips_row)
        self.model_chip.clicked.connect(self._open_model_selector)
        chips_layout.addWidget(self.model_chip, 0, Qt.AlignLeft)

        self._refresh_model_chip()

        chips_layout.addStretch()

        input_container = QFrame(self)
        input_container.setFrameShape(QFrame.NoFrame)
        input_container_layout = QVBoxLayout(input_container)
        input_container_layout.setContentsMargins(6, 0, 6, 0)
        input_container_layout.setSpacing(6)
        input_container_layout.addWidget(chips_row)
        input_container_layout.addWidget(self.input_bar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 40)
        layout.setSpacing(8)
        layout.addWidget(top_bar)
        layout.addWidget(transcript_container, 1)
        layout.addWidget(input_container)

        self.plus_menu: _FloatingPopover | None = None
        self.mode_popover: _FloatingPopover | None = None
        self.model_selector_panel: ModelSelectorPanel | None = None
        self.agents_panel: AgentsDropdownPanel | None = None

    def set_active_document_provider(self, provider) -> None:
        self.active_document_provider = provider

    def set_open_documents_provider(self, provider) -> None:
        self.open_documents_provider = provider

    def set_insert_handler(self, handler) -> None:
        self.insert_handler = handler

    def set_command_adapter(self, adapter) -> None:
        self.command_adapter = adapter

    def _snapshot_messages(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        return [
            ChatMessage(message.role, message.text, list(message.context or []))
            for message in messages
        ]

    def _derive_title(self, messages: list[ChatMessage]) -> str:
        for message in messages:
            if message.role.lower() == "you" and message.text:
                first_line = message.text.strip().splitlines()[0]
                if first_line:
                    return first_line[:60] + ("…" if len(first_line) > 60 else "")
        return f"Chat started {self._current_chat_started_at.strftime('%Y-%m-%d %H:%M')}"

    def _ensure_current_snapshot(self) -> None:
        if not self._current_messages:
            return
        snapshot = self._snapshot_messages(self._current_messages)
        session = ChatSession(
            self._derive_title(snapshot), snapshot, self._current_chat_started_at
        )
        if self.chat_history and self.chat_history[0].created_at == session.created_at:
            self.chat_history[0] = session
        else:
            self.chat_history.insert(0, session)

    def _toggle_plus_menu(self) -> None:
        if self.plus_menu and self.plus_menu.isVisible():
            self.plus_menu.hide()
            return
        if self.plus_menu:
            self.plus_menu.deleteLater()
        self.plus_menu = _FloatingPopover(self)
        layout = QVBoxLayout(self.plus_menu)
        for label in ["Mentions", "Trigger Workflow", "Upload Image"]:
            btn = QPushButton(label, self.plus_menu)
            btn.clicked.connect(self.plus_menu.hide)
            layout.addWidget(btn)

        anchor = self.plus_button.mapToGlobal(QPoint(self.plus_button.width() // 2, 0))
        self.plus_menu.adjustSize()
        x = anchor.x() - self.plus_menu.width() // 2
        y = anchor.y() - self.plus_menu.height() - 8
        self.plus_menu.move(x, y)
        self.plus_menu.show()

    def _toggle_mode_menu(self) -> None:
        if self.mode_popover and self.mode_popover.isVisible():
            self.mode_popover.hide()
            return
        if self.mode_popover:
            self.mode_popover.deleteLater()
        self.mode_popover = _FloatingPopover(self)
        layout = QVBoxLayout(self.mode_popover)
        layout.setContentsMargins(6, 6, 6, 6)
        modes = [
            ("Code", "Generate code with workspace context"),
            ("Chat", "General purpose conversation"),
        ]
        for mode, desc in modes:
            option = QFrame(self.mode_popover)
            option_layout = QVBoxLayout(option)
            option_layout.setContentsMargins(8, 6, 8, 6)
            title = QLabel(mode, option)
            title.setStyleSheet("font-weight: 600;")
            subtitle = QLabel(desc, option)
            subtitle.setWordWrap(True)
            subtitle.setStyleSheet("color: palette(dark); font-size: 11px;")
            option_layout.addWidget(title)
            option_layout.addWidget(subtitle)
            option.mousePressEvent = lambda _event, m=mode: self._set_mode(m)  # type: ignore[assignment]
            layout.addWidget(option)

        anchor = self.mode_chip.mapToGlobal(QPoint(self.mode_chip.width() // 2, 0))
        self.mode_popover.adjustSize()
        x = anchor.x() - self.mode_popover.width() // 2
        y = anchor.y() - self.mode_popover.height() - 8
        self.mode_popover.move(x, y)
        self.mode_popover.show()

    def _set_mode(self, mode: str) -> None:
        self.current_mode = mode
        self.mode_chip.setText(mode)
        if self.mode_popover:
            self.mode_popover.hide()

    def _refresh_models(self, initial: bool = False) -> None:
        self.available_models = []
        try:
            self.available_models.extend(self.model_registry.enabled_openai_models())
        except Exception:  # noqa: BLE001
            pass
        try:
            self.available_models.extend(self.model_registry.ollama_models())
        except Exception:  # noqa: BLE001
            pass

        fallback: ModelDescriptor | None = None
        if not self.available_models:
            openai_candidates = self.model_registry.openai_models()
            fallback = openai_candidates[0] if openai_candidates else None

        chosen = self._choose_default_model(initial, fallback)
        if chosen:
            self.current_model_descriptor = chosen
        self._has_openai_key = bool(self.model_registry._openai_settings().get("api_key"))
        if hasattr(self, "model_chip"):
            self._refresh_model_chip()

    def _choose_default_model(
        self, initial: bool = False, fallback: ModelDescriptor | None = None
    ) -> ModelDescriptor | None:
        last_used = self.model_registry.last_used_model()
        if last_used:
            for model in self.available_models:
                if model.id == last_used.id and model.provider == last_used.provider:
                    return model
            if not initial:
                return last_used
        if self.available_models:
            return self.available_models[0]
        return fallback

    def _refresh_model_chip(self) -> None:
        label = self.current_model_descriptor.label if self.current_model_descriptor else "Select model"
        tooltip_parts = []
        if self.current_model_descriptor:
            tooltip_parts.append(self.current_model_descriptor.provider.capitalize())
            if not self._has_openai_key and self.current_model_descriptor.provider == "openai":
                tooltip_parts.append("Set OpenAI API key in AI Settings to use cloud models")
        tooltip = " | ".join(tooltip_parts) or "Choose a model"
        self.model_chip.setText(label)
        self.model_chip.setToolTip(tooltip)

    def _open_model_selector(self) -> None:
        if self.model_selector_panel and self.model_selector_panel.isVisible():
            self.model_selector_panel.hide()
            return
        self._refresh_models()
        self.model_selector_panel = ModelSelectorPanel(
            self.available_models,
            self.current_model_descriptor,
            self._has_openai_key,
            self,
        )
        self.model_selector_panel.model_selected.connect(self._select_model)
        size_hint = self.model_selector_panel.sizeHint()
        anchor = self.input_bar.mapToGlobal(QPoint(self.input_bar.width() - size_hint.width(), 0))
        y = anchor.y() - size_hint.height() - 12
        self.model_selector_panel.show_at(QPoint(max(anchor.x(), 10), max(y, 10)))

    def _select_model(self, model: ModelDescriptor) -> None:
        self.current_model_descriptor = model
        self.model_registry.set_last_used_model(model)
        self._refresh_model_chip()
        self.client.active_model = model
        try:
            self.client.config.save()
        except Exception:  # noqa: BLE001
            pass
        if self.model_selector_panel:
            self.model_selector_panel.hide()

    def _toggle_agents_dropdown(self) -> None:
        if self.agents_panel and self.agents_panel.isVisible():
            self.agents_panel.hide()
            return
        self._ensure_current_snapshot()
        if not self.agents_panel:
            self.agents_panel = AgentsDropdownPanel(self, load_handler=self._restore_session)
        self.agents_panel.populate(self.chat_history)
        self.agents_panel.search_input.clear()
        self.agents_panel.resize(self.width() - 32, int(self.height() * 0.45))
        pos = self.agents_button.mapToGlobal(QPoint(0, self.agents_button.height()))
        self.agents_panel.move(pos.x(), pos.y() + 6)
        self.agents_panel.show()

    def _store_current_chat(self) -> None:
        if not self._current_messages:
            return
        self._ensure_current_snapshot()
        self._current_messages = []
        self._current_chat_started_at = datetime.now()

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
        self._store_current_chat()
        self.transcript_list.clear()
        self._active_response_card = None
        self._active_response_text = ""
        self._current_messages = []
        self._current_chat_started_at = datetime.now()
        self.transcript_stack.setCurrentWidget(self.placeholder)

    def _render_history_preview(self, session: ChatSession) -> str:
        lines = [
            session.title,
            session.created_at.strftime("%Y-%m-%d %H:%M"),
        ]
        for message in session.messages:
            context_suffix = ""
            if message.context:
                context_suffix = " (" + ", ".join(chunk.title for chunk in message.context) + ")"
            body = message.text.strip() or "[empty]"
            lines.append(f"{message.role}{context_suffix}:\n{body}")
        return "\n\n".join(lines)

    def _restore_session(self, session: ChatSession) -> None:
        self.transcript_list.clear()
        self.transcript_stack.setCurrentWidget(self.transcript_list)
        self._current_messages = self._snapshot_messages(session.messages)
        for message in self._current_messages:
            self._append(message.role, message.text, context=message.context)
        self._active_response_card = None
        self._active_response_text = ""
        self._current_chat_started_at = session.created_at

    def _delete_history_item(
        self, item: QListWidgetItem | None, list_widget: QListWidget, preview: QTextEdit
    ) -> None:
        if not item:
            return
        session = item.data(Qt.UserRole)
        if session in self.chat_history:
            self.chat_history.remove(session)
        row = list_widget.row(item)
        removed = list_widget.takeItem(row)
        if removed:
            removed.setData(Qt.UserRole, None)
        preview.clear()

    def _load_history_item(self, item: QListWidgetItem | None, dialog: QDialog) -> None:
        if not item:
            return
        session = item.data(Qt.UserRole)
        if not session:
            return
        self._restore_session(session)
        dialog.accept()

    def _open_history_dialog(self) -> None:
        self._ensure_current_snapshot()
        dialog = QDialog(self)
        dialog.setWindowTitle("Chat history")
        layout = QVBoxLayout(dialog)

        if not self.chat_history:
            layout.addWidget(QLabel("No chats yet. Start a conversation to build history.", dialog))
            buttons = QDialogButtonBox(QDialogButtonBox.Close, dialog)
            buttons.rejected.connect(dialog.reject)
            buttons.accepted.connect(dialog.accept)
            layout.addWidget(buttons)
            dialog.exec()
            return

        list_widget = QListWidget(dialog)
        list_widget.setSelectionMode(QListWidget.SingleSelection)
        list_widget.setMinimumHeight(240)
        for session in self.chat_history:
            summary = f"{session.title} — {session.created_at.strftime('%b %d, %H:%M')}"
            item = QListWidgetItem(summary, list_widget)
            item.setData(Qt.UserRole, session)
        layout.addWidget(list_widget)

        preview = QTextEdit(dialog)
        preview.setReadOnly(True)
        layout.addWidget(preview)

        def _update_preview() -> None:
            item = list_widget.currentItem()
            if not item:
                preview.clear()
                return
            session = item.data(Qt.UserRole)
            if session:
                preview.setPlainText(self._render_history_preview(session))
            else:
                preview.clear()

        list_widget.currentItemChanged.connect(lambda *_: _update_preview())

        buttons = QDialogButtonBox(QDialogButtonBox.Close, dialog)
        load_btn = buttons.addButton("Load conversation", QDialogButtonBox.AcceptRole)
        delete_btn = buttons.addButton("Delete", QDialogButtonBox.DestructiveRole)
        load_btn.clicked.connect(lambda: self._load_history_item(list_widget.currentItem(), dialog))
        delete_btn.clicked.connect(
            lambda: self._delete_history_item(list_widget.currentItem(), list_widget, preview)
        )
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        if list_widget.count():
            list_widget.setCurrentRow(0)
            _update_preview()

        dialog.exec()

    def _set_busy(self, busy: bool) -> None:
        enabled = not busy and self.workspace_active
        self.input.setEnabled(enabled)
        for button in (
            self.send_button,
            self.mic_button,
            self.plus_button,
            self.mode_chip,
            self.model_chip,
            self.agents_button,
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
        self._current_messages.append(ChatMessage("AI", text, list(self._last_chunks)))
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
        self._current_messages.append(ChatMessage("AI", message, list(self._last_chunks)))
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
        self._current_messages.append(
            ChatMessage("You", prompt, list(self._last_chunks))
        )
        self._set_busy(True)

        thread = QThread(self)
        worker = _AIRequestWorker(self.client, prompt, context, self.current_model_descriptor)
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
        self.status_label.setText(tooltip)

    def _update_pinned_badge(self, count: int) -> None:
        tooltip_suffix = f" ({count} pinned)" if count else ""
        self.tools_button.setToolTip(f"Context and tools{tooltip_suffix}")

    @Slot(str)
    def _on_worker_partial(self, delta: str) -> None:
        if not self._active_response_card:
            return
        self._active_response_text += delta
        self._active_response_card.set_text(self._active_response_text)

