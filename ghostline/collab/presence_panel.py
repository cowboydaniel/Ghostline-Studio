"""UI panel showing collaborators and active files."""
from __future__ import annotations

from PySide6.QtWidgets import QListWidget, QVBoxLayout, QWidget


class PresencePanel(QWidget):
    def __init__(self, session_manager, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.list = QListWidget(self)
        layout.addWidget(self.list)
        session_manager.presence_changed.connect(self._update_list)

    def _update_list(self, participants: list[str]) -> None:
        self.list.clear()
        for user in participants:
            self.list.addItem(user)
