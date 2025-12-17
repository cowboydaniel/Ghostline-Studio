"""Community and Changelog dialogs for Ghostline Studio."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QTextEdit,
)

from ghostline.core.urls import COMMUNITY_URL, REPO_URL, RELEASES_URL


class CommunityDialog(QDialog):
    """Dialog showing community resources and support information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Join the Community")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Ghostline Community")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        layout.addSpacing(10)

        # Community info
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setText(
            """Welcome to the Ghostline Community!

Get Help & Support:
• GitHub Discussions - Ask questions and share ideas with the community
• GitHub Issues - Report bugs and request features
• Repository - Explore the source code and contribute

Contribute:
• Fork the repository
• Create a feature branch
• Submit pull requests
• Help improve documentation
• Share your extensions and use cases

Connect:
• Star the project on GitHub
• Follow for updates
• Participate in discussions
• Provide feedback
"""
        )
        layout.addWidget(info_text)

        layout.addSpacing(10)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        discussions_btn = QPushButton("GitHub Discussions")
        discussions_btn.clicked.connect(self._on_discussions)
        button_layout.addWidget(discussions_btn)

        repo_btn = QPushButton("View Repository")
        repo_btn.clicked.connect(self._on_repository)
        button_layout.addWidget(repo_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _on_discussions(self) -> None:
        """Open GitHub Discussions."""
        QDesktopServices.openUrl(QUrl(COMMUNITY_URL))
        self.close()

    def _on_repository(self) -> None:
        """Open GitHub repository."""
        QDesktopServices.openUrl(QUrl(REPO_URL))
        self.close()


class ChangelogDialog(QDialog):
    """Dialog for viewing the changelog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ghostline Changelog")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self._setup_ui()
        self._load_changelog()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Changelog")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        layout.addSpacing(10)

        # Changelog content
        self.content_view = QTextEdit()
        self.content_view.setReadOnly(True)
        layout.addWidget(self.content_view)

        layout.addSpacing(10)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        releases_btn = QPushButton("View All Releases")
        releases_btn.clicked.connect(self._on_view_releases)
        button_layout.addWidget(releases_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _load_changelog(self) -> None:
        """Load CHANGELOG.md file."""
        changelog_paths = [
            Path(__file__).resolve().parent.parent.parent.parent / "CHANGELOG.md",
            Path(__file__).resolve().parent.parent.parent / "CHANGELOG.md",
            Path.cwd() / "CHANGELOG.md",
            Path.home() / "Ghostline-Studio" / "CHANGELOG.md",
        ]

        changelog_content = ""
        for path in changelog_paths:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        changelog_content = f.read()
                    self.content_view.setText(changelog_content)
                    return
                except Exception as e:
                    print(f"Error reading changelog: {e}")
                    break

        # If no local changelog, show a default message
        if not changelog_content:
            self.content_view.setText(
                """# Ghostline Changelog

View the complete changelog and release notes on GitHub.

Visit the Releases page to see:
• Latest version information
• New features and improvements
• Bug fixes
• Breaking changes
• Upgrade guides

Click 'View All Releases' below to open the releases page.
"""
            )

    def _on_view_releases(self) -> None:
        """Open releases page in browser."""
        QDesktopServices.openUrl(QUrl(RELEASES_URL))
        self.close()
