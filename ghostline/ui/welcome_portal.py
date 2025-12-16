"""Full-window welcome portal with Windsurf-style design."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ghostline.core.config import ConfigManager


class WelcomePortal(QWidget):
    """Windsurf-style welcome screen with quick actions and shortcuts."""

    openFolderRequested = Signal()
    openCommandPaletteRequested = Signal()
    openAIChatRequested = Signal()
    openRecentRequested = Signal(str)

    def __init__(self, parent=None, config: ConfigManager | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WelcomePortal")
        self.config = config
        self._story_dialog: QDialog | None = None
        self._ascii_timer: QTimer | None = None
        self._ascii_frames: list[str] = []
        self._ascii_frame_index = 0

        # Main layout - centered content
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(48, 48, 48, 48)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignCenter)

        # Content container for centering
        content_widget = QWidget(self)
        content_widget.setMaximumWidth(800)
        content_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(32)
        content_layout.setAlignment(Qt.AlignCenter)

        # Title section
        self.title = QLabel("Ghostline Studio", self)
        self.title.setObjectName("WelcomeTitle")
        self.title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(48)
        title_font.setBold(True)
        self.title.setFont(title_font)

        self.subtitle = QLabel("Getting started with Ghostline Studio", self)
        self.subtitle.setObjectName("WelcomeSubtitle")
        self.subtitle.setAlignment(Qt.AlignCenter)
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        self.subtitle.setFont(subtitle_font)

        self.title.installEventFilter(self)
        self.subtitle.installEventFilter(self)
        if self._insider_hint_enabled():
            hint_text = "double-click for a surprise"
            self.title.setToolTip(hint_text)
            self.subtitle.setToolTip(hint_text)

        # Add spacing after subtitle
        content_layout.addWidget(self.title)
        content_layout.addSpacing(8)
        content_layout.addWidget(self.subtitle)
        content_layout.addSpacing(40)

        # Quick actions container
        actions_container = QWidget(content_widget)
        actions_container.setMaximumWidth(600)
        actions_layout = QVBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(12)

        # Create quick action items
        self._add_quick_action(
            actions_layout,
            "Code with Ghostline AI",
            "Ctrl+L",
            self.openAIChatRequested.emit,
        )
        self._add_quick_action(
            actions_layout,
            "Open Command Palette",
            "Ctrl+Shift+P",
            self.openCommandPaletteRequested.emit,
        )
        self._add_quick_action(
            actions_layout,
            "Open Folder",
            "Ctrl+K Ctrl+O",
            self.openFolderRequested.emit,
        )

        content_layout.addWidget(actions_container, alignment=Qt.AlignCenter)
        content_layout.addSpacing(16)

        self.recent_files = QListWidget(self)
        self.recent_files.setObjectName("WelcomeRecents")
        self.recent_files.itemActivated.connect(lambda item: self._open_recent(item))

        content_layout.addWidget(QLabel("Recent Files", self), alignment=Qt.AlignCenter)
        content_layout.addWidget(self.recent_files)
        content_layout.addStretch(1)

        main_layout.addWidget(content_widget, alignment=Qt.AlignCenter)

    def set_recent_files(self, files: list[str]) -> None:
        self.recent_files.clear()
        added = False
        for path in files:
            added = True
            item = QListWidgetItem(path)
            item.setData(Qt.UserRole, path)
            self.recent_files.addItem(item)
        if not added:
            placeholder = QListWidgetItem("No recent files. Open a workspace to get started.")
            placeholder.setFlags(Qt.NoItemFlags)
            self.recent_files.addItem(placeholder)

    def _open_recent(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self.openRecentRequested.emit(str(path))

    def _add_quick_action(
        self,
        layout: QVBoxLayout,
        label_text: str,
        shortcut_text: str,
        callback,
    ) -> None:
        """Add a quick action row with label and keyboard shortcut."""
        action_widget = QWidget()
        action_widget.setObjectName("WelcomeAction")
        action_widget.setCursor(Qt.PointingHandCursor)
        action_widget.mousePressEvent = lambda event: callback()

        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(16, 12, 16, 12)
        action_layout.setSpacing(16)

        # Action label
        action_label = QLabel(label_text)
        action_label.setObjectName("WelcomeActionLabel")
        label_font = QFont()
        label_font.setPointSize(13)
        action_label.setFont(label_font)

        # Spacer
        action_layout.addWidget(action_label)
        action_layout.addStretch(1)

        # Keyboard shortcut pill
        shortcut_label = QLabel(shortcut_text)
        shortcut_label.setObjectName("WelcomeShortcut")
        shortcut_font = QFont()
        shortcut_font.setPointSize(11)
        shortcut_label.setFont(shortcut_font)
        shortcut_label.setAlignment(Qt.AlignCenter)

        action_layout.addWidget(shortcut_label)

        layout.addWidget(action_widget)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if event.type() == QEvent.MouseButtonDblClick and watched in {self.title, self.subtitle}:
            self._show_story_dialog()
            return True
        return super().eventFilter(watched, event)

    def _show_story_dialog(self) -> None:
        if self._story_dialog and self._story_dialog.isVisible():
            self._story_dialog.raise_()
            self._story_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Ghostline Lore")
        dialog.setModal(False)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        art_label = QLabel(dialog)
        art_label.setAlignment(Qt.AlignCenter)
        art_font = QFont("monospace")
        art_font.setStyleHint(QFont.Monospace)
        art_font.setPointSize(11)
        art_label.setFont(art_font)
        art_label.setObjectName("GhostlineAsciiArt")

        story = QLabel(
            "An engineer named Echo traced spectral logs through midnight terminals, "
            "teaching a curious ghost to read code and whisper refactors back. "
            "That apprentice spirit became Ghostline—guiding builders through every haunted stack.",
            dialog,
        )
        story.setWordWrap(True)
        story.setAlignment(Qt.AlignCenter)

        layout.addWidget(art_label)
        layout.addWidget(story)

        base_frame = "\n".join(
            [
                "  .-.",
                " (o o)",
                " | O \\",
                "  \\   \\",
                "   `~~~'",
            ]
        )
        trailing_frame = "\n".join(
            [
                "  .-.",
                " (o o)",
                " | O \\",
                "  \\   \\",
                "   `~~~'   ~",
            ]
        )
        self._ascii_frames = [base_frame, trailing_frame]
        self._ascii_frame_index = 0
        art_label.setText(self._ascii_frames[self._ascii_frame_index])

        self._ascii_timer = QTimer(dialog)
        self._ascii_timer.timeout.connect(lambda: self._cycle_ascii_frame(art_label))
        self._ascii_timer.start(420)

        dialog.finished.connect(self._teardown_story_dialog)

        self._story_dialog = dialog
        dialog.show()

    def _cycle_ascii_frame(self, art_label: QLabel) -> None:
        if not self._ascii_frames:
            return
        self._ascii_frame_index = (self._ascii_frame_index + 1) % len(self._ascii_frames)
        art_label.setText(self._ascii_frames[self._ascii_frame_index])

    def _teardown_story_dialog(self) -> None:
        if self._ascii_timer:
            self._ascii_timer.stop()
            self._ascii_timer = None
        self._story_dialog = None
        self._ascii_frames = []
        self._ascii_frame_index = 0

    def _insider_hint_enabled(self) -> bool:
        if not self.config:
            return False
        debug_cfg = self.config.get("debug", {})
        if isinstance(debug_cfg, dict) and debug_cfg.get("insider"):
            return True
        return bool(self.config.get("insider", False))
