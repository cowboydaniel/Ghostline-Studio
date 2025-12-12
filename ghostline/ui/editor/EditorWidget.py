from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize
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
from ghostline.core.resources import load_icon
from ghostline.core.theme import ThemeManager
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
        self.theme = theme or ThemeManager()

        # Main editor
        self.editor = CodeEditor(
            path,
            parent=self,
            config=config,
            theme=self.theme,
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
        self.run_button.setIcon(load_icon("run.svg"))
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
        self.debug_button.setIcon(load_icon("debug.svg"))
        self.debug_button.setIconSize(icon_size)
        self.debug_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.debug_button.setAutoRaise(True)
        self.debug_button.setCursor(Qt.PointingHandCursor)
        self.debug_button.setToolTip("Debug")
        header_layout.addWidget(self.debug_button)

        # Configure button
        self.configure_button = QToolButton(header)
        self.configure_button.setObjectName("EditorConfigureButton")
        self.configure_button.setIcon(load_icon("configure.svg"))
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
        print("\n=== Run button clicked! ===")  # Debug log
        
        # Check command registry
        if not self.command_registry:
            print("ERROR: No command registry available!")
            return
        print("✓ Command registry available")

        # Get the command descriptor
        if not hasattr(self.command_registry, 'get'):
            print(f"ERROR: command_registry is not a CommandRegistry instance. Type: {type(self.command_registry)}")
            return

        descriptor = self.command_registry.get("python.runFile")
        print(f"Command descriptor: {descriptor}")
        
        # Get the file path
        path = self._file_path()
        print(f"File path: {path}")
        
        # Validate descriptor and path
        if not descriptor:
            print("ERROR: 'python.runFile' command not found in registry!")
            if hasattr(self.command_registry, '_commands'):
                print(f"Available commands: {list(self.command_registry._commands.keys())}")
            return
            
        if not path:
            print("ERROR: No file path available to run!")
            return
            
        print(f"✓ Ready to execute command for file: {path}")
        
        try:
            # Prepare the command with arguments
            command = descriptor.with_arguments(file_path=str(path))
            print(f"Executing command: {command}")
            
            # Execute the command
            result = self.command_registry.execute(command)
            print(f"Command execution result: {result}")
            
        except Exception as e:
            print(f"ERROR during command execution: {e}")
            import traceback
            traceback.print_exc()

    def _file_path(self) -> Path | None:
        return self.editor.path if isinstance(self.editor.path, Path) else None

    def _is_runnable(self) -> bool:
        path = self._file_path()
        return bool(path and path.suffix.lower() in self.RUNNABLE_SUFFIXES)

    def _update_toolbar_visibility(self) -> None:
        path = self._file_path()
        runnable = self._is_runnable()

        print("\n=== Updating Toolbar Visibility ===")
        print(f"Current file: {path}")
        print(f"Is runnable: {runnable}")
        print(f"Run button enabled: {runnable}")
        print(f"Run button visible: {self.run_button.isVisible()}")
        print(f"Run button tooltip: {self.run_button.toolTip()}")

        # Set both visibility and enabled state
        self.run_button.setVisible(runnable)
        self.run_button.setEnabled(runnable)
        self.debug_button.setVisible(runnable)
        self.debug_button.setEnabled(runnable)
        self.configure_button.setVisible(runnable)
        self.configure_button.setEnabled(runnable)

        print("Toolbar visibility update complete\n")

    # Qt overrides ------------------------------------------------------
    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        # Use size policy instead of fixed constraints for better performance
        # The toolbar naturally fills the width via the layout
