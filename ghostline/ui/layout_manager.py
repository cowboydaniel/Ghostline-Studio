"""Manage workspace layouts for different roles."""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow


class LayoutManager:
    def __init__(self, window: QMainWindow) -> None:
        self.window = window
        self._saved: dict[str, bytes] = {}

    def apply_mode(self, mode: str) -> None:
        state = self._saved.get(mode)
        if state:
            self.window.restoreState(state)

    def save_mode(self, mode: str) -> None:
        self._saved[mode] = self.window.saveState()

    def available_modes(self) -> list[str]:
        return ["Development", "Debug", "Writing", "Minimal"]
