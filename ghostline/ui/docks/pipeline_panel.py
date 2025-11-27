"""Pipeline editor and control panel."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ghostline.workflows.pipeline_manager import PipelineDefinition, PipelineManager


class PipelinePanel(QDockWidget):
    """UI for managing autonomous pipelines."""

    def __init__(self, manager: PipelineManager, parent=None) -> None:
        super().__init__("Pipelines", parent)
        self.manager = manager

        self.pipeline_list = QListWidget(self)
        self.details = QTextEdit(self)
        self.details.setReadOnly(True)
        self.toggle_button = QPushButton("Enable/Disable")
        self.run_button = QPushButton("Run Pipeline")
        self.import_button = QPushButton("Import YAML")

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.addWidget(QLabel("Configured pipelines"))
        layout.addWidget(self.pipeline_list)
        layout.addWidget(self.details)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.run_button)
        layout.addWidget(self.import_button)
        self.setWidget(content)

        self.pipeline_list.currentItemChanged.connect(self._refresh_details)
        self.run_button.clicked.connect(self._run_selected)
        self.toggle_button.clicked.connect(self._toggle_selected)
        self.import_button.clicked.connect(self._import_yaml)

        self._populate()

    def _populate(self) -> None:
        self.pipeline_list.clear()
        for pipeline in self.manager.pipelines:
            item = QListWidgetItem(pipeline.name)
            item.setData(0x0100, pipeline)  # Qt.UserRole
            self.pipeline_list.addItem(item)
        if self.pipeline_list.count():
            self.pipeline_list.setCurrentRow(0)

    def _refresh_details(self) -> None:
        item = self.pipeline_list.currentItem()
        if not item:
            self.details.clear()
            return
        pipeline: PipelineDefinition | None = item.data(0x0100)
        if not pipeline:
            return
        trigger_text = ", ".join(pipeline.triggers)
        steps = "\n".join(f"- {step.kind}" for step in pipeline.steps)
        status = "enabled" if pipeline.enabled else "disabled"
        last_run = pipeline.last_run.isoformat() if pipeline.last_run else "never"
        self.details.setPlainText(
            f"Status: {status}\nTriggers: {trigger_text}\nLast run: {last_run}\nSteps:\n{steps}"
        )

    def _run_selected(self) -> None:
        item = self.pipeline_list.currentItem()
        pipeline: PipelineDefinition | None = item.data(0x0100) if item else None
        if pipeline:
            self.manager.run_pipeline(pipeline)
            self._refresh_details()

    def _toggle_selected(self) -> None:
        item = self.pipeline_list.currentItem()
        pipeline: PipelineDefinition | None = item.data(0x0100) if item else None
        if pipeline:
            pipeline.enabled = not pipeline.enabled
            self._refresh_details()

    def _import_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import pipeline.yaml", str(Path.cwd()), "YAML (*.yaml *.yml)")
        if path:
            self.manager.config_path = Path(path)
            self.manager.pipelines.clear()
            self.manager._load()
            self._populate()
