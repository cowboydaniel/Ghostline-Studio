"""Vertical activity bar similar to VS Code/Windsurf."""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QStyle, QToolButton, QVBoxLayout, QWidget


class ActivityBar(QWidget):
    """Thin vertical bar with icon-only buttons for primary tools."""

    toolActivated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActivityBar")
        self.setFixedWidth(52)

        self._buttons: Dict[str, QToolButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(4)

        top_container = QWidget(self)
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)

        bottom_container = QWidget(self)
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)

        style = self.style()
        icons: list[tuple[str, QStyle.StandardPixmap, str, bool]] = [
            ("explorer", QStyle.SP_DirIcon, "Explorer", True),
            ("search", QStyle.SP_FileDialogContentsView, "Search", True),
            ("scm", QStyle.SP_BrowserReload, "Source Control", True),
            ("run", QStyle.SP_MediaPlay, "Run / Debug", True),
            ("map3d", QStyle.SP_DirLinkIcon, "3D Architecture Map", True),
            ("terminal", QStyle.SP_ComputerIcon, "Terminal", True),
            ("ai", QStyle.SP_FileDialogInfoView, "Ghostline AI", True),
        ]

        for tool_id, icon_id, tooltip, enabled in icons:
            button = self._create_button(style, icon_id, tooltip, tool_id, enabled)
            top_layout.addWidget(button)

        layout.addWidget(top_container)
        layout.addStretch(1)

        settings_button = self._create_button(style, QStyle.SP_FileDialogDetailedView, "Settings", "settings", True)
        bottom_layout.addWidget(settings_button)
        layout.addWidget(bottom_container)

    def _create_button(
        self,
        style: QStyle,
        icon_id: QStyle.StandardPixmap,
        tooltip: str,
        tool_id: str,
        enabled: bool,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(style.standardIcon(icon_id))
        button.setToolTip(tooltip)
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        button.setAutoRaise(True)
        button.setEnabled(enabled)
        button.clicked.connect(lambda: self.toolActivated.emit(tool_id))

        self._group.addButton(button)
        self._buttons[tool_id] = button
        return button

    def setActiveTool(self, tool_id: Optional[str]) -> None:
        for key, button in self._buttons.items():
            button.setChecked(key == tool_id)

