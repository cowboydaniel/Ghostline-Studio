"""Helpers for editor gutter interactions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QRect


@dataclass
class GutterMarker:
    line: int
    color: str = "#c85050"
    tooltip: str | None = None


def marker_rect(area_width: int, top: int, height: int) -> QRect:
    radius = 5
    return QRect(area_width - 2 * radius - 2, top, radius * 2, height)


def handle_gutter_click(y: float, block_height: int, handler: Callable[[int], None]) -> None:
    line = int(y // block_height)
    handler(line)
