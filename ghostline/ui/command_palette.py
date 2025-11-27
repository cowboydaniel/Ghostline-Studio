"""Simple command palette dialog."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from ghostline.core.events import Command, CommandRegistry


class CommandPalette(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setWindowModality(Qt.ApplicationModal)
        self.registry: CommandRegistry | None = None

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Type a command...")
        self.input.textChanged.connect(self._refresh_list)
        self.input.returnPressed.connect(self._execute_selected)

        self.list_widget = QListWidget(self)
        self.list_widget.itemActivated.connect(self._execute_item)

        layout = QVBoxLayout(self)
        layout.addWidget(self.input)
        layout.addWidget(self.list_widget)

    def set_registry(self, registry: CommandRegistry) -> None:
        self.registry = registry

    def open_palette(self) -> None:
        self._refresh_list()
        self.input.clear()
        self.show()
        self.input.setFocus()

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        commands = self.registry.list_commands(self.input.text()) if self.registry else []
        for command in commands:
            item = QListWidgetItem(f"{command.text} ({command.category})")
            item.setData(Qt.UserRole, command)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _execute_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item:
            self._execute_item(item)

    def _execute_item(self, item: QListWidgetItem) -> None:
        command: Command | None = item.data(Qt.UserRole)
        if command:
            command.callback()
        self.close()
