"""Full-window welcome portal."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class WelcomePortal(QWidget):
    """Modern welcome screen showing quick starts and templates."""

    startRequested = Signal()
    recentRequested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.recent = QListWidget(self)
        self.recent.setObjectName("WelcomeRecentList")
        self.recent.itemActivated.connect(self._emit_recent_requested)

        self.start_button = QPushButton("Open Folder…")
        self.start_button.clicked.connect(self.startRequested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self._content_widget = QWidget(self)
        # Use size policy instead of fixed maximum for better responsiveness
        self._content_widget.setMaximumWidth(640)  # Increased from 560
        self._content_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        container_layout = QVBoxLayout(self._content_widget)
        container_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        container_layout.setSpacing(16)

        center_card = QWidget(self._content_widget)
        # Removed fixed maximum width - will inherit from parent
        center_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        card_layout = QVBoxLayout(center_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(16)

        title = QLabel("Welcome to Ghostline Studio", self)
        title.setAlignment(Qt.AlignCenter)
        title.setProperty("class", "hero")

        subtitle = QLabel("Open a folder to start coding or pick a recent project.", self)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        card_layout.addWidget(self.start_button, alignment=Qt.AlignCenter)

        recent_label = QLabel("Recent Projects", self)
        recent_label.setAlignment(Qt.AlignLeft)
        card_layout.addWidget(recent_label)
        card_layout.addWidget(self.recent)

        container_layout.addWidget(center_card, alignment=Qt.AlignHCenter)
        layout.addWidget(self._content_widget, alignment=Qt.AlignHCenter)
        layout.addStretch(1)

    def set_recents(self, items: list[str]) -> None:
        self.recent.clear()
        if not items:
            placeholder = QListWidgetItem("No recent workspaces yet")
            placeholder.setFlags(Qt.NoItemFlags)
            self.recent.addItem(placeholder)
            return

        for path in items:
            name = Path(path).name if path else "Unknown"
            item = QListWidgetItem(f"{name}\n{path}")
            item.setData(Qt.UserRole, path)
            self.recent.addItem(item)

    def _emit_recent_requested(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self.recentRequested.emit(str(path))
