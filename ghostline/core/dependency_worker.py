"""Worker thread for running dependency installation without blocking the UI."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from ghostline.core.dependency_installer import run_dependency_setup


class DependencyWorker(QThread):
    """Worker thread that runs dependency installation in the background."""

    progress = Signal(str)  # Emits progress messages
    finished = Signal(bool)  # Emits True on success, False on failure

    def run(self) -> None:
        """Execute dependency installation and report progress."""
        try:
            def report_progress(message: str) -> None:
                self.progress.emit(message)

            success = run_dependency_setup(progress_callback=report_progress)
            self.finished.emit(success)
        except Exception as exc:
            self.progress.emit(f"Unexpected error: {exc}")
            self.finished.emit(False)
