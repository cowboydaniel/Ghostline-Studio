"""Dock widget for runtime inspector."""
from __future__ import annotations

from PySide6.QtWidgets import QDockWidget, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from ghostline.runtime.inspector import RuntimeInspector, RuntimeObservation


class RuntimePanel(QDockWidget):
    def __init__(self, inspector: RuntimeInspector, parent=None) -> None:
        super().__init__("Runtime Inspector", parent)
        self.inspector = inspector

        self.events = QListWidget(self)
        self.refresh_button = QPushButton("Refresh")

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.addWidget(QLabel("Latest runtime observations"))
        layout.addWidget(self.events)
        layout.addWidget(self.refresh_button)
        self.setWidget(content)

        self.refresh_button.clicked.connect(self._refresh)
        self.inspector.observation_added.connect(lambda _: self._refresh())

        self._refresh()

    def _refresh(self) -> None:
        self.events.clear()
        for obs in self.inspector.recent():
            summary = f"{obs.path}: calls={len(obs.calls)} error={obs.error or 'none'}"
            item = QListWidgetItem(summary)
            item.setData(0x0100, obs)
            self.events.addItem(item)
