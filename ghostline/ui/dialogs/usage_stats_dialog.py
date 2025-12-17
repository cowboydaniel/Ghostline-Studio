"""Usage statistics window for Ghostline Studio."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFormLayout,
    QWidget,
    QMessageBox,
)

from ghostline.core.usage_stats import UsageStatsTracker


class UsageStatsDialog(QDialog):
    """Window displaying usage statistics for the application."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.stats_tracker = UsageStatsTracker()
        self.setWindowTitle("Ghostline Usage Statistics")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self._setup_ui()
        self._update_stats()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Usage Statistics")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        layout.addSpacing(10)

        # Stats display
        stats_layout = QFormLayout()

        self.launches_label = QLabel()
        stats_layout.addRow("App Launches:", self.launches_label)

        self.session_time_label = QLabel()
        stats_layout.addRow("Total Session Time:", self.session_time_label)

        self.files_opened_label = QLabel()
        stats_layout.addRow("Files Opened:", self.files_opened_label)

        self.ai_requests_label = QLabel()
        stats_layout.addRow("AI Requests:", self.ai_requests_label)

        self.commands_executed_label = QLabel()
        stats_layout.addRow("Commands Executed:", self.commands_executed_label)

        self.first_launch_label = QLabel()
        stats_layout.addRow("First Launch:", self.first_launch_label)

        layout.addLayout(stats_layout)

        layout.addSpacing(20)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        reset_btn = QPushButton("Reset Usage Stats")
        reset_btn.clicked.connect(self._on_reset)
        button_layout.addWidget(reset_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._update_stats)
        button_layout.addWidget(refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _update_stats(self) -> None:
        """Update the statistics display."""
        stats = self.stats_tracker.get_stats()

        launches = stats.get("app_launches", 0)
        self.launches_label.setText(str(launches))

        session_time = self.stats_tracker.get_formatted_session_time()
        self.session_time_label.setText(session_time)

        files_opened = stats.get("files_opened", 0)
        self.files_opened_label.setText(str(files_opened))

        ai_requests = stats.get("ai_requests_count", 0)
        self.ai_requests_label.setText(str(ai_requests))

        commands = stats.get("commands_executed", 0)
        self.commands_executed_label.setText(str(commands))

        first_launch = stats.get("first_launch_date", "N/A")
        if first_launch and first_launch != "N/A":
            # Format the ISO date to something readable
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(first_launch)
                first_launch = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        self.first_launch_label.setText(str(first_launch))

    def _on_reset(self) -> None:
        """Reset usage statistics."""
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "Are you sure you want to reset all usage statistics?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.stats_tracker.reset()
            self._update_stats()
            QMessageBox.information(
                self, "Reset", "Usage statistics have been reset."
            )
