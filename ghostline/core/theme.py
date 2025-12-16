"""Theme helpers for Ghostline Studio."""
from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from ghostline.core.resources import icons_dir


class ThemeManager:
    """Applies and exposes the Ghostline Studio theme."""

    DEFAULT_THEME = "ghost_dark"
    THEMES: dict[str, dict[str, dict[str, str]]] = {
        "ghost_dark": {
            "palette": {
                "window": "#101113",
                "window_text": "#D4D4D4",
                "base": "#101113",
                "alternate_base": "#15171a",
                "tool_tip_base": "#101113",
                "tool_tip_text": "#D4D4D4",
                "text": "#D4D4D4",
                "button": "#101113",
                "button_text": "#D4D4D4",
                "bright_text": "#ffffff",
                "highlight": "#264F78",
                "highlighted_text": "#ffffff",
                "link": "#569CD6",
                "link_visited": "#C586C0",
                "dark": "#0d0e10",
            },
            "syntax": {
                "keyword": "#569CD6",
                "string": "#CE9178",
                "comment": "#6A9955",
                "number": "#B5CEA8",
                "builtin": "#4EC9B0",
                "definition": "#9CDCFE",
                "function": "#DCDCAA",
                "class": "#4EC9B0",
                "import": "#C586C0",
                "literal": "#B5CEA8",
                "dunder": "#4EC9B0",
                "typehint": "#4EC9B0",
                "decorator": "#C586C0",
                "operator": "#D4D4D4",
                "variable": "#9CDCFE",
                "constant": "#4FC1FF",
            },
        },
        "ghost_night": {
            "palette": {
                "window": "#0b0d0c",
                "window_text": "#d5e8d6",
                "base": "#050605",
                "alternate_base": "#0e120f",
                "tool_tip_base": "#0b0d0c",
                "tool_tip_text": "#d5e8d6",
                "text": "#d5e8d6",
                "button": "#0b0d0c",
                "button_text": "#d5e8d6",
                "bright_text": "#f4fff5",
                "highlight": "#0fa36b",
                "highlighted_text": "#f5fff8",
                "link": "#28c58a",
                "link_visited": "#4fbf9d",
                "dark": "#070808",
            },
            # Easter egg trigger: hidden ghost night palette
            "syntax": {
                "keyword": "#39c46a",
                "string": "#9edfae",
                "comment": "#5f8763",
                "number": "#7ddbb3",
                "builtin": "#2fbf9f",
                "definition": "#8fe8c1",
                "function": "#cde8a2",
                "class": "#48d597",
                "import": "#90e0d1",
                "literal": "#b0f0b4",
                "dunder": "#2fbf9f",
                "typehint": "#2fbf9f",
                "decorator": "#6fffd4",
                "operator": "#dcead7",
                "variable": "#a4f4c4",
                "constant": "#54f0b7",
            },
        },
    }

    def __init__(self, theme_name: str | None = None) -> None:
        self.theme_name = theme_name or self.DEFAULT_THEME
        self.previous_theme_name: str | None = None
        self._palette = self._build_palette()
        self._syntax_colors = self._load_syntax_colors()

    def apply(self, app: QApplication) -> None:
        """Apply the dark theme, fonts, and stylesheet to the application."""
        app.setStyle("Fusion")
        self._palette = self._build_palette()
        app.setPalette(self._palette)
        app.setFont(self._preferred_font())
        stylesheet = self._load_stylesheet()
        if stylesheet:
            app.setStyleSheet(stylesheet)
        self._syntax_colors = self._load_syntax_colors()

    def set_theme(self, theme_name: str) -> None:
        """Switch to a new theme when it exists."""
        if theme_name not in self.THEMES:
            return
        self.theme_name = theme_name
        self._palette = self._build_palette()
        self._syntax_colors = self._load_syntax_colors()

    def remember_current_theme(self) -> None:
        """Record the active theme so it can be restored later."""
        self.previous_theme_name = self.theme_name

    def color(self, role: QPalette.ColorRole) -> QColor:
        return self._palette.color(role)

    def syntax_color(self, key: str) -> QColor:
        return self._syntax_colors.get(key, QColor(200, 200, 200))

    def editor_color(self, key: str) -> QColor:
        """Get editor-specific colors (line numbers, gutter, etc)."""
        editor_colors = {
            "line_number": QColor("#858585"),  # Inactive line numbers
            "active_line_number": QColor("#C6C6C6"),  # Active line number
            "gutter_background": QColor("#1E1E1E"),
            "gutter_divider": QColor("#2D2D30"),
        }
        return editor_colors.get(key, QColor(200, 200, 200))

    def _theme_definition(self) -> dict[str, dict[str, str]]:
        return self.THEMES.get(self.theme_name, self.THEMES[self.DEFAULT_THEME])

    def _build_palette(self) -> QPalette:
        palette = QPalette()
        palette_def = self._theme_definition().get("palette", {})
        palette.setColor(QPalette.Window, QColor(palette_def.get("window", "#101113")))
        palette.setColor(QPalette.WindowText, QColor(palette_def.get("window_text", "#D4D4D4")))
        palette.setColor(QPalette.Base, QColor(palette_def.get("base", "#101113")))
        # Current line highlight - using solid color, alpha applied in code_editor.py
        palette.setColor(QPalette.AlternateBase, QColor(palette_def.get("alternate_base", "#15171a")))
        palette.setColor(QPalette.ToolTipBase, QColor(palette_def.get("tool_tip_base", "#101113")))
        palette.setColor(QPalette.ToolTipText, QColor(palette_def.get("tool_tip_text", "#D4D4D4")))
        palette.setColor(QPalette.Text, QColor(palette_def.get("text", "#D4D4D4")))
        palette.setColor(QPalette.Button, QColor(palette_def.get("button", "#101113")))
        palette.setColor(QPalette.ButtonText, QColor(palette_def.get("button_text", "#D4D4D4")))
        palette.setColor(QPalette.BrightText, QColor(palette_def.get("bright_text", "#ffffff")))
        palette.setColor(QPalette.Highlight, QColor(palette_def.get("highlight", "#264F78")))
        palette.setColor(QPalette.HighlightedText, QColor(palette_def.get("highlighted_text", "#ffffff")))
        palette.setColor(QPalette.Link, QColor(palette_def.get("link", "#569CD6")))
        palette.setColor(QPalette.LinkVisited, QColor(palette_def.get("link_visited", "#C586C0")))
        # Used for gutter divider etc
        palette.setColor(QPalette.Dark, QColor(palette_def.get("dark", "#0d0e10")))
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

        icons_base = icons_dir().resolve()

        def _replace_icon(match: re.Match[str]) -> str:
            icon_name = match.group(1)
            icon_path = (icons_base / icon_name).resolve()
            # Qt stylesheets expect a local filesystem path, not a file:// URI.
            url = str(icon_path)
            return f'url("{url}")'

        return re.sub(r"url\(:/icons/([^\)]+)\)", _replace_icon, stylesheet)

    def _load_syntax_colors(self) -> dict[str, QColor]:
        theme_path = Path(__file__).resolve().parent.parent / "settings" / "default_theme.json"
        if self.theme_name == self.DEFAULT_THEME and theme_path.exists():
            try:
                data = json.loads(theme_path.read_text(encoding="utf-8"))
                syntax = data.get("syntax", {}) if isinstance(data, dict) else {}
                return {key: QColor(value) for key, value in syntax.items()}
            except (OSError, json.JSONDecodeError):
                pass
        return self._default_syntax_colors()

    def _default_syntax_colors(self) -> dict[str, QColor]:
        syntax = self._theme_definition().get("syntax", {})
        return {key: QColor(value) for key, value in syntax.items()}
