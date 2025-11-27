"""Application bootstrap for Ghostline Studio."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ghostline.core.config import ConfigManager
from ghostline.core.logging import configure_logging
from ghostline.core.theme import ThemeManager
from ghostline.workspace.workspace_manager import WorkspaceManager
from ghostline.ui.main_window import MainWindow


class GhostlineApplication:
    """Owns application-wide objects and startup sequence."""

    def __init__(self) -> None:
        self.args = self._parse_args()
        configure_logging()
        self.qt_app = QApplication(sys.argv)
        self.config = ConfigManager()
        self.theme = ThemeManager(self.config)
        self.workspace_manager = WorkspaceManager()
        self.main_window = MainWindow(self.config, self.theme, self.workspace_manager)

    def _parse_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Ghostline Studio")
        parser.add_argument("path", nargs="?", help="File or folder to open")
        return parser.parse_args()

    def run(self) -> int:
        self.theme.apply_theme(self.qt_app)
        if self.args.path:
            self._open_initial_path(self.args.path)
        self.main_window.show()
        return self.qt_app.exec()

    def _open_initial_path(self, path: str) -> None:
        target = Path(path)
        if target.is_file():
            self.main_window.open_file(str(target))
        elif target.is_dir():
            self.main_window.open_folder(str(target))
