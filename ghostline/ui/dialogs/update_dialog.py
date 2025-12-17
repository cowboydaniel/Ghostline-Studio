"""Update checker dialog for Ghostline Studio."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QWidget,
    QTextEdit,
)

from ghostline.core.update_checker import UpdateChecker


class UpdateDialog(QDialog):
    """Dialog for checking and displaying update information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.update_checker = UpdateChecker()
        self.setWindowTitle("Check for Updates")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        self._setup_ui()
        self._check_updates()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Status label
        self.status_label = QLabel("Checking for updates...")
        layout.addWidget(self.status_label)

        layout.addSpacing(10)

        # Version info
        self.version_label = QLabel()
        layout.addWidget(self.version_label)

        layout.addSpacing(10)

        # Release notes
        self.release_notes = QTextEdit()
        self.release_notes.setReadOnly(True)
        self.release_notes.setVisible(False)
        layout.addWidget(self.release_notes)

        layout.addSpacing(10)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.open_btn = QPushButton("Open Release Page")
        self.open_btn.clicked.connect(self._on_open_release)
        self.open_btn.setVisible(False)
        button_layout.addWidget(self.open_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _check_updates(self) -> None:
        """Check for updates from GitHub."""
        result = self.update_checker.check_for_updates()

        if result is None:
            self.status_label.setText(
                "Unable to check for updates. Please check your internet connection."
            )
            return

        current = result["current_version"]
        latest = result["latest_version"]
        self.release_url = result.get("release_url", "")
        release_name = result.get("release_name", f"Version {latest}")
        release_body = result.get("release_body", "")

        self.version_label.setText(f"Current: {current} | Latest: {latest}")

        if result["update_available"]:
            self.status_label.setText(
                f"A new version is available! ({release_name})"
            )
            self.open_btn.setVisible(True)

            if release_body:
                self.release_notes.setVisible(True)
                self.release_notes.setText(release_body)
        else:
            self.status_label.setText("You are running the latest version.")

    def _on_open_release(self) -> None:
        """Open the release page in browser."""
        if hasattr(self, "release_url") and self.release_url:
            QDesktopServices.openUrl(QUrl(self.release_url))
            self.close()
