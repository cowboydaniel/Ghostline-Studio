"""Breakpoint tracking shared across editors."""
from __future__ import annotations

from typing import Dict, List, Set


class BreakpointStore:
    _instance: "BreakpointStore | None" = None

    def __init__(self) -> None:
        self._breakpoints: Dict[str, Set[int]] = {}

    @classmethod
    def instance(cls) -> "BreakpointStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def toggle(self, path: str, line: int) -> None:
        lines = self._breakpoints.setdefault(path, set())
        if line in lines:
            lines.remove(line)
        else:
            lines.add(line)

    def list_for(self, path: str) -> List[int]:
        return sorted(self._breakpoints.get(path, set()))

    def has(self, path: str, line: int) -> bool:
        return line in self._breakpoints.get(path, set())
