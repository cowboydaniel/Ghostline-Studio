from __future__ import annotations

from pathlib import Path

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
    """Wraps a CodeEditor with a header bar and run/debug/config actions."""

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
        self.header = QFrame(self)
        self.header.setObjectName("EditorHeader")
        self.header.setFrameShape(QFrame.NoFrame)

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_layout.setSpacing(6)

        # Breadcrumbs container
        self.breadcrumbs = QFrame(self.header)
        self.breadcrumbs.setObjectName("Breadcrumbs")
        crumbs_layout = QHBoxLayout(self.breadcrumbs)
        crumbs_layout.setContentsMargins(0, 0, 0, 0)
        crumbs_layout.setSpacing(4)
        header_layout.addWidget(self.breadcrumbs)

        # Spacer so buttons hug the right edge
        header_layout.addStretch(1)

        # Action buttons aligned to the right
        self.run_button = QToolButton(self.header)
        self.run_button.setText("Run")
        self.run_button.setAutoRaise(True)
        self.run_button.clicked.connect(self._trigger_run)
        header_layout.addWidget(self.run_button)

        self.debug_button = QToolButton(self.header)
        self.debug_button.setText("Debug")
        self.debug_button.setAutoRaise(True)
        header_layout.addWidget(self.debug_button)

        self.configure_button = QToolButton(self.header)
        self.configure_button.setText("Configure")
        self.configure_button.setAutoRaise(True)
        header_layout.addWidget(self.configure_button)

        # Layout: header above editor
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.editor, 1)

        self._rebuild_breadcrumbs()
        self._update_toolbar_visibility()

    # ------------------------------------------------------------------
    # Breadcrumbs
    # ------------------------------------------------------------------
    def _rebuild_breadcrumbs(self) -> None:
        layout = self.breadcrumbs.layout()
        # Clear existing widgets
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        path = self._file_path()
        if not path:
            return

        parts = list(path.parts)

        # Heuristic: show path from "ghostline" onward, to match the project root
        start_index = 0
        for i, part in enumerate(parts):
            if part == "ghostline":
                start_index = i
                break
        parts = parts[start_index:]

        for i, part in enumerate(parts):
            label = QLabel(part, self.breadcrumbs)
            if i == len(parts) - 1:
                # Final segment (file name) gets a slightly different style
                label.setObjectName("BreadcrumbLeaf")
            layout.addWidget(label)

            if i != len(parts) - 1:
                sep = QLabel("›", self.breadcrumbs)
                layout.addWidget(sep)

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
        # Header always visible; buttons enabled/disabled based on file type
        self.header.setVisible(True)
        self.run_button.setEnabled(runnable)
        self.debug_button.setEnabled(runnable)
        self.configure_button.setEnabled(runnable)

    # Qt overrides ------------------------------------------------------
    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self.header.setMaximumWidth(self.width())
        self.header.setMinimumWidth(self.width())
