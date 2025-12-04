"""Lightweight command registry used by the command palette."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, List


@dataclass
class CommandParameter:
    """Describe an input parameter for a command."""

    name: str
    description: str = ""
    default: Any | None = None


@dataclass
class CommandDescriptor:
    """Metadata for commands exposed to the palette and AI layer."""

    id: str
    description: str
    category: str
    callback: Callable[..., None]
    parameters: list[CommandParameter] = field(default_factory=list)
    side_effects: set[str] = field(default_factory=set)
    undo: Callable[[], None] | None = None
    redo: Callable[[], None] | None = None
    arguments: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.description

    def with_arguments(self, **kwargs: Any) -> "CommandDescriptor":
        """Return a copy of the descriptor with bound arguments."""

        return replace(self, arguments={**self.arguments, **kwargs})


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: list[CommandDescriptor] = []
        self._undo_stack: list[CommandDescriptor] = []
        self._redo_stack: list[CommandDescriptor] = []

    def register_command(self, command: CommandDescriptor) -> None:
        self._commands = [cmd for cmd in self._commands if cmd.id != command.id]
        self._commands.append(command)

    def get(self, command_id: str) -> CommandDescriptor | None:
        for cmd in self._commands:
            if cmd.id == command_id:
                return cmd
        return None

    def list_commands(self, filter_text: str | None = None) -> List[CommandDescriptor]:
        if not filter_text:
            return list(self._commands)
        lowered = filter_text.lower()
        return [cmd for cmd in self._commands if lowered in cmd.description.lower() or lowered in cmd.id]

    # Execution helpers -------------------------------------------------
    def execute(self, descriptor: CommandDescriptor) -> None:
        descriptor.callback(**descriptor.arguments)
        if descriptor.undo:
            self._undo_stack.append(descriptor)
            self._redo_stack.clear()

    def undo_last(self) -> None:
        if not self._undo_stack:
            return
        last = self._undo_stack.pop()
        if last.undo:
            last.undo()
            if last.redo:
                self._redo_stack.append(last)

    def redo_last(self) -> None:
        if not self._redo_stack:
            return
        last = self._redo_stack.pop()
        if last.redo:
            last.redo()
            self._undo_stack.append(last)

