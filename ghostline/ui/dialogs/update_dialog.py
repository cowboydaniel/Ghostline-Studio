"""Update checker dialog for Ghostline Studio."""
from __future__ import annotations

import logging

from PySide6.QtCore import QUrl, Qt, QTimer
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
    QProgressBar,
)

from ghostline.core.update_checker import UpdateChecker
from ghostline.core.update_installer import UpdateInstaller
from ghostline.core.urls import RELEASES_URL

logger = logging.getLogger(__name__)


class UpdateDialog(QDialog):
    """Dialog for checking and displaying update information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.update_checker = UpdateChecker()
        self.update_installer = UpdateInstaller()
        self.setWindowTitle("Check for Updates")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        self._setup_ui()
        self._check_updates()
        self._installing = False

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

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        layout.addWidget(self.progress_bar)

        # Status message during install
        self.status_message = QLabel()
        self.status_message.setVisible(False)
        self.status_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_message)

        layout.addSpacing(10)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.install_btn = QPushButton("Install & Restart")
        self.install_btn.clicked.connect(self._on_install_update)
        self.install_btn.setVisible(False)
        button_layout.addWidget(self.install_btn)

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

        current_version = self.update_checker.current_version
        self.version_label.setText(f"Current version: {current_version}")

        if result is None:
            self.status_label.setText(
                "Unable to check for updates automatically.\n\n"
                "Network or firewall may be blocking GitHub API.\n"
                "Click 'View Releases' to check manually."
            )
            # Still show button to check manually
            self.open_btn.setText("View Releases")
            self.open_btn.setVisible(True)
            self.release_url = RELEASES_URL
            return

        current = result["current_version"]
        latest = result["latest_version"]
        self.release_url = result.get("release_url", RELEASES_URL)
        release_name = result.get("release_name", f"Version {latest}")
        release_body = result.get("release_body", "")

        self.version_label.setText(f"Current: {current} | Latest: {latest}")

        if result["update_available"]:
            self.status_label.setText(
                f"A new version is available! ({release_name})"
            )
            self.install_btn.setVisible(True)
            self.open_btn.setText("Open Release Page")
            self.open_btn.setVisible(True)

            if release_body:
                self.release_notes.setVisible(True)
                self.release_notes.setText(release_body)
        else:
            self.status_label.setText("You are running the latest version.")

    def _on_install_update(self) -> None:
        """Handle install & restart button click."""
        if self._installing:
            return

        if not hasattr(self, "release_url") or not self.release_url:
            QMessageBox.warning(
                self, "Error", "No release URL available for installation."
            )
            return

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Confirm Installation",
            "This will download and install the update, then restart the application.\n\n"
            "Make sure all your work is saved!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Start installation
        self._installing = True
        self.install_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_message.setVisible(True)
        self.status_message.setText("Downloading and installing update...")

        # Run installation in the background
        QTimer.singleShot(100, self._perform_installation)

    def _perform_installation(self) -> None:
        """Perform the actual installation."""
        try:
            self.status_message.setText("Downloading update...")
            logger.info(f"Installing update from {self.release_url}")

            success = self.update_installer.download_and_install(self.release_url)

            if success:
                self.status_message.setText("Installation complete! Restarting...")
                QTimer.singleShot(1000, self._restart_app)
            else:
                self._handle_install_error("Installation failed. Please try again later.")

        except Exception as e:
            logger.exception("Error during installation")
            self._handle_install_error(f"Installation error: {str(e)}")

    def _handle_install_error(self, message: str) -> None:
        """Handle installation errors."""
        self._installing = False
        self.progress_bar.setVisible(False)
        self.status_message.setVisible(False)
        self.install_btn.setEnabled(True)
        self.open_btn.setEnabled(True)

        QMessageBox.critical(self, "Installation Failed", message)
        logger.error(message)

    def _restart_app(self) -> None:
        """Restart the application."""
        try:
            self.update_installer.restart_application()
        except Exception as e:
            logger.error(f"Error restarting application: {e}")
            QMessageBox.critical(
                self,
                "Restart Failed",
                "Update installed but failed to restart.\n\n"
                "Please restart the application manually.",
            )

    def _on_open_release(self) -> None:
        """Open the release page in browser."""
        if hasattr(self, "release_url") and self.release_url:
            QDesktopServices.openUrl(QUrl(self.release_url))
            self.close()
