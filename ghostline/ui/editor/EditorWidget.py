from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import ghostline.resources.resources_rc  # type: ignore  # noqa: F401
from ghostline.core.events import CommandRegistry
from ghostline.editor.code_editor import CodeEditor


class EditorWidget(QWidget):
    """Code editor with Windsurf-style header: filename breadcrumb + icon buttons."""

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

        # Main editor
        self.editor = CodeEditor(
            path,
            parent=self,
            config=config,
            theme=theme,
            lsp_manager=lsp_manager,
            ai_client=ai_client,
        )

        # Header: breadcrumbs left, icon buttons right
        header = QFrame(self)
        header.setObjectName("EditorHeader")
        header.setFrameShape(QFrame.NoFrame)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_layout.setSpacing(6)

        # Keep "toolbar" name for compatibility
        self.toolbar = header

        # Breadcrumbs
        self.breadcrumbs = QFrame(header)
        self.breadcrumbs.setObjectName("Breadcrumbs")
        crumbs_layout = QHBoxLayout(self.breadcrumbs)
        crumbs_layout.setContentsMargins(0, 0, 0, 0)
        crumbs_layout.setSpacing(4)
        header_layout.addWidget(self.breadcrumbs)

        # Spacer
        header_layout.addStretch(1)

        icon_size = QSize(16, 16)

        # Run button
        self.run_button = QToolButton(header)
        self.run_button.setObjectName("EditorRunButton")
        self.run_button.setIcon(QIcon(":/icons/run.svg"))
        self.run_button.setIconSize(icon_size)
        self.run_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.run_button.setAutoRaise(True)
        self.run_button.setCursor(Qt.PointingHandCursor)
        self.run_button.setToolTip("Run")
        self.run_button.clicked.connect(self._trigger_run)
        header_layout.addWidget(self.run_button)

        # Debug button
        self.debug_button = QToolButton(header)
        self.debug_button.setObjectName("EditorDebugButton")
        self.debug_button.setIcon(QIcon(":/icons/debug.svg"))
        self.debug_button.setIconSize(icon_size)
        self.debug_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.debug_button.setAutoRaise(True)
        self.debug_button.setCursor(Qt.PointingHandCursor)
        self.debug_button.setToolTip("Debug")
        header_layout.addWidget(self.debug_button)

        # Configure button
        self.configure_button = QToolButton(header)
        self.configure_button.setObjectName("EditorConfigureButton")
        self.configure_button.setIcon(QIcon(":/icons/configure.svg"))
        self.configure_button.setIconSize(icon_size)
        self.configure_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.configure_button.setAutoRaise(True)
        self.configure_button.setCursor(Qt.PointingHandCursor)
        self.configure_button.setToolTip("Configure")
        header_layout.addWidget(self.configure_button)

        # Layout: header above editor
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self.editor, 1)

        self._rebuild_breadcrumbs()
        self._update_toolbar_visibility()

    # ------------------------------------------------------------------
    # Breadcrumbs: show "start.py  >  ..."
    # ------------------------------------------------------------------
    def _rebuild_breadcrumbs(self) -> None:
        layout = self.breadcrumbs.layout()
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        path = self._file_path()
        if not path:
            return

        filename = path.name

        leaf = QLabel(filename, self.breadcrumbs)
        leaf.setObjectName("BreadcrumbLeaf")
        layout.addWidget(leaf)

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
        self.run_button.setEnabled(runnable)
        self.debug_button.setEnabled(runnable)
        self.configure_button.setEnabled(runnable)

    # Qt overrides ------------------------------------------------------
    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self.toolbar.setMaximumWidth(self.width())
        self.toolbar.setMinimumWidth(self.width())
