"""Custom tab bar styling for editor tabs."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QStyle, QStyleOptionTab, QStylePainter, QTabBar


class EditorTabBar(QTabBar):
    """Tab bar with Windsurf-inspired appearance."""

    PREVIEW_ROLE = Qt.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)

    def set_tab_preview(self, index: int, is_preview: bool) -> None:
        self.setTabData(index, self.PREVIEW_ROLE, is_preview)
        self.update()

    def tabSizeHint(self, index: int):
        # Windsurf tabs are flatter and wider with reduced height.
        size = super().tabSizeHint(index)
        return QSize(size.width() + 36, 28)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionTab()

        for i in range(self.count()):
            self.initStyleOption(option, i)

            # Windsurf removes borders and rounded corners
            option.shape = QTabBar.RoundedNorth
            option.features &= ~QStyleOptionTab.HasFrame

            is_active = (self.currentIndex() == i)
            is_preview = self.tabData(i, self.PREVIEW_ROLE) or False

            if is_active:
                option.palette.setColor(option.palette.Button, QColor("#1e1f23"))
                option.palette.setColor(option.palette.Window, QColor("#1e1f23"))
            else:
                option.palette.setColor(option.palette.Button, QColor("#191a1d"))
                option.palette.setColor(option.palette.Window, QColor("#191a1d"))

            if is_preview:
                font = self.font()
                font.setItalic(True)
                option.font = font

            painter.drawControl(QStyle.CE_TabBarTab, option)

            # Draw thin underline for active tab
            if is_active:
                rect = self.tabRect(i)
                underline_y = rect.bottom() - 1
                painter.fillRect(
                    QRect(rect.left() + 8, underline_y, rect.width() - 16, 2),
                    QColor("#3b82f6")
                )
