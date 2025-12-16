"""Simple command palette dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ghostline.core.events import CommandDescriptor, CommandRegistry
from ghostline.core.theme import ThemeManager
from ghostline.ai.navigation_assistant import NavigationAssistant, PredictiveContext
from ghostline.ui.dialogs.credits_dialog import CreditsDialog


EASTER_EGG_QUERY = "about:ghosts"


class CommandPalette(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setWindowModality(Qt.ApplicationModal)
        self.registry: CommandRegistry | None = None
        self.navigation_assistant: NavigationAssistant | None = None
        self.predictive_context: PredictiveContext | None = None
        self.autoflow_mode = "passive"
        self.file_provider = None
        self.open_file_callback = None
        self.pending_commands: list[CommandDescriptor] = []
        self._credits_dialog: CreditsDialog | None = None
        self.theme: ThemeManager | None = None

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Type a command...")
        self.input.textChanged.connect(self._refresh_list)
        self.input.returnPressed.connect(self._execute_selected)

        self.list_widget = QListWidget(self)
        self.list_widget.itemActivated.connect(self._execute_item)

        self.plan_list = QListWidget(self)
        self.plan_group = QGroupBox("Command Plan", self)
        self.plan_group.setVisible(False)
        plan_layout = QVBoxLayout(self.plan_group)
        plan_layout.addWidget(self.plan_list)

        plan_buttons = QHBoxLayout()
        self.approve_btn = QPushButton("Approve All", self.plan_group)
        self.step_btn = QPushButton("Run Next", self.plan_group)
        self.cancel_btn = QPushButton("Cancel", self.plan_group)
        self.approve_btn.clicked.connect(self._approve_plan)
        self.step_btn.clicked.connect(self._step_plan)
        self.cancel_btn.clicked.connect(self._cancel_plan)
        for btn in (self.approve_btn, self.step_btn, self.cancel_btn):
            plan_buttons.addWidget(btn)
        plan_layout.addLayout(plan_buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(self.input)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.plan_group)

    def set_registry(self, registry: CommandRegistry) -> None:
        self.registry = registry

    def set_navigation_assistant(self, assistant: NavigationAssistant) -> None:
        self.navigation_assistant = assistant

    def set_predictive_context(self, context: PredictiveContext) -> None:
        self.predictive_context = context

    def set_file_provider(self, provider) -> None:
        self.file_provider = provider

    def set_open_file_handler(self, handler) -> None:
        self.open_file_callback = handler

    def set_theme_manager(self, theme: ThemeManager) -> None:
        self.theme = theme

    def open_palette(self) -> None:
        self._refresh_list()
        self.input.clear()
        self.show()
        self.input.setFocus()

    def open_with_query(self, query: str) -> None:
        self.input.setText(query)
        self._refresh_list()
        self.show()
        self.input.setFocus()

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        commands = self.registry.list_commands(self.input.text()) if self.registry else []
        for command in commands:
            label = f"{command.label} ({command.category})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, command)
            self.list_widget.addItem(item)
        if self.file_provider and self.input.text().strip():
            for path in self.file_provider(self.input.text().strip()):
                display = f"Open {path.name}"
                cmd = CommandDescriptor(
                    id=f"file:{path}",
                    description=display,
                    category="File",
                    callback=lambda p=path: self._open_file(p),
                )
                item = QListWidgetItem(f"{cmd.label} ({cmd.category})")
                item.setData(Qt.UserRole, cmd)
                self.list_widget.addItem(item)
        if self.navigation_assistant and self.input.text().strip():
            query = self.input.text().strip()
            nav_command = CommandDescriptor(
                id=f"navigate:{query}",
                description=f"Semantic navigate: {query}",
                callback=lambda q=query: self._run_navigation(q),
                category="navigation",
            )
            nav_item = QListWidgetItem(nav_command.label)
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
                cmd = CommandDescriptor(
                    id=f"prediction:{predicted.label}",
                    description=predicted.label,
                    callback=lambda action=predicted.action: self._execute_prediction(action),
                    category="autoflow" if self.autoflow_mode == "active" else "prediction",
                )
                item = QListWidgetItem(f"{cmd.label} ({cmd.category})")
                item.setData(Qt.UserRole, cmd)
                self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def set_autoflow_mode(self, mode: str) -> None:
        """Switch between passive suggestions and active autoflow."""

        if mode in {"passive", "active"}:
            self.autoflow_mode = mode

    def _execute_selected(self) -> None:
        query = self.input.text().strip()
        normalized_query = query.lower()
        # Hidden easter egg: entering "ghost night" toggles the secret theme.
        if self._activate_ghost_night(normalized_query):
            return
        # Hidden easter egg: entering "about:ghosts" opens the credits dialog instead of running a command.
        if self._handle_easter_egg(query):
            return
        item = self.list_widget.currentItem()
        if item:
            self._execute_item(item)

    def _execute_item(self, item: QListWidgetItem) -> None:
        command: CommandDescriptor | None = item.data(Qt.UserRole)
        if command:
            self._apply_command(command)
        self.close()

    def _open_file(self, path):
        if self.open_file_callback:
            self.open_file_callback(str(path))

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

    # Command plan -----------------------------------------------------
    def set_command_plan(self, commands: list[CommandDescriptor]) -> None:
        self.pending_commands = commands
        self.plan_list.clear()
        for descriptor in commands:
            details = ", ".join(sorted(descriptor.side_effects)) if descriptor.side_effects else "No side-effects"
            label = f"{descriptor.label} — {details}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, descriptor)
            self.plan_list.addItem(item)
        self.plan_group.setVisible(bool(commands))

    def _approve_plan(self) -> None:
        if not self.pending_commands:
            return
        if (
            QMessageBox.question(
                self,
                "Apply AI Plan",
                "Run all proposed commands? (Undo is used when available.)",
            )
            != QMessageBox.Yes
        ):
            return
        for descriptor in list(self.pending_commands):
            self._apply_command(descriptor)
        self._cancel_plan()

    def _step_plan(self) -> None:
        if not self.pending_commands:
            return
        descriptor = self.pending_commands.pop(0)
        if QMessageBox.question(self, "Run command", f"Run {descriptor.label}?") != QMessageBox.Yes:
            self.pending_commands.insert(0, descriptor)
            return
        self._apply_command(descriptor)
        self.set_command_plan(self.pending_commands)

    def _cancel_plan(self) -> None:
        self.pending_commands = []
        self.plan_list.clear()
        self.plan_group.setVisible(False)

    def _apply_command(self, descriptor: CommandDescriptor) -> None:
        if self.registry and self.registry.get(descriptor.id):
            self.registry.execute(descriptor)
        else:
            descriptor.callback(**descriptor.arguments)

    # Easter egg -------------------------------------------------------
    def _activate_ghost_night(self, normalized_query: str) -> bool:
        if normalized_query != "ghost night":
            return False

        # Easter egg trigger path for the secret Ghost Night theme.
        if self.theme:
            self.theme.set_theme("ghost_night")
            app = QApplication.instance()
            if app:
                self.theme.apply(app)
        return True

    def _handle_easter_egg(self, query: str) -> bool:
        if query != EASTER_EGG_QUERY:
            return False

        self._show_credits_dialog()
        return True

    def _show_credits_dialog(self) -> None:
        if not self._credits_dialog:
            self._credits_dialog = CreditsDialog(self)
        # Show the dialog without blocking the palette so users can keep searching.
        self._credits_dialog.show()
