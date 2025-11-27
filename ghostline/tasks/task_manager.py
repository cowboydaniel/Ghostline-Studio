"""Task execution utilities for Ghostline Studio."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml
from PySide6.QtCore import QObject, QProcess, Signal


@dataclass
class TaskDefinition:
    name: str
    command: str
    cwd: str | None = None


class TaskManager(QObject):
    output = Signal(str)
    state_changed = Signal(str)
    tasks_loaded = Signal(list)

    def __init__(self, workspace_provider: Callable[[], str | None]) -> None:
        super().__init__()
        self._workspace_provider = workspace_provider
        self.process: QProcess | None = None
        self.tasks: list[TaskDefinition] = []

    def load_workspace_tasks(self) -> None:
        workspace = self._workspace_provider()
        if not workspace:
            self.tasks = []
            self.tasks_loaded.emit(self.tasks)
            return
        config_path = Path(workspace) / ".ghostline" / "tasks.yaml"
        if not config_path.exists():
            self.tasks = []
            self.tasks_loaded.emit(self.tasks)
            return
        data = yaml.safe_load(config_path.read_text()) or []
        self.tasks = [TaskDefinition(**item) for item in data if "name" in item and "command" in item]
        self.tasks_loaded.emit(self.tasks)

    def run_task(self, name: str, file_path: str | None = None) -> None:
        task = next((t for t in self.tasks if t.name == name), None)
        if not task:
            self.output.emit(f"Task '{name}' not found")
            return
        workspace = self._workspace_provider() or ""
        resolved_cmd = self._interpolate(task.command, workspace, file_path)
        cwd = self._interpolate(task.cwd or workspace, workspace, file_path)
        self._start_process(task.name, resolved_cmd, cwd)

    def run_command(self, label: str, command: str, cwd: str | None = None) -> None:
        workspace = self._workspace_provider() or ""
        self._start_process(label, self._interpolate(command, workspace, None), cwd or workspace)

    def stop(self) -> None:
        if self.process and self.process.state() == QProcess.Running:
            self.process.terminate()
            self.state_changed.emit("stopped")

    def _read_stdout(self) -> None:
        if self.process:
            self.output.emit(str(self.process.readAllStandardOutput(), encoding="utf-8"))

    def _read_stderr(self) -> None:
        if self.process:
            self.output.emit(str(self.process.readAllStandardError(), encoding="utf-8"))

    def _on_finished(self) -> None:
        self.state_changed.emit("finished")
        self.output.emit("Task finished")

    def _interpolate(self, value: str, workspace: str, file_path: str | None) -> str:
        if not value:
            return value
        replacements = {
            "${workspaceRoot}": workspace,
        }
        if file_path:
            path_obj = Path(file_path)
            replacements.update(
                {
                    "${fileDirname}": str(path_obj.parent),
                    "${fileBasename}": path_obj.name,
                }
            )
        for key, rep in replacements.items():
            value = value.replace(key, rep)
        return value

    def _start_process(self, label: str, command: str, cwd: str) -> None:
        if self.process and self.process.state() == QProcess.Running:
            self.output.emit("Another task is already running")
            return
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(lambda err: self.output.emit(f"Task error: {err}"))

        self.output.emit(f"Running task: {label}")
        self.state_changed.emit("running")
        program, *args = command.split()
        self.process.setWorkingDirectory(cwd)
        self.process.start(program, args)

