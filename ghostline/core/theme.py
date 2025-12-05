"""Theme helpers for Ghostline Studio."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from ghostline.core.resources import icons_dir


class ThemeManager:
    """Applies and exposes the Ghostline Studio theme."""

    def __init__(self) -> None:
        self._palette = self._build_dark_palette()
        self._syntax_colors = self._default_syntax_colors()

    def apply(self, app: QApplication) -> None:
        """Apply the dark theme, fonts, and stylesheet to the application."""
        app.setStyle("Fusion")
        self._palette = self._build_dark_palette()
        app.setPalette(self._palette)
        app.setFont(self._preferred_font())
        stylesheet = self._load_stylesheet()
        if stylesheet:
            app.setStyleSheet(stylesheet)
        self._syntax_colors = self._default_syntax_colors()

    def color(self, role: QPalette.ColorRole) -> QColor:
        return self._palette.color(role)

    def syntax_color(self, key: str) -> QColor:
        return self._syntax_colors.get(key, QColor(200, 200, 200))

    def _build_dark_palette(self) -> QPalette:
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#15161a"))
        palette.setColor(QPalette.WindowText, QColor("#e0e0e0"))
        # Editor base and current line background
        palette.setColor(QPalette.Base, QColor("#1a1b1f"))
        palette.setColor(QPalette.AlternateBase, QColor("#22232a"))
        palette.setColor(QPalette.ToolTipBase, QColor("#1e1f24"))
        palette.setColor(QPalette.ToolTipText, QColor("#e0e0e0"))
        palette.setColor(QPalette.Text, QColor("#e0e0e0"))
        palette.setColor(QPalette.Button, QColor("#1e1f24"))
        palette.setColor(QPalette.ButtonText, QColor("#e0e0e0"))
        palette.setColor(QPalette.BrightText, QColor("#ffffff"))
        palette.setColor(QPalette.Highlight, QColor("#4f8cff"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.Link, QColor("#4f8cff"))
        palette.setColor(QPalette.LinkVisited, QColor("#a68cff"))
        # Used for gutter divider etc
        palette.setColor(QPalette.Dark, QColor("#111219"))
        return palette

    def _preferred_font(self) -> QFont:
        font_db = QFontDatabase()
        size = 11
        preferred = "JetBrains Mono"
        if preferred in font_db.families():
            return QFont(preferred, size)
        font = font_db.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(size)
        return font

    def _load_stylesheet(self) -> str:
        style_path = Path(__file__).resolve().parent.parent / "resources" / "styles" / "ghostline_dark.qss"
        try:
            stylesheet = style_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

        icons_base = icons_dir().resolve().as_uri()

        def _replace_icon(match: re.Match[str]) -> str:
            icon_name = match.group(1)
            return f'url("{icons_base}/{icon_name}")'

        return re.sub(r"url\(:/icons/([^\)]+)\)", _replace_icon, stylesheet)

    def _default_syntax_colors(self) -> dict[str, QColor]:
        return {
            "keyword": QColor(189, 147, 249),
            "string": QColor(152, 195, 121),
            "comment": QColor(120, 120, 120),
            "number": QColor(209, 154, 102),
            "builtin": QColor(97, 175, 239),
            "definition": self._palette.color(QPalette.Highlight),
        }
