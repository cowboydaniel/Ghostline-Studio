"""Breakpoint tracking shared across editors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass
class Breakpoint:
    """Represents a single breakpoint on a file and line."""

    line: int
    kind: str = "line"  # line | conditional | logpoint
    expression: str | None = None
    enabled: bool = True


class BreakpointStore:
    _instance: "BreakpointStore | None" = None

    def __init__(self) -> None:
        self._breakpoints: Dict[str, Dict[int, Breakpoint]] = {}

    @classmethod
    def instance(cls) -> "BreakpointStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def toggle_line(self, path: str, line: int) -> None:
        """Toggle a basic breakpoint at the given path and line."""

        entries = self._breakpoints.setdefault(path, {})
        if line in entries:
            del entries[line]
        else:
            entries[line] = Breakpoint(line=line)

    def set_conditional(self, path: str, line: int, expression: str) -> None:
        """Create or update a conditional breakpoint."""

        entries = self._breakpoints.setdefault(path, {})
        entries[line] = Breakpoint(line=line, kind="conditional", expression=expression, enabled=True)

    def set_logpoint(self, path: str, line: int, message: str) -> None:
        """Create or update a logpoint breakpoint."""

        entries = self._breakpoints.setdefault(path, {})
        entries[line] = Breakpoint(line=line, kind="logpoint", expression=message, enabled=True)

    def remove(self, path: str, line: int) -> None:
        if path in self._breakpoints:
            self._breakpoints[path].pop(line, None)

    def list_for(self, path: str, include_disabled: bool = False) -> List[int]:
        entries = self._breakpoints.get(path, {})
        if include_disabled:
            return sorted(entries.keys())
        return sorted(bp.line for bp in entries.values() if bp.enabled)

    def get_for_path(self, path: str) -> list[Breakpoint]:
        return list(self._breakpoints.get(path, {}).values())

    def has(self, path: str, line: int, *, include_disabled: bool = False) -> bool:
        bp = self._breakpoints.get(path, {}).get(line)
        if not bp:
            return False
        return bp.enabled or include_disabled

    def get(self, path: str, line: int) -> Breakpoint | None:
        return self._breakpoints.get(path, {}).get(line)

    def enable_all(self, path: str) -> None:
        for bp in self._breakpoints.get(path, {}).values():
            bp.enabled = True

    def disable_all(self, path: str) -> None:
        for bp in self._breakpoints.get(path, {}).values():
            bp.enabled = False

    def clear(self, path: str | None = None) -> None:
        if path:
            self._breakpoints.pop(path, None)
        else:
            self._breakpoints.clear()

    def serialize_for_debugger(self, path: str) -> list[dict]:
        """Return breakpoints in a debugpy-friendly dict structure."""

        payload: list[dict] = []
        for bp in self._breakpoints.get(path, {}).values():
            if not bp.enabled:
                continue
            entry: dict[str, object] = {"line": bp.line + 1}
            if bp.kind == "conditional" and bp.expression:
                entry["condition"] = bp.expression
            if bp.kind == "logpoint" and bp.expression:
                entry["logMessage"] = bp.expression
            payload.append(entry)
        return payload

    def iter_paths(self) -> Iterable[str]:
        return self._breakpoints.keys()
