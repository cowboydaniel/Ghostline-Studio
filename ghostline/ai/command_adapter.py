"""Adapter that maps AI responses into executable command descriptors."""
from __future__ import annotations

import json
from typing import Any, Iterable

from ghostline.core.events import CommandDescriptor, CommandRegistry
from ghostline.ui.command_palette import CommandPalette


class AICommandAdapter:
    """Translate AI JSON outputs into approved command executions."""

    def __init__(self, registry: CommandRegistry, palette: CommandPalette) -> None:
        self.registry = registry
        self.palette = palette

    def handle_response(self, response_text: str | dict | list[dict[str, Any]]) -> None:
        """Attempt to parse AI output and stage commands for approval."""

        payload: Iterable[dict[str, Any]] | None = None
        if isinstance(response_text, list):
            payload = response_text
        elif isinstance(response_text, dict):
            payload = response_text.get("commands") or response_text.get("plan")
        elif isinstance(response_text, str):
            try:
                decoded = json.loads(response_text)
                payload = decoded.get("commands") if isinstance(decoded, dict) else decoded
            except Exception:  # noqa: BLE001
                payload = None

        if not payload:
            return

        planned: list[CommandDescriptor] = []
        for entry in payload:
            cmd_id = entry.get("command") or entry.get("id")
            if not cmd_id:
                continue
            arguments = entry.get("args", {}) or {}
            descriptor = self.registry.get(cmd_id)
            if descriptor:
                bound = descriptor.with_arguments(**arguments)
                bound.side_effects.update(entry.get("side_effects", []) or [])
                planned.append(bound)
        if planned:
            self.palette.set_command_plan(planned)
