"""Qt resource registration for Ghostline assets."""

from __future__ import annotations

from importlib import import_module


def load() -> None:
    """Ensure compiled Qt resources are registered."""

    import_module("ghostline.resources.resources_rc")


# Load resources on import
load()
