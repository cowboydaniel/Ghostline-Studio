"""UI panel for the multi-process build manager."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QListWidget, QListWidgetItem, QTextEdit, QVBoxLayout, QWidget

from ghostline.build.build_manager import BuildManager


class BuildPanel(QDockWidget):
    def __init__(self, build_manager: BuildManager, parent=None) -> None:
        super().__init__("Build Panel", parent)
        self.build_manager = build_manager
        self.running = QListWidget(self)
        self.queue = QListWidget(self)
        self.logs = QTextEdit(self)
        self.logs.setReadOnly(True)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.running)
        layout.addWidget(self.queue)
        layout.addWidget(self.logs)
        self.setWidget(content)

        self.build_manager.task_started.connect(self._on_task_started)
        self.build_manager.task_finished.connect(self._on_task_finished)
        self.build_manager.task_output.connect(self._on_output)
        self.build_manager.queue_changed.connect(self._on_queue_changed)

    def _on_task_started(self, name: str) -> None:
        self.running.addItem(name)

    def _on_task_finished(self, name: str, code: int) -> None:
        items = self.running.findItems(name, Qt.MatchExactly)
        for item in items:
            row = self.running.row(item)
            self.running.takeItem(row)
        self.logs.append(f"{name} finished with code {code}")

    def _on_output(self, name: str, line: str) -> None:
        self.logs.append(f"[{name}] {line}")

    def _on_queue_changed(self, queue: list[str]) -> None:
        self.queue.clear()
        for item in queue:
            self.queue.addItem(QListWidgetItem(item))

