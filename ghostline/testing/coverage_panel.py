"""Coverage display panel."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class CoveragePanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["File", "Coverage %"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.empty_label = QLabel("Run tests to see coverage results.", self)
        self.empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.table)
        self._update_empty_state(True)

    def update_coverage(self, data: list[tuple[str, float]]) -> None:
        self.table.setRowCount(len(data))
        for row, (path, percent) in enumerate(data):
            self.table.setItem(row, 0, QTableWidgetItem(path))
            self.table.setItem(row, 1, QTableWidgetItem(f"{percent:.1f}%"))
        self._update_empty_state(len(data) == 0)

    def _update_empty_state(self, is_empty: bool) -> None:
        self.table.setVisible(not is_empty)
        self.empty_label.setVisible(is_empty)
