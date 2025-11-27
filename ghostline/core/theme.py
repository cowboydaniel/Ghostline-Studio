"""Theme helpers for Ghostline Studio."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ghostline.core.config import ConfigManager


class ThemeManager:
    """Applies UI themes based on configuration."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config

    def apply_theme(self, app: QApplication) -> None:
        theme_name = self.config.get("theme", "Ghostline Dark")
        if theme_name == "Ghostline Dark":
            palette = self._dark_palette()
            app.setPalette(palette)
            app.setStyle("Fusion")

    def _dark_palette(self) -> QPalette:
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(33, 37, 43))
        palette.setColor(QPalette.WindowText, QColor(230, 230, 230))
        palette.setColor(QPalette.Base, QColor(25, 29, 34))
        palette.setColor(QPalette.AlternateBase, QColor(33, 37, 43))
        palette.setColor(QPalette.ToolTipBase, QColor(45, 49, 54))
        palette.setColor(QPalette.ToolTipText, QColor(230, 230, 230))
        palette.setColor(QPalette.Text, QColor(230, 230, 230))
        palette.setColor(QPalette.Button, QColor(45, 49, 54))
        palette.setColor(QPalette.ButtonText, QColor(230, 230, 230))
        palette.setColor(QPalette.BrightText, QColor(255, 69, 58))
        palette.setColor(QPalette.Highlight, QColor(52, 152, 219))
        palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        return palette
