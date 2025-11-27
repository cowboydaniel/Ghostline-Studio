"""Simple command palette dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from ghostline.core.events import Command, CommandRegistry
from ghostline.ai.navigation_assistant import NavigationAssistant, PredictiveContext


class CommandPalette(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setWindowModality(Qt.ApplicationModal)
        self.registry: CommandRegistry | None = None
        self.navigation_assistant: NavigationAssistant | None = None
        self.predictive_context: PredictiveContext | None = None
        self.autoflow_mode = "passive"

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

    def set_navigation_assistant(self, assistant: NavigationAssistant) -> None:
        self.navigation_assistant = assistant

    def set_predictive_context(self, context: PredictiveContext) -> None:
        self.predictive_context = context

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
        if self.navigation_assistant and self.input.text().strip():
            query = self.input.text().strip()
            nav_command = Command(
                text=f"Semantic navigate: {query}",
                callback=lambda q=query: self._run_navigation(q),
                category="navigation",
            )
            nav_item = QListWidgetItem(nav_command.text)
            nav_item.setData(Qt.UserRole, nav_command)
            self.list_widget.addItem(nav_item)
        if self.navigation_assistant:
            context = self.predictive_context or PredictiveContext(cursor_symbol=self.input.text().strip())
            suggestions = (
                self.navigation_assistant.autoflow(context)
                if self.autoflow_mode == "active"
                else self.navigation_assistant.predict_actions(context)
            )
            for predicted in suggestions:
                cmd = Command(
                    text=predicted.label,
                    callback=lambda action=predicted.action: self._execute_prediction(action),
                    category="autoflow" if self.autoflow_mode == "active" else "prediction",
                )
                item = QListWidgetItem(f"{cmd.text} ({cmd.category})")
                item.setData(Qt.UserRole, cmd)
                self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def set_autoflow_mode(self, mode: str) -> None:
        """Switch between passive suggestions and active autoflow."""

        if mode in {"passive", "active"}:
            self.autoflow_mode = mode

    def _execute_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item:
            self._execute_item(item)

    def _execute_item(self, item: QListWidgetItem) -> None:
        command: Command | None = item.data(Qt.UserRole)
        if command:
            command.callback()
        self.close()

    def _run_navigation(self, query: str) -> None:
        if not self.navigation_assistant:
            return
        results = (
            self.navigation_assistant.go_to_function_generating(query)
            + self.navigation_assistant.find_module_handling(query)
            + self.navigation_assistant.jump_to_error_construction()
        )
        self.list_widget.clear()
        for result in results:
            self.list_widget.addItem(f"{result.label} @ {result.node.file}")

    def _execute_prediction(self, action: str) -> None:
        self.list_widget.clear()
        self.list_widget.addItem(f"Predicted action executed: {action}")
