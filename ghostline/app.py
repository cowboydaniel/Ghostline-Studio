"""Application bootstrap for Ghostline Studio."""
from __future__ import annotations

import argparse
import logging
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog

from ghostline.core.config import ConfigManager
from ghostline.core.logging import configure_logging, get_logger
from ghostline.core.theme import ThemeManager
from ghostline.workspace.workspace_manager import WorkspaceManager
from ghostline.ui.main_window import MainWindow
from ghostline.ui.splash_screen import GhostlineSplash
from ghostline.ui.dialogs.setup_wizard import SetupWizardDialog


class GhostlineApplication:
    """Owns application-wide objects and startup sequence."""

    def __init__(self) -> None:
        self.args = self._parse_args()
        configure_logging()
        self.logger = get_logger(__name__)
        self.qt_app = QApplication(sys.argv)
        self._install_exception_hook()
        self.theme = ThemeManager()
        self.theme.apply(self.qt_app)
        self.config = ConfigManager()
        self.workspace_manager = WorkspaceManager()
        self.main_window = MainWindow(self.config, self.theme, self.workspace_manager)
        self.splash: GhostlineSplash | None = None

    def _parse_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Ghostline Studio")
        parser.add_argument("path", nargs="?", help="File or folder to open")
        return parser.parse_args()

    def _show_splash(self) -> None:
        self.splash = GhostlineSplash()
        self.splash.splashFinished.connect(self._on_splash_finished)
        self.splash.show()
        self.qt_app.processEvents()

    def _on_splash_finished(self) -> None:
        initial_first_run = not bool(self.config.get("first_run_completed", False))

        if initial_first_run:
            wizard = SetupWizardDialog(self.config, self.main_window)
            result = wizard.exec()
            if result != QDialog.Accepted and not self.config.get("first_run_completed", False):
                self.logger.info("Setup wizard was cancelled; exiting before showing main window.")
                self.qt_app.quit()
                return

        self.main_window.apply_initial_window_state(force_maximize=initial_first_run)

        if self.config.get("first_run_completed", False):
            if self.args.path:
                self._open_initial_path(self.args.path)
            else:
                last_workspace = self.workspace_manager.last_recent_workspace()
                if last_workspace:
                    self.main_window.open_folder(str(last_workspace))

        self.main_window.show()

    def run(self) -> int:
        try:
            self._show_splash()
            return self.qt_app.exec()
        except Exception as e:
            self.logger.exception("Unhandled exception in main loop")
            return 1
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up resources in the correct order."""
        try:
            # Close main window first to trigger any pending operations
            if hasattr(self, 'main_window') and self.main_window:
                self.main_window.close()
                self.main_window.deleteLater()
                self.main_window = None

            if hasattr(self, 'splash') and self.splash:
                self.splash.close()
                self.splash.deleteLater()
                self.splash = None

            # Clean up workspace manager
            if hasattr(self, 'workspace_manager') and self.workspace_manager:
                self.workspace_manager.save_recents()
                self.workspace_manager = None

            # Clean up QApplication
            if hasattr(self, 'qt_app') and self.qt_app:
                self.qt_app.processEvents()
                self.qt_app.quit()
                self.qt_app = None

        except Exception as e:
            self.logger.exception("Error during cleanup")

    def _open_initial_path(self, path: str) -> None:
        target = Path(path)
        if target.is_file():
            self.main_window.open_file(str(target))
        elif target.is_dir():
            self.main_window.open_folder(str(target))

    # Error handling
    def _install_exception_hook(self) -> None:
        sys.excepthook = self._handle_exception  # type: ignore[assignment]

    def _handle_exception(self, exc_type, exc_value, exc_tb) -> None:  # type: ignore[override]
        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.error("Uncaught exception:\n%s", formatted)
        dialog = QMessageBox()
        dialog.setWindowTitle("Unexpected Error")
        dialog.setIcon(QMessageBox.Critical)
        dialog.setText("An unexpected error occurred. Details have been written to the log file.")
        dialog.setDetailedText(formatted)
        dialog.exec()
