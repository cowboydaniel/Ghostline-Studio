"""Live console for multi-agent coordination."""
from __future__ import annotations

from PySide6.QtWidgets import QDockWidget, QLabel, QListWidget, QListWidgetItem, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ghostline.agents.agent_manager import AgentManager


class AgentConsole(QDockWidget):
    """Display agent status, logs, and summaries."""

    def __init__(self, manager: AgentManager, parent=None) -> None:
        super().__init__("Multi-Agent Console", parent)
        self.manager = manager

        self.status_list = QListWidget(self)
        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)
        self.refresh_button = QPushButton("Refresh Status")
        self.run_button = QPushButton("Run Agents")

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.addWidget(QLabel("Agents"))
        layout.addWidget(self.status_list)
        layout.addWidget(self.log_output)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.run_button)
        self.setWidget(content)

        self.refresh_button.clicked.connect(self._refresh)
        self.run_button.clicked.connect(self._run_once)

        self._refresh()

    def _refresh(self) -> None:
        self.status_list.clear()
        for status in self.manager.agent_status():
            self.status_list.addItem(QListWidgetItem(status))

    def _run_once(self) -> None:
        results = self.manager.coordinate("ui-triggered review")
        for result in results:
            self.log_output.append(f"[{result.agent_name}] {result.summary}")
            for insight in result.insights:
                self.log_output.append(f" • {insight}")
