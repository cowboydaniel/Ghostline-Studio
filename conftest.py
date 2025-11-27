"""Top-level pytest configuration.

This file ensures that PySide6 (or a lightweight stub) is available before any
test modules are imported, including those that live outside the ``tests``
directory. The concrete QApplication fixture remains in ``tests/conftest.py``.
"""

from tests._qt_compat import ensure_qt_available


# Guarantee Qt imports succeed (using the real bindings when possible).
ensure_qt_available()
