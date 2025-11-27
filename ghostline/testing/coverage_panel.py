"""Coverage display panel."""
from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class CoveragePanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["File", "Coverage %"])
        layout.addWidget(self.table)

    def update_coverage(self, data: list[tuple[str, float]]) -> None:
        self.table.setRowCount(len(data))
        for row, (path, percent) in enumerate(data):
            self.table.setItem(row, 0, QTableWidgetItem(path))
            self.table.setItem(row, 1, QTableWidgetItem(f"{percent:.1f}%"))
