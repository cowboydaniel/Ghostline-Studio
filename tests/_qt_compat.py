"""Qt compatibility helpers for tests.

The helpers here prefer the real PySide6 bindings when they can be imported
successfully (including their native dependencies). If the bindings are
installed but fail to load due to missing system libraries, a minimal stub is
installed so modules can still be imported and exercised.
"""
from __future__ import annotations

import importlib
import os
import sys
import types
from typing import Any


def _install_pyside6_stub() -> None:
    """Install a lightweight PySide6 stub if the real library is missing."""

    pyside6 = types.ModuleType("PySide6")

    class _Signal:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._subscribers: list[Any] = []

        def connect(self, callback: Any) -> None:
            self._subscribers.append(callback)

        def emit(self, *args: Any, **kwargs: Any) -> None:
            for callback in list(self._subscribers):
                callback(*args, **kwargs)

    class _QObject:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__()

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Signal = _Signal
    qtcore.QObject = _QObject
    qtcore.Qt = types.SimpleNamespace()

    class _Widget:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.children: list[Any] = []
            super().__init__()

    class _Layout(_Widget):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.items: list[Any] = []

        def addWidget(self, widget: Any) -> None:  # noqa: N802 - Qt style API
            self.items.append(widget)

        def addLayout(self, layout: Any) -> None:  # noqa: N802 - Qt style API
            self.items.append(layout)

    class _PushButton(_Widget):
        def __init__(self, label: str = "", parent: Any | None = None) -> None:
            super().__init__(parent)
            self.label = label
            self.clicked = _Signal()

    class _TextEdit(_Widget):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._read_only = False
            self._contents: list[str] = []

        def setReadOnly(self, value: bool) -> None:
            self._read_only = value

        def append(self, text: str) -> None:
            self._contents.append(text)

        @property
        def contents(self) -> list[str]:
            return list(self._contents)

    class _ListWidget(_Widget):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.items: list[Any] = []

        def addItem(self, item: Any) -> None:
            self.items.append(item)

    class _TableWidget(_Widget):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.headers: list[str] = []
            self.cells: dict[tuple[int, int], Any] = {}

        def setRowCount(self, count: int) -> None:
            self.row_count = count

        def setColumnCount(self, count: int) -> None:
            self.col_count = count

        def setHorizontalHeaderLabels(self, labels: list[str]) -> None:
            self.headers = labels

        def setItem(self, row: int, column: int, item: Any) -> None:
            self.cells[(row, column)] = item

    class _TableWidgetItem:
        def __init__(self, text: str) -> None:
            self.text = text

    class _StatusBar(_Widget):
        def showMessage(self, message: str, timeout: int | None = None) -> None:
            self.message = message
            self.timeout = timeout

        def addWidget(self, widget: Any) -> None:  # noqa: N802 - Qt style API
            self.children.append(widget)

        def addPermanentWidget(self, widget: Any) -> None:  # noqa: N802 - Qt style API
            self.addWidget(widget)

    class _Label(_Widget):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._text = ""

        def setText(self, text: str) -> None:
            self._text = text

        def text(self) -> str:
            return self._text

    class _DockWidget(_Widget):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._widget: Any | None = None

        def setWidget(self, widget: Any) -> None:
            self._widget = widget

    class _MainWindow(_Widget):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.docks: list[Any] = []

        def addDockWidget(self, *args: Any, **kwargs: Any) -> None:
            self.docks.append((args, kwargs))

    class _Application:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        @staticmethod
        def instance() -> "_Application | None":  # type: ignore[name-match]
            return None

        def exec(self) -> int:  # noqa: A003 - API compatibility
            return 0

    class _MessageBox:
        @staticmethod
        def information(*args: Any, **kwargs: Any) -> None:
            return None

    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QWidget = _Widget
    qtwidgets.QVBoxLayout = type("QVBoxLayout", (_Layout,), {})
    qtwidgets.QHBoxLayout = type("QHBoxLayout", (_Layout,), {})
    qtwidgets.QPushButton = _PushButton
    qtwidgets.QTextEdit = _TextEdit
    qtwidgets.QListWidget = _ListWidget
    qtwidgets.QListWidgetItem = type("QListWidgetItem", (_Widget,), {})
    qtwidgets.QTableWidget = _TableWidget
    qtwidgets.QTableWidgetItem = _TableWidgetItem
    qtwidgets.QStatusBar = _StatusBar
    qtwidgets.QDockWidget = _DockWidget
    qtwidgets.QMainWindow = _MainWindow
    qtwidgets.QTabWidget = type("QTabWidget", (_Widget,), {})
    qtwidgets.QPlainTextEdit = type("QPlainTextEdit", (_Widget,), {})
    qtwidgets.QToolTip = type("QToolTip", (_Widget,), {})
    qtwidgets.QLabel = _Label
    qtwidgets.QLineEdit = type("QLineEdit", (_Widget,), {})
    qtwidgets.QComboBox = type("QComboBox", (_Widget,), {})
    qtwidgets.QStackedLayout = type("QStackedLayout", (_Layout,), {})
    qtwidgets.QApplication = _Application
    qtwidgets.QMessageBox = _MessageBox
    qtwidgets.QDialog = type("QDialog", (_Widget,), {})
    qtwidgets.QDialogButtonBox = type("QDialogButtonBox", (_Widget,), {})
    qtwidgets.QCheckBox = type("QCheckBox", (_Widget,), {})
    qtwidgets.QProgressBar = type("QProgressBar", (_Widget,), {})
    qtwidgets.QSplitter = type("QSplitter", (_Widget,), {})
    qtwidgets.QGraphicsView = type("QGraphicsView", (_Widget,), {})
    qtwidgets.QGraphicsScene = type("QGraphicsScene", (_Widget,), {})

    pyside6.QtCore = qtcore
    pyside6.QtWidgets = qtwidgets

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["PySide6.QtWidgets"] = qtwidgets


def ensure_qt_available() -> None:
    """Guarantee that PySide6 imports succeed (with a stub if necessary)."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    if "PySide6" in sys.modules:
        return

    try:
        importlib.import_module("PySide6")
        return
    except Exception:
        _install_pyside6_stub()


def build_qt_app():  # noqa: ANN201 - fixture helper
    """Create a QApplication instance when possible."""

    try:  # pragma: no cover - only executed when Qt is available
        from PySide6.QtWidgets import QApplication

        try:
            return QApplication.instance() or QApplication([])
        except Exception:
            return QApplication([])
    except Exception:  # pragma: no cover - stubbed Qt
        return None
