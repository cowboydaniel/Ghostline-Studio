"""Architecture insights dock panel."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QPushButton, QTextEdit, QVBoxLayout, QWidget, QDockWidget

from ghostline.ai.architecture_assistant import ArchitectureAssistant, ArchitectureInsight


class ArchitecturePanel(QDockWidget):
    def __init__(self, assistant: ArchitectureAssistant, parent=None) -> None:
        super().__init__("Architecture", parent)
        self.assistant = assistant
        self.issue_list = QListWidget(self)
        self.recommendations = QTextEdit(self)
        self.recommendations.setReadOnly(True)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.addWidget(self.issue_list)
        layout.addWidget(self.recommendations)
        layout.addWidget(self.refresh_button)
        self.setWidget(content)

    def refresh(self) -> None:
        insights = self.assistant.detect_code_smells() + list(self.assistant.propose_refactors())
        self._populate_issues(insights)
        boundaries = self.assistant.suggest_boundaries()
        if boundaries:
            self.recommendations.setPlainText(boundaries[0].detail)

    def _populate_issues(self, issues: list[ArchitectureInsight]) -> None:
        self.issue_list.clear()
        for issue in issues:
            item = QListWidgetItem(f"[{issue.severity}] {issue.title}")
            item.setData(Qt.UserRole, issue)
            self.issue_list.addItem(item)

