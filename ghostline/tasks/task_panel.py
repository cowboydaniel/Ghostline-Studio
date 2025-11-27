"""Dockable panel that lists tasks and shows output."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class TaskPanel(QWidget):
    def __init__(self, task_manager, parent=None) -> None:
        super().__init__(parent)
        self.task_manager = task_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.empty_label = QLabel("No tasks loaded yet.", self)
        self.empty_label.setWordWrap(True)

        self.task_list = QListWidget(self)

        list_container = QStackedLayout()
        list_container.setContentsMargins(0, 0, 0, 0)
        list_container.addWidget(self.empty_label)
        list_container.addWidget(self.task_list)
        layout.addLayout(list_container)
        self.list_container = list_container

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
        if not tasks:
            self._show_empty_state(True)
            return

        for task in tasks:
            self.task_list.addItem(task.name)
        self._show_empty_state(False)

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

    def _show_empty_state(self, show_empty: bool) -> None:
        target = self.empty_label if show_empty else self.task_list
        self.list_container.setCurrentWidget(target)

