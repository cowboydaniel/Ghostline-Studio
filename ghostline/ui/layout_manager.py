"""Manage workspace layouts for different roles."""
from __future__ import annotations

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QMainWindow


class LayoutManager:
    def __init__(self, window: QMainWindow) -> None:
        self.window = window
        self._saved: dict[str, QByteArray] = {}

    def apply_mode(self, mode: str) -> None:
        state = self._saved.get(mode)
        if state:
            self.window.restoreState(state)
            enforce = getattr(self.window, "_enforce_dock_policies", None)
            if callable(enforce):
                enforce()

    def save_mode(self, mode: str) -> None:
        self._saved[mode] = QByteArray(self.window.saveState())

    def available_modes(self) -> list[str]:
        return ["Development", "Debug", "Writing", "Minimal"]
