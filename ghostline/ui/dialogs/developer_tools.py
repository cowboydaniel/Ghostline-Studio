"""Developer and diagnostics dialogs for Ghostline."""
from __future__ import annotations

import importlib.util
import os
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QPlainTextEdit,
)


class DeveloperToolsDialog(QDialog):
    """Simple diagnostics viewer for log output."""

    def __init__(self, log_path: str, parent=None) -> None:
        super().__init__(parent)
        self._log_path = log_path
        self.setWindowTitle("Developer Tools")
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QLabel(f"Diagnostics log: {self._log_path}", self)
        header.setWordWrap(True)
        layout.addWidget(header)

        controls = QHBoxLayout()
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.clicked.connect(self.refresh)
        open_btn = QPushButton("Open log folder", self)
        open_btn.clicked.connect(self._open_folder)
        controls.addWidget(refresh_btn)
        controls.addWidget(open_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.viewer = QPlainTextEdit(self)
        self.viewer.setReadOnly(True)
        self.viewer.setMinimumSize(420, 260)
        layout.addWidget(self.viewer)

        self.refresh()

    def _open_folder(self) -> None:
        folder = os.path.dirname(self._log_path)
        os.makedirs(folder, exist_ok=True)
        os.system(f"xdg-open '{folder}' >/dev/null 2>&1 &")

    def refresh(self) -> None:
        try:
            with open(self._log_path, "r", encoding="utf-8") as handle:
                content = handle.read()
        except FileNotFoundError:
            content = "Log file not found yet. Perform an action to generate logs."
        except Exception as exc:  # noqa: BLE001
            content = f"Failed to read log file:\n{exc}"
        self.viewer.setPlainText(content)


class ProcessExplorerDialog(QDialog):
    """Display process information for Ghostline and active tools."""

    def __init__(self, provider: Callable[[], list[dict]], parent=None) -> None:
        super().__init__(parent)
        self._provider = provider
        self.setWindowTitle("Process Explorer")
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Live view of Ghostline process activity.", self))

        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "PID", "CPU", "Memory", "Details"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        controls = QHBoxLayout()
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.clicked.connect(self.refresh)
        controls.addWidget(refresh_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.refresh()

    def refresh(self) -> None:
        records = self._provider()
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            for col, key in enumerate(["name", "type", "pid", "cpu", "memory", "details"]):
                value = record.get(key, "n/a")
                item = QTableWidgetItem(str(value))
                if key in {"pid", "cpu", "memory"}:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()


def optional_psutil():
    """Return psutil module if available without requiring it."""
    spec = importlib.util.find_spec("psutil")
    if spec is None:
        return None
    import psutil  # type: ignore[import-not-found]

    return psutil
