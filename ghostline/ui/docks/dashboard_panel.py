"""Unified build/test/report dashboard."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ghostline.build.build_manager import BuildManager
from ghostline.testing.test_manager import TestManager
from ghostline.testing.coverage_panel import CoveragePanel


class DashboardPanel(QDockWidget):
    def __init__(
        self,
        build_manager: BuildManager,
        test_manager: TestManager,
        parent=None,
    ) -> None:
        super().__init__("Dashboard", parent)
        self.build_manager = build_manager
        self.test_manager = test_manager

        self.build_status = QListWidget(self)
        self.test_status = QListWidget(self)
        self.coverage = CoveragePanel(self)
        self.ai_insights = QLabel("AI insights pending")
        self.explain_button = QPushButton("Explain this failure")
        self.rewrite_button = QPushButton("Rewrite failing test")

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.addWidget(QLabel("Build status"))
        layout.addWidget(self.build_status)
        layout.addWidget(QLabel("Test results"))
        layout.addWidget(self.test_status)
        layout.addWidget(self.coverage)
        layout.addWidget(self.ai_insights)
        layout.addWidget(self.explain_button)
        layout.addWidget(self.rewrite_button)
        self.setWidget(content)

        self.build_manager.task_finished.connect(self._on_build_finished)
        self.build_manager.task_started.connect(self._on_build_started)
        self.test_manager.state_changed.connect(self._on_test_state)

    def _on_build_started(self, name: str) -> None:
        self.build_status.addItem(QListWidgetItem(f"{name}: running"))

    def _on_build_finished(self, name: str, code: int) -> None:
        self.build_status.addItem(QListWidgetItem(f"{name}: exit {code}"))
        self.ai_insights.setText("AI insights: consider rerunning failed tasks" if code else "Build healthy")

    def _on_test_state(self, state: str) -> None:
        self.test_status.addItem(QListWidgetItem(f"Tests: {state}"))
