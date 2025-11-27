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
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(QLabel("Latest Runtime Observations"))
        layout.addWidget(self.events)
        layout.addWidget(self.refresh_button)
        self.setWidget(content)
        self.setMinimumWidth(260)

        self.refresh_button.clicked.connect(self._refresh)
        self.inspector.observation_added.connect(lambda _: self._refresh())

        self._refresh()

    def _refresh(self) -> None:
        self.events.clear()
        observations = list(self.inspector.recent())
        if not observations:
            self.events.addItem("No runtime observations yet. Run a pipeline or debug session to populate this log.")
            return

        for obs in observations:
            summary = f"{obs.path}: calls={len(obs.calls)} error={obs.error or 'none'}"
            item = QListWidgetItem(summary)
            item.setData(0x0100, obs)
            self.events.addItem(item)
