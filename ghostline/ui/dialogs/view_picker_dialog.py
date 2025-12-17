from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QScrollArea, QVBoxLayout, QWidget


class ViewPickerDialog(QDialog):
    """Dialog that lists available view toggles and lets the user enable/disable them."""

    def __init__(self, actions: list, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("View Picker")
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Toggle panels and interface elements:", self))

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        inner = QWidget(scroll)
        self.inner_layout = QVBoxLayout(inner)
        self.inner_layout.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._populate(actions)

    def _populate(self, actions: list) -> None:
        for action in actions:
            if not action.isCheckable():
                continue
            box = QCheckBox(action.text(), self)
            box.setChecked(action.isChecked())
            box.toggled.connect(action.setChecked)
            self.inner_layout.addWidget(box)
        self.inner_layout.addStretch(1)
