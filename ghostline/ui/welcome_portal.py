"""Full-window welcome portal with Windsurf-style design."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class WelcomePortal(QWidget):
    """Windsurf-style welcome screen with quick actions and shortcuts."""

    openFolderRequested = Signal()
    openCommandPaletteRequested = Signal()
    openAIChatRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("WelcomePortal")

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
        title = QLabel("Ghostline Studio", self)
        title.setObjectName("WelcomeTitle")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(48)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel("Getting started with Ghostline Studio", self)
        subtitle.setObjectName("WelcomeSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle.setFont(subtitle_font)

        # Add spacing after subtitle
        content_layout.addWidget(title)
        content_layout.addSpacing(8)
        content_layout.addWidget(subtitle)
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
            self.openAIChatRequested.emit
        )
        self._add_quick_action(
            actions_layout,
            "Open Command Palette",
            "Ctrl+Shift+P",
            self.openCommandPaletteRequested.emit
        )
        self._add_quick_action(
            actions_layout,
            "Open Folder",
            "Ctrl+K Ctrl+O",
            self.openFolderRequested.emit
        )

        content_layout.addWidget(actions_container, alignment=Qt.AlignCenter)
        content_layout.addStretch(1)

        main_layout.addWidget(content_widget, alignment=Qt.AlignCenter)

    def _add_quick_action(
        self,
        layout: QVBoxLayout,
        label_text: str,
        shortcut_text: str,
        callback
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
