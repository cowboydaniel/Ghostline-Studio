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

    def __init__(self) -> None:
        self._palette = self._build_dark_palette()
        self._syntax_colors = self._load_syntax_colors()

    def apply(self, app: QApplication) -> None:
        """Apply the dark theme, fonts, and stylesheet to the application."""
        app.setStyle("Fusion")
        self._palette = self._build_dark_palette()
        app.setPalette(self._palette)
        app.setFont(self._preferred_font())
        stylesheet = self._load_stylesheet()
        if stylesheet:
            app.setStyleSheet(stylesheet)
        self._syntax_colors = self._load_syntax_colors()

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

    def _build_dark_palette(self) -> QPalette:
        palette = QPalette()
        # VS Code Dark+ theme colors
        palette.setColor(QPalette.Window, QColor("#101113"))
        palette.setColor(QPalette.WindowText, QColor("#D4D4D4"))
        # Editor base and current line background
        palette.setColor(QPalette.Base, QColor("#101113"))
        # Current line highlight - using solid color, alpha applied in code_editor.py
        palette.setColor(QPalette.AlternateBase, QColor("#15171a"))  # Will have alpha applied
        palette.setColor(QPalette.ToolTipBase, QColor("#101113"))
        palette.setColor(QPalette.ToolTipText, QColor("#D4D4D4"))
        palette.setColor(QPalette.Text, QColor("#D4D4D4"))
        palette.setColor(QPalette.Button, QColor("#101113"))
        palette.setColor(QPalette.ButtonText, QColor("#D4D4D4"))
        palette.setColor(QPalette.BrightText, QColor("#ffffff"))
        palette.setColor(QPalette.Highlight, QColor("#264F78"))  # Selection background
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.Link, QColor("#569CD6"))
        palette.setColor(QPalette.LinkVisited, QColor("#C586C0"))
        # Used for gutter divider etc
        palette.setColor(QPalette.Dark, QColor("#0d0e10"))
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
        if theme_path.exists():
            try:
                data = json.loads(theme_path.read_text(encoding="utf-8"))
                syntax = data.get("syntax", {}) if isinstance(data, dict) else {}
                return {key: QColor(value) for key, value in syntax.items()}
            except (OSError, json.JSONDecodeError):
                pass
        return self._default_syntax_colors()

    def _default_syntax_colors(self) -> dict[str, QColor]:
        # VS Code Dark+ theme syntax colors
        return {
            "keyword": QColor("#569CD6"),  # Keywords (if, return, import, etc)
            "string": QColor("#CE9178"),   # Strings (single, double, f-strings, docstrings)
            "comment": QColor("#6A9955"),  # Comments
            "number": QColor("#B5CEA8"),   # Numbers
            "builtin": QColor("#4EC9B0"),  # Builtins / types (list, dict, type names)
            "definition": QColor("#9CDCFE"), # Variables / identifiers
            "function": QColor("#DCDCAA"),   # Function names
            "class": QColor("#4EC9B0"),      # Class names
            "import": QColor("#C586C0"),     # Import statements
            "literal": QColor("#B5CEA8"),    # Literals (number literals, custom literals)
            "dunder": QColor("#4EC9B0"),     # Dunder methods
            "typehint": QColor("#4EC9B0"),   # Type hints
            "decorator": QColor("#C586C0"),  # Decorators (@something)
            "operator": QColor("#D4D4D4"),   # Operators (default foreground)
            "variable": QColor("#9CDCFE"),   # Variables
            "constant": QColor("#4FC1FF"),   # Constants / enum members
        }
