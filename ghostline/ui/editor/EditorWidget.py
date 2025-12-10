from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ghostline.core.events import CommandRegistry
from ghostline.editor.code_editor import CodeEditor


class EditorWidget(QWidget):
    """Wraps a CodeEditor with a Windsurf-style header + Run/Debug/Configure."""

    RUNNABLE_SUFFIXES = {".py", ".pyw"}

    def __init__(
        self,
        path: Path | None = None,
        parent: QWidget | None = None,
        *,
        config=None,
        theme=None,
        lsp_manager=None,
        ai_client=None,
        command_registry: CommandRegistry | None = None,
    ) -> None:
        super().__init__(parent)
        self.command_registry = command_registry

        # The actual editor
        self.editor = CodeEditor(
            path,
            parent=self,
            config=config,
            theme=theme,
            lsp_manager=lsp_manager,
            ai_client=ai_client,
        )

        # Header row: breadcrumbs on the left, actions on the right
        header = QFrame(self)
        header.setObjectName("EditorHeader")
        header.setFrameShape(QFrame.NoFrame)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_layout.setSpacing(6)

        # Keep compatibility with older code that expects .toolbar
        self.toolbar = header

        # Breadcrumbs container
        self.breadcrumbs = QFrame(header)
        self.breadcrumbs.setObjectName("Breadcrumbs")
        crumbs_layout = QHBoxLayout(self.breadcrumbs)
        crumbs_layout.setContentsMargins(0, 0, 0, 0)
        crumbs_layout.setSpacing(4)
        header_layout.addWidget(self.breadcrumbs)

        # Space in the middle so buttons hug the right edge
        header_layout.addStretch(1)

        # Right-side buttons (Run / Debug / Configure)
        self.run_button = QToolButton(header)
        self.run_button.setText("Run")
        self.run_button.setAutoRaise(True)
        self.run_button.setCursor(Qt.PointingHandCursor)
        self.run_button.clicked.connect(self._trigger_run)
        header_layout.addWidget(self.run_button)

        self.debug_button = QToolButton(header)
        self.debug_button.setText("Debug")
        self.debug_button.setAutoRaise(True)
        self.debug_button.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(self.debug_button)

        self.configure_button = QToolButton(header)
        self.configure_button.setText("Configure")
        self.configure_button.setAutoRaise(True)
        self.configure_button.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(self.configure_button)

        # Editor below the header
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self.editor, 1)

        self._rebuild_breadcrumbs()
        self._update_toolbar_visibility()

    # ------------------------------------------------------------------
    # Breadcrumbs
    # ------------------------------------------------------------------
    def _rebuild_breadcrumbs(self) -> None:
        """Make breadcrumbs look like 'start.py  >  ...' (filename + ellipsis)."""
        layout = self.breadcrumbs.layout()
        # Clear any existing labels
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        path = self._file_path()
        if not path:
            return

        filename = path.name

        # File name (highlighted)
        leaf = QLabel(filename, self.breadcrumbs)
        leaf.setObjectName("BreadcrumbLeaf")
        layout.addWidget(leaf)

        # If there is any parent path, show " > ..."
        if path.parent != path:
            sep = QLabel(">", self.breadcrumbs)
            layout.addWidget(sep)

            dots = QLabel("...", self.breadcrumbs)
            dots.setObjectName("BreadcrumbEllipsis")
            layout.addWidget(dots)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _trigger_run(self) -> None:
        if not self.command_registry:
            return

        descriptor = self.command_registry.get("python.runFile")
        path = self._file_path()
        if not descriptor or not path:
            return

        self.command_registry.execute(descriptor.with_arguments(file_path=str(path)))

    def _file_path(self) -> Path | None:
        return self.editor.path if isinstance(self.editor.path, Path) else None

    def _is_runnable(self) -> bool:
        path = self._file_path()
        return bool(path and path.suffix.lower() in self.RUNNABLE_SUFFIXES)

    def _update_toolbar_visibility(self) -> None:
        runnable = self._is_runnable()
        # Header is always visible; just toggle button enabled state
        self.run_button.setEnabled(runnable)
        self.debug_button.setEnabled(runnable)
        self.configure_button.setEnabled(runnable)

    # Qt overrides ------------------------------------------------------
    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        # Keep header width in sync with the editor
        self.toolbar.setMaximumWidth(self.width())
        self.toolbar.setMinimumWidth(self.width())
