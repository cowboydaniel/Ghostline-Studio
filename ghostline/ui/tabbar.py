"""Custom tab bar styling for editor tabs."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QStyle, QStyleOptionTab, QStylePainter, QTabBar


class EditorTabBar(QTabBar):
    """Tab bar with Windsurf-inspired appearance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._preview_tabs = {}  # Track which tabs are in preview mode

    def set_tab_preview(self, index: int, is_preview: bool) -> None:
        if is_preview:
            self._preview_tabs[index] = True
        else:
            self._preview_tabs.pop(index, None)
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
            is_preview = self._preview_tabs.get(i, False)

            if is_active:
                option.palette.setColor(QPalette.ColorRole.Button, QColor("#1e1f23"))
                option.palette.setColor(QPalette.ColorRole.Window, QColor("#1e1f23"))
            else:
                option.palette.setColor(QPalette.ColorRole.Button, QColor("#191a1d"))
                option.palette.setColor(QPalette.ColorRole.Window, QColor("#191a1d"))

            # For preview tabs, we'll paint the text ourselves in italic
            saved_text = ""
            if is_preview:
                saved_text = option.text
                option.text = ""  # Clear text so Qt doesn't paint it

            painter.drawControl(QStyle.CE_TabBarTab, option)

            # Paint italic text for preview tabs
            if is_preview and saved_text:
                rect = self.tabRect(i)
                font = QFont(self.font())
                font.setItalic(True)
                painter.setFont(font)
                painter.setPen(option.palette.color(option.palette.WindowText))

                # Leave space for the close button on the right (typically 20-24px)
                text_rect = QRect(
                    rect.left() + 8,
                    rect.top(),
                    rect.width() - 32,  # Leave room for icon and close button
                    rect.height()
                )
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, saved_text)

            # Draw thin underline for active tab
            if is_active:
                rect = self.tabRect(i)
                underline_y = rect.bottom() - 1
                painter.fillRect(
                    QRect(rect.left() + 8, underline_y, rect.width() - 16, 2),
                    QColor("#3b82f6")
                )
