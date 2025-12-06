from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QVBoxLayout, QWidget

from ghostline.core.events import CommandRegistry
from ghostline.editor.code_editor import CodeEditor


class EditorWidget(QWidget):
    """Wraps a CodeEditor with a small toolbar for run/debug/config actions."""

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
        self.editor = CodeEditor(
            path,
            config=config,
            theme=theme,
            lsp_manager=lsp_manager,
            ai_client=ai_client,
        )

        self.toolbar = QFrame(self)
        self.toolbar.setObjectName("EditorToolbar")
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.setSpacing(8)

        self.run_button = QToolButton(self.toolbar)
        self.run_button.setText("Run")
        self.run_button.clicked.connect(self._trigger_run)
        toolbar_layout.addWidget(self.run_button)

        self.debug_button = QToolButton(self.toolbar)
        self.debug_button.setText("Debug")
        toolbar_layout.addWidget(self.debug_button)

        self.configure_button = QToolButton(self.toolbar)
        self.configure_button.setText("Configure")
        toolbar_layout.addWidget(self.configure_button)

        toolbar_layout.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.editor, 1)

        self._update_toolbar_visibility()

    # ------------------------------------------------------------------
    def _trigger_run(self) -> None:
        descriptor = self.command_registry.get("python.runFile") if self.command_registry else None
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
        self.toolbar.setVisible(self._is_runnable())
        self.run_button.setEnabled(self._is_runnable())
        self.debug_button.setEnabled(self._is_runnable())
        self.configure_button.setEnabled(self._is_runnable())

    # Qt overrides ------------------------------------------------------
    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self.toolbar.setMaximumWidth(self.width())
        self.toolbar.setMinimumWidth(self.width())

