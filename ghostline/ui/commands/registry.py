"""Reusable command definitions for UI actions and the command palette."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from PySide6.QtGui import QAction

from ghostline.core.events import CommandDescriptor, CommandRegistry


@dataclass
class CommandActionDefinition:
    """Describe a command-driven QAction.

    The definition captures a command id, label, category, shortcut metadata, and
    the callable that should be executed when the action fires. Checkable commands
    receive the QAction's checked state when invoked.
    """

    id: str
    text: str
    category: str
    handler: Callable[..., None]
    shortcut: str | None = None
    checkable: bool = False
    checked: bool | None = None
    enabled: Callable[[], bool] | None = None

    def create_action(self, parent) -> QAction:
        action = QAction(self.text, parent)
        if self.shortcut:
            action.setShortcut(self.shortcut)
        if self.checkable:
            action.setCheckable(True)
            if self.checked is not None:
                action.setChecked(self.checked)
            action.triggered.connect(lambda checked: self.handler(checked))
        else:
            action.triggered.connect(lambda _checked=False: self.handler())
        return action

    def to_descriptor(self, trigger: Callable[[], None]) -> CommandDescriptor:
        return CommandDescriptor(
            id=self.id,
            description=self.text,
            category=self.category,
            callback=trigger,
        )


class CommandActionRegistry:
    """Build QActions from definitions and expose them to the command palette."""

    def __init__(self, parent, command_registry: CommandRegistry | None = None) -> None:
        self.parent = parent
        self.command_registry = command_registry
        self._definitions: dict[str, CommandActionDefinition] = {}
        self._actions: dict[str, QAction] = {}

    def register(self, definition: CommandActionDefinition) -> None:
        self._definitions[definition.id] = definition

    def bulk_register(self, definitions: Iterable[CommandActionDefinition]) -> None:
        for definition in definitions:
            self.register(definition)

    def build(self) -> dict[str, QAction]:
        for definition in self._definitions.values():
            action = definition.create_action(self.parent)
            self._actions[definition.id] = action

            if self.command_registry:
                descriptor = definition.to_descriptor(lambda def_id=definition.id: self.trigger(def_id))
                self.command_registry.register_command(descriptor)
        return self._actions

    def trigger(self, command_id: str) -> None:
        action = self._actions.get(command_id)
        if action:
            action.trigger()

    def action(self, command_id: str) -> QAction | None:
        return self._actions.get(command_id)

    def refresh_enabled(self) -> None:
        for definition in self._definitions.values():
            if definition.enabled:
                action = self._actions.get(definition.id)
                if action:
                    action.setEnabled(bool(definition.enabled()))
