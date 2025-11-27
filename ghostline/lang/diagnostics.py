"""Diagnostics model for editor and UI panels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from PySide6.QtGui import QStandardItem, QStandardItemModel


@dataclass
class Diagnostic:
    file: str
    line: int
    col: int
    severity: str
    message: str


class DiagnosticsModel(QStandardItemModel):
    """Simple table-like model to display diagnostics."""

    headers = ["File", "Line", "Column", "Severity", "Message"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHorizontalHeaderLabels(self.headers)

    def set_diagnostics(self, diagnostics: Iterable[Diagnostic]) -> None:
        self.clear()
        self.setHorizontalHeaderLabels(self.headers)
        for diag in diagnostics:
            self.appendRow(self._items_for_diag(diag))

    def _items_for_diag(self, diag: Diagnostic) -> List[QStandardItem]:
        return [
            QStandardItem(str(diag.file)),
            QStandardItem(str(diag.line + 1)),
            QStandardItem(str(diag.col + 1)),
            QStandardItem(diag.severity),
            QStandardItem(diag.message),
        ]

