"""Vertical activity bar similar to VS Code/Windsurf."""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QButtonGroup, QStyle, QToolButton, QVBoxLayout, QWidget

from ghostline.core.resources import load_icon


class ActivityBar(QWidget):
    """Thin vertical bar with icon-only buttons for primary tools."""

    explorerRequested = Signal()
    gitRequested = Signal()
    debugRequested = Signal()
    testsRequested = Signal()
    tasksRequested = Signal()
    architectureRequested = Signal()
    settingsRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActivityBar")
        # Reduced from 48 to save horizontal space on small screens
        self.setFixedWidth(42)

        self._buttons: Dict[str, QToolButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(6)

        top_container = QWidget(self)
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        bottom_container = QWidget(self)
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(6)

        style = self.style()
        folder_icon = load_icon("folders/folder.svg")
        explorer_icon = folder_icon if not folder_icon.isNull() else style.standardIcon(QStyle.SP_DirIcon)
        buttons = [
            ("explorer", explorer_icon, "Explorer", self.explorerRequested),
            ("git", style.standardIcon(QStyle.SP_BrowserReload), "Source Control", self.gitRequested),
            ("debug", style.standardIcon(QStyle.SP_MediaPlay), "Run / Debug", self.debugRequested),
            ("tests", style.standardIcon(QStyle.SP_DriveHDIcon), "Tests", self.testsRequested),
            ("tasks", style.standardIcon(QStyle.SP_FileDialogDetailedView), "Tasks", self.tasksRequested),
            ("architecture", style.standardIcon(QStyle.SP_DirLinkIcon), "3D Architecture", self.architectureRequested),
        ]

        for tool_id, icon, tooltip, signal in buttons:
            button = self._create_button(style, icon, tooltip, tool_id, signal)
            top_layout.addWidget(button)

        layout.addWidget(top_container)
        layout.addStretch(1)

        settings_button = self._create_button(
            style, style.standardIcon(QStyle.SP_FileDialogInfoView), "Settings", "settings", self.settingsRequested
        )
        bottom_layout.addWidget(settings_button)
        layout.addWidget(bottom_container)

    def _create_button(
        self,
        style: QStyle,
        icon: QIcon,
        tooltip: str,
        tool_id: str,
        emitter: Signal,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(icon if not icon.isNull() else style.standardIcon(QStyle.SP_FileIcon))
        button.setToolTip(tooltip)
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        button.setAutoRaise(True)
        button.clicked.connect(emitter)

        self._group.addButton(button)
        self._buttons[tool_id] = button
        return button

    def setActiveTool(self, tool_id: Optional[str]) -> None:
        for key, button in self._buttons.items():
            button.setChecked(key == tool_id)

