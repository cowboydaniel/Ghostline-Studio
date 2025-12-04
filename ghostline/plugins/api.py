"""Public plugin API surface for Ghostline Studio."""
from __future__ import annotations

from typing import Callable, Protocol

from PySide6.QtWidgets import QDockWidget

from ghostline.core.events import CommandDescriptor


class MenuCallback(Protocol):
    def __call__(self) -> None:  # pragma: no cover - UI callback
        ...


class PluginContext:
    """Expose extension points to third-party plugins."""

    def __init__(self, app, command_registry, menu_bar, dock_host, event_bus) -> None:
        self.app = app
        self._command_registry = command_registry
        self._menu_bar = menu_bar
        self._dock_host = dock_host
        self._event_bus = event_bus

    def register_command(self, identifier: str, label: str, callback: Callable) -> None:
        command = CommandDescriptor(identifier, label, "Plugins", callback)
        self._command_registry.register_command(command)

    def register_menu(self, path: str, callback: MenuCallback) -> None:
        parts = path.split("/")
        menu = self._menu_bar
        for part in parts[:-1]:
            existing = next((m for m in menu.actions() if m.menu() and m.text() == part), None)
            menu = existing.menu() if existing else menu.addMenu(part)
        menu.addAction(parts[-1], callback)

    def register_dock(self, identifier: str, widget_factory: Callable[[], QDockWidget]) -> None:
        widget = widget_factory()
        widget.setObjectName(identifier)
        self._dock_host.register_dock(identifier, widget)

    def listen(self, event_name: str, callback: Callable) -> None:
        self._event_bus.setdefault(event_name, []).append(callback)

