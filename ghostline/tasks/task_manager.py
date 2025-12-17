"""Task execution utilities for Ghostline Studio."""
from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import yaml
from PySide6.QtCore import QObject, QProcess, Signal


@dataclass
class TaskDefinition:
    name: str
    command: str
    cwd: str | None = None
    args: list[str] | None = None
    group: str | None = None
    is_default: bool = False


class TaskManager(QObject):
    output = Signal(str)
    state_changed = Signal(str)
    tasks_loaded = Signal(list)
    task_statuses = Signal(dict)

    def __init__(self, workspace_provider: Callable[[], str | None], preferences: dict | None = None) -> None:
        super().__init__()
        self._workspace_provider = workspace_provider
        self.preferences = preferences if preferences is not None else {}
        self.processes: dict[str, QProcess] = {}
        self.tasks: list[TaskDefinition] = []
        self.task_states: dict[str, str] = {}
        self.default_build_task: str | None = self.preferences.get("default_build_task")

    def load_workspace_tasks(self) -> None:
        workspace = self._workspace_provider()
        if not workspace:
            self.tasks = []
            self.tasks_loaded.emit(self.tasks)
            return
        config_path = self._discover_config(Path(workspace))
        if not config_path:
            self.tasks = []
            self.tasks_loaded.emit(self.tasks)
            return
        data = self._load_config(config_path)
        self.tasks = [task for task in (self._parse_task(item) for item in data) if task]
        if not self.default_build_task:
            self.default_build_task = next((t.name for t in self.tasks if t.is_default or t.group == "build"), None)
        self.tasks_loaded.emit(self.tasks)
        self._emit_statuses()

    def _discover_config(self, workspace: Path) -> Path | None:
        ghostline_dir = workspace / ".ghostline"
        for candidate in (ghostline_dir / "tasks.json", ghostline_dir / "tasks.yaml"):
            if candidate.exists():
                return candidate
        return None

    def _load_config(self, path: Path) -> list[dict]:
        if path.suffix == ".json":
            return (json.loads(path.read_text()) or {}).get("tasks", [])
        raw = yaml.safe_load(path.read_text()) or []
        if isinstance(raw, dict):
            return raw.get("tasks", [])
        return raw

    def _parse_task(self, item: dict | None) -> TaskDefinition | None:
        if not item:
            return None
        name = item.get("name") or item.get("label")
        command = item.get("command")
        if not name or not command:
            return None
        args = item.get("args") if isinstance(item.get("args"), list) else None
        cwd = item.get("options", {}).get("cwd") if isinstance(item.get("options"), dict) else item.get("cwd")
        group = None
        is_default = False
        group_cfg = item.get("group")
        if isinstance(group_cfg, str):
            group = group_cfg
        elif isinstance(group_cfg, dict):
            group = group_cfg.get("kind") or group_cfg.get("type")
            is_default = bool(group_cfg.get("isDefault"))
        is_default = bool(item.get("isDefault")) or is_default or bool(item.get("isDefaultTask"))
        if item.get("isBuildCommand"):
            group = group or "build"
            is_default = True
        return TaskDefinition(name=name, command=command, args=args, cwd=cwd, group=group, is_default=is_default)

    def run_task(self, name: str, file_path: str | None = None) -> None:
        task = next((t for t in self.tasks if t.name == name), None)
        if not task:
            self.output.emit(f"Task '{name}' not found")
            return
        workspace = self._workspace_provider() or ""
        resolved_cmd = self._build_command(task, workspace, file_path)
        cwd = self._interpolate(task.cwd or workspace, workspace, file_path)
        self._start_process(task.name, resolved_cmd, cwd)

    def run_build_task(self) -> None:
        build_tasks = [t for t in self.tasks if t.group == "build" or t.is_default]
        if not build_tasks:
            self.output.emit("No build tasks configured")
            return
        target = next((t for t in build_tasks if t.name == self.default_build_task), None) or build_tasks[0]
        self.run_task(target.name)

    def set_default_build_task(self, name: str) -> None:
        self.default_build_task = name
        self.preferences["default_build_task"] = name
        self._emit_statuses()

    def run_command(self, label: str, command: str, cwd: str | None = None) -> None:
        workspace = self._workspace_provider() or ""
        self._start_process(label, self._interpolate(command, workspace, None), cwd or workspace)

    def stop(self) -> None:
        for label, process in list(self.processes.items()):
            if process.state() == QProcess.Running:
                process.terminate()
                self._update_state(label, "stopped")

    def terminate_task(self, name: str) -> None:
        process = self.processes.get(name)
        if process and process.state() == QProcess.Running:
            process.terminate()
            self._update_state(name, "stopped")

    def restart_task(self, name: str) -> None:
        self.terminate_task(name)
        self.run_task(name)

    def _read_stdout(self, label: str) -> None:
        process = self.processes.get(label)
        if process:
            self.output.emit(f"[{label}] {str(process.readAllStandardOutput(), encoding='utf-8')}")

    def _read_stderr(self, label: str) -> None:
        process = self.processes.get(label)
        if process:
            self.output.emit(f"[{label}] {str(process.readAllStandardError(), encoding='utf-8')}")

    def _on_finished(self, label: str, exit_code: int | None = None, _status: QProcess.ExitStatus | None = None) -> None:
        state = "finished" if not exit_code else "failed"
        self._update_state(label, state)
        self.output.emit(f"Task finished: {label}")
        self.processes.pop(label, None)

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

    def _build_command(self, task: TaskDefinition, workspace: str, file_path: str | None) -> str:
        base = self._interpolate(task.command, workspace, file_path)
        args = [self._interpolate(arg, workspace, file_path) for arg in (task.args or [])]
        if args:
            base = " ".join([base, *[shlex.quote(arg) for arg in args]])
        return base

    def _start_process(self, label: str, command: str, cwd: str) -> None:
        if label in self.processes and self.processes[label].state() == QProcess.Running:
            self.output.emit(f"Task '{label}' already running")
            return
        process = QProcess(self)
        process.readyReadStandardOutput.connect(lambda: self._read_stdout(label))
        process.readyReadStandardError.connect(lambda: self._read_stderr(label))
        process.errorOccurred.connect(lambda err: self.output.emit(f"Task error ({label}): {err}"))

        self.output.emit(f"Running task: {label}")
        self._update_state(label, "running")
        parts = shlex.split(command)
        if not parts:
            self.output.emit(f"Task '{label}' has an empty command")
            return
        program, *args = parts
        process.setWorkingDirectory(cwd)
        process.finished.connect(lambda exit_code, status: self._on_finished(label, exit_code, status))
        process.start(program, args)
        self.processes[label] = process

    def run_tasks_concurrently(self, task_names: Iterable[str]) -> None:
        for name in task_names:
            task = next((t for t in self.tasks if t.name == name), None)
            if task:
                workspace = self._workspace_provider() or ""
                resolved_cmd = self._build_command(task, workspace, None)
                cwd = self._interpolate(task.cwd or workspace, workspace, None)
                self._start_process(task.name, resolved_cmd, cwd)

    def _update_state(self, label: str, state: str) -> None:
        self.task_states[label] = state
        self.state_changed.emit(f"{state}:{label}")
        self._emit_statuses()

    def _emit_statuses(self) -> None:
        self.task_statuses.emit(dict(self.task_states))

