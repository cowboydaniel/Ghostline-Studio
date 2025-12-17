"""Dockable panel that lists tasks and shows output."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
        self.build_button = QPushButton("Run Build", self)
        self.restart_button = QPushButton("Restart", self)
        self.stop_button = QPushButton("Terminate", self)
        self.configure_button = QPushButton("Configure Tasks", self)
        controls.addWidget(self.run_button)
        controls.addWidget(self.build_button)
        controls.addWidget(self.restart_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.configure_button)
        layout.addLayout(controls)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        status_label = QLabel("Running Tasks", self)
        self.running_tasks = QListWidget(self)
        status_row.addWidget(status_label)
        status_row.addWidget(self.running_tasks, 1)
        layout.addLayout(status_row)

        self.output = QTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Task output will appear here when a task runs.")
        layout.addWidget(self.output)

        self.run_button.clicked.connect(self._run_selected)
        self.build_button.clicked.connect(self.task_manager.run_build_task)
        self.restart_button.clicked.connect(self._restart_selected)
        self.stop_button.clicked.connect(self._terminate_selected)
        self.configure_button.clicked.connect(lambda: self.task_manager.output.emit("Open task configuration from menu"))

        self.task_manager.tasks_loaded.connect(self._populate)
        self.task_manager.output.connect(self._append_output)
        self.task_manager.state_changed.connect(self._update_state)
        self.task_manager.task_statuses.connect(self._refresh_running)

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
        running = state.startswith("running:")
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    def _run_selected(self) -> None:
        item = self.task_list.currentItem()
        if not item:
            return
        self.task_manager.run_task(item.text())

    def _restart_selected(self) -> None:
        item = self.task_list.currentItem()
        if not item:
            return
        self.task_manager.restart_task(item.text())

    def _terminate_selected(self) -> None:
        item = self.task_list.currentItem()
        if not item:
            return
        self.task_manager.terminate_task(item.text())

    def _refresh_running(self, statuses: dict) -> None:
        self.running_tasks.clear()
        for label, state in statuses.items():
            text = f"{label} — {state}"
            self.running_tasks.addItem(QListWidgetItem(text))

    def _show_empty_state(self, show_empty: bool) -> None:
        target = self.empty_label if show_empty else self.task_list
        self.list_container.setCurrentWidget(target)

    def set_configure_handler(self, handler: Callable[[], None]) -> None:
        try:
            self.configure_button.clicked.disconnect()
        except Exception:
            pass
        self.configure_button.clicked.connect(handler)

