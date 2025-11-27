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


class CommandPalette(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setWindowModality(Qt.ApplicationModal)
        self.commands: dict[str, Callable[[], None]] = {}

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Type a command...")
        self.input.textChanged.connect(self._filter_commands)
        self.input.returnPressed.connect(self._execute_selected)

        self.list_widget = QListWidget(self)
        self.list_widget.itemActivated.connect(self._execute_item)

        layout = QVBoxLayout(self)
        layout.addWidget(self.input)
        layout.addWidget(self.list_widget)

    def set_commands(self, commands: dict[str, Callable[[], None]]) -> None:
        self.commands = commands
        self._refresh_list()

    def open_palette(self) -> None:
        self._refresh_list()
        self.input.clear()
        self.show()
        self.input.setFocus()

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        for name in sorted(self.commands.keys()):
            self.list_widget.addItem(QListWidgetItem(name))
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _filter_commands(self, text: str) -> None:
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            item.setHidden(text.lower() not in item.text().lower())

    def _execute_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item:
            self._execute_item(item)

    def _execute_item(self, item: QListWidgetItem) -> None:
        command = self.commands.get(item.text())
        if command:
            command()
        self.close()
