"""Minimal CRDT engine placeholder for collaborative editing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class RemoteCursor:
    user: str
    position: int
    color: str = "#00aaff"


class CRDTEngine:
    def __init__(self) -> None:
        self.buffer: list[str] = []
        self.remote_cursors: list[RemoteCursor] = []

    def apply_local_change(self, text: str) -> list[Tuple[int, str]]:
        self.buffer = list(text)
        return []

    def apply_remote_patch(self, patch: str) -> str:
        self.buffer = list(patch)
        return "".join(self.buffer)

    def set_remote_cursor(self, cursor: RemoteCursor) -> None:
        self.remote_cursors.append(cursor)

    def participants(self) -> List[str]:
        return [cursor.user for cursor in self.remote_cursors]
