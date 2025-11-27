"""Lightweight command registry used by the command palette."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List


@dataclass
class Command:
    id: str
    text: str
    category: str
    callback: Callable[[], None]


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: list[Command] = []

    def register_command(self, command: Command) -> None:
        self._commands = [cmd for cmd in self._commands if cmd.id != command.id]
        self._commands.append(command)

    def list_commands(self, filter_text: str | None = None) -> List[Command]:
        if not filter_text:
            return list(self._commands)
        lowered = filter_text.lower()
        return [cmd for cmd in self._commands if lowered in cmd.text.lower() or lowered in cmd.id]

