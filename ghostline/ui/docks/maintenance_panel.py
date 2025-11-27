"""Dock panel for maintenance daemon suggestions."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDockWidget,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ghostline.ai.maintenance_daemon import MaintenanceAction, MaintenanceDaemon, MaintenanceFinding


class MaintenancePanel(QDockWidget):
    def __init__(self, daemon: MaintenanceDaemon, parent=None) -> None:
        super().__init__("Maintenance", parent)
        self.daemon = daemon

        self.findings = QListWidget(self)
        self.detail = QTextEdit(self)
        self.detail.setReadOnly(True)
        self.apply_button = QPushButton("Apply suggested change")
        self.apply_button.clicked.connect(self._apply_selected)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.addWidget(self.findings)
        layout.addWidget(self.detail)
        layout.addWidget(self.apply_button)
        self.setWidget(content)

        self.findings.itemSelectionChanged.connect(self._on_selection_changed)
        self.daemon.findings_changed.connect(self._refresh)

    def _refresh(self, findings: list[MaintenanceFinding]) -> None:
        self.findings.clear()
        for finding in findings:
            item = QListWidgetItem(f"{finding.label} [{finding.severity}]")
            item.setData(1, finding)
            self.findings.addItem(item)

    def _on_selection_changed(self) -> None:
        item = self.findings.currentItem()
        if not item:
            self.detail.clear()
            return
        finding: MaintenanceFinding = item.data(1)
        actions = "\n".join(action.title for action in finding.actions) or "No actions proposed"
        self.detail.setPlainText(f"{finding.detail}\n\nActions:\n{actions}")

    def _apply_selected(self) -> None:
        item = self.findings.currentItem()
        if not item:
            return
        finding: MaintenanceFinding = item.data(1)
        self.detail.append("\nApplying actions...")
        for action in finding.actions:
            self._apply_action(action)
        self.detail.append("Applied. Consider reviewing the maintenance branch.")

    def _apply_action(self, action: MaintenanceAction) -> None:
        # Placeholder for integration with refactor pipeline
        self.detail.append(f"- {action.title}: {action.description}")
