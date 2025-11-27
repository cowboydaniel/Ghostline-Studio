"""Dockable panel that lists tasks and shows output."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QPushButton, QTextEdit, QVBoxLayout, QWidget


class TaskPanel(QWidget):
    def __init__(self, task_manager, parent=None) -> None:
        super().__init__(parent)
        self.task_manager = task_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.task_list = QListWidget(self)
        self.task_list.setPlaceholderText("No tasks loaded yet.")
        layout.addWidget(self.task_list)

        controls = QHBoxLayout()
        controls.setSpacing(6)
        self.run_button = QPushButton("Run Task", self)
        self.stop_button = QPushButton("Stop", self)
        controls.addWidget(self.run_button)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)

        self.output = QTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Task output will appear here when a task runs.")
        layout.addWidget(self.output)

        self.run_button.clicked.connect(self._run_selected)
        self.stop_button.clicked.connect(self.task_manager.stop)

        self.task_manager.tasks_loaded.connect(self._populate)
        self.task_manager.output.connect(self._append_output)
        self.task_manager.state_changed.connect(self._update_state)

    def _populate(self, tasks) -> None:
        self.task_list.clear()
        for task in tasks:
            self.task_list.addItem(task.name)

    def _append_output(self, text: str) -> None:
        self.output.append(text)

    def _update_state(self, state: str) -> None:
        self.run_button.setEnabled(state != "running")
        self.stop_button.setEnabled(state == "running")

    def _run_selected(self) -> None:
        item = self.task_list.currentItem()
        if not item:
            return
        self.task_manager.run_task(item.text())

