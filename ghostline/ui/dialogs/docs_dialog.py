"""Documentation viewer for Ghostline Studio."""
from __future__ import annotations

import logging
from pathlib import Path

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
    QListWidget,
    QListWidgetItem,
    QSplitter,
)
from PySide6.QtCore import Qt

from ghostline.core.urls import REPO_URL

logger = logging.getLogger(__name__)


class DocsDialog(QDialog):
    """Dialog for browsing and viewing documentation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ghostline Documentation")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        self.docs_dir = self._find_docs_directory()
        self._setup_ui()
        self._load_docs()

    def _find_docs_directory(self) -> Path | None:
        """Find the docs directory in the project."""
        # Try multiple possible locations
        candidates = [
            Path(__file__).resolve().parent.parent.parent.parent / "docs",
            Path(__file__).resolve().parent.parent.parent / "docs",
            Path.cwd() / "docs",
            Path.home() / "Ghostline-Studio" / "docs",
        ]

        for path in candidates:
            if path.exists() and path.is_dir():
                return path

        return None

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Documentation")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        layout.addSpacing(10)

        if self.docs_dir:
            # Splitter for file list and content
            splitter = QSplitter(Qt.Orientation.Horizontal)

            # File list
            self.doc_list = QListWidget()
            self.doc_list.itemClicked.connect(self._on_doc_selected)
            splitter.addWidget(self.doc_list)

            # Content viewer
            self.content_view = QTextEdit()
            self.content_view.setReadOnly(True)
            splitter.addWidget(self.content_view)

            splitter.setSizes([200, 500])
            layout.addWidget(splitter)
        else:
            # No local docs, show message
            no_docs_label = QLabel(
                "Local documentation not found.\n\n"
                "You can view the documentation online or open the README file."
            )
            layout.addWidget(no_docs_label)

            layout.addStretch()

        layout.addSpacing(10)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        online_btn = QPushButton("View Online")
        online_btn.clicked.connect(self._on_view_online)
        button_layout.addWidget(online_btn)

        readme_btn = QPushButton("Open README")
        readme_btn.clicked.connect(self._on_open_readme)
        button_layout.addWidget(readme_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _load_docs(self) -> None:
        """Load documentation files from docs directory."""
        if not self.docs_dir:
            return

        try:
            # Find all markdown files
            md_files = sorted(self.docs_dir.glob("*.md"))

            for file in md_files:
                item = QListWidgetItem(file.stem.replace("_", " ").title())
                item.setData(Qt.ItemDataRole.UserRole, str(file))
                self.doc_list.addItem(item)

            # Also look for subdirectories
            for subdir in sorted(self.docs_dir.iterdir()):
                if subdir.is_dir() and not subdir.name.startswith("."):
                    for file in sorted(subdir.glob("*.md")):
                        display_name = f"{subdir.name} / {file.stem}".replace(
                            "_", " "
                        ).title()
                        item = QListWidgetItem(display_name)
                        item.setData(Qt.ItemDataRole.UserRole, str(file))
                        self.doc_list.addItem(item)

            # Select first item if available
            if self.doc_list.count() > 0:
                self.doc_list.setCurrentRow(0)
                self._on_doc_selected(self.doc_list.item(0))

        except Exception as e:
            logger.error(f"Error loading docs: {e}")

    def _on_doc_selected(self, item: QListWidgetItem) -> None:
        """Handle documentation file selection."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.content_view.setText(content)
        except Exception as e:
            logger.error(f"Error reading doc file: {e}")
            self.content_view.setText(f"Error loading file: {e}")

    def _on_view_online(self) -> None:
        """Open documentation URL in browser."""
        docs_url = QUrl(f"{REPO_URL}#documentation")
        QDesktopServices.openUrl(docs_url)

    def _on_open_readme(self) -> None:
        """Open README.md file."""
        readme_paths = [
            Path(__file__).resolve().parent.parent.parent.parent / "README.md",
            Path(__file__).resolve().parent.parent.parent / "README.md",
            Path.cwd() / "README.md",
            Path.home() / "Ghostline-Studio" / "README.md",
        ]

        readme_file = None
        for path in readme_paths:
            if path.exists():
                readme_file = path
                break

        if readme_file:
            try:
                with open(readme_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.content_view.setText(content)
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"Failed to open README: {e}"
                )
        else:
            QMessageBox.information(
                self,
                "README Not Found",
                "README.md file could not be found locally.\n\n"
                "Opening GitHub repository...",
            )
            QDesktopServices.openUrl(QUrl(REPO_URL))
