"""Resource helpers for Ghostline Studio."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon


_ICONS_DIR = Path(__file__).resolve().parent.parent / "resources" / "icons"


def icons_dir() -> Path:
    """Return the absolute path to the bundled icons directory."""

    return _ICONS_DIR


@lru_cache(maxsize=None)
def _existing_icon_path(name: str) -> Path | None:
    path = _ICONS_DIR / name
    if path.exists():
        return path
    return None


def icon_path(name: str, *, fallback: str | None = None) -> Path | None:
    """Resolve an icon path, optionally falling back to another name."""

    for candidate in (name, fallback):
        if not candidate:
            continue
        path = _existing_icon_path(candidate)
        if path:
            return path
    return None


def load_icon(name: str, *, fallback: str | None = None) -> QIcon:
    """Load an icon from disk, returning an empty icon if missing."""

    path = icon_path(name, fallback=fallback)
    return QIcon(str(path)) if path else QIcon()
