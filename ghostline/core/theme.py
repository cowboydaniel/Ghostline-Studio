"""Theme helpers for Ghostline Studio."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ghostline.core.config import ConfigManager


class ThemeManager:
    """Applies UI themes based on configuration."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        self._palette: QPalette | None = None
        self._syntax_colors: dict[str, QColor] = {}

    def apply_theme(self, app: QApplication) -> None:
        theme_name = self.config.get("theme", "Ghostline Dark")
        if theme_name == "Ghostline Dark":
            palette = self._dark_palette()
            app.setPalette(palette)
            app.setStyle("Fusion")
            self._palette = palette
            self._syntax_colors = self._default_syntax_colors()

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

    def color(self, role: QPalette.ColorRole) -> QColor:
        if self._palette:
            return self._palette.color(role)
        return self._dark_palette().color(role)

    def syntax_color(self, key: str) -> QColor:
        if not self._syntax_colors:
            self._syntax_colors = self._default_syntax_colors()
        return self._syntax_colors.get(key, QColor(200, 200, 200))

    def _default_syntax_colors(self) -> dict[str, QColor]:
        base = self._palette or self._dark_palette()
        return {
            "keyword": QColor(189, 147, 249),
            "string": QColor(152, 195, 121),
            "comment": QColor(120, 120, 120),
            "number": QColor(209, 154, 102),
            "builtin": QColor(97, 175, 239),
            "definition": base.color(QPalette.Highlight),
        }
