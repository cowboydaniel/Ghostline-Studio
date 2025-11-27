"""Pytest configuration and shared fixtures for the test suite."""
from __future__ import annotations

import pytest

from tests._qt_compat import build_qt_app, ensure_qt_available


ensure_qt_available()
_qt_app = build_qt_app()


@pytest.fixture(scope="session")
def qt_app():
    """Provide a shared QApplication instance (or ``None`` when stubbed)."""

    return _qt_app
