"""Multi-process build and task orchestration."""
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List

from PySide6.QtCore import QObject, Signal


@dataclass
class BuildTask:
    name: str
    command: str
    cwd: Path
    dependencies: list[str] = field(default_factory=list)


class BuildManager(QObject):
    """Coordinate multiple build/test processes with dependency awareness."""

    task_started = Signal(str)
    task_finished = Signal(str, int)
    task_output = Signal(str, str)
    queue_changed = Signal(list)
    state_changed = Signal(str)

    def __init__(self, workspace_provider: Callable[[], str | None]) -> None:
        super().__init__()
        self.workspace_provider = workspace_provider
        self.tasks: Dict[str, BuildTask] = {}
        self.running: Dict[str, subprocess.Popen] = {}
        self._queue: list[str] = []
        self._last_results: dict[str, int] = {}

    def register_task(self, name: str, command: str, dependencies: Iterable[str] | None = None) -> None:
        workspace = Path(self.workspace_provider() or ".")
        self.tasks[name] = BuildTask(name, command, workspace, list(dependencies or []))
        self.queue_changed.emit(list(self.tasks))

    def enqueue_all(self) -> None:
        self._queue = list(self.tasks)
        self._start_ready_tasks()

    def enqueue(self, task_names: Iterable[str]) -> None:
        for name in task_names:
            if name in self.tasks and name not in self._queue:
                self._queue.append(name)
        self._start_ready_tasks()

    def _start_ready_tasks(self) -> None:
        ready = [name for name in self._queue if self._dependencies_finished(name)]
        for name in ready:
            self._queue.remove(name)
            self._start_process(self.tasks[name])
        self.queue_changed.emit(list(self._queue))
        self._emit_state()

    def _dependencies_finished(self, name: str) -> bool:
        deps = self.tasks[name].dependencies
        return all(dep not in self.running for dep in deps)

    def _start_process(self, task: BuildTask) -> None:
        self.task_started.emit(task.name)
        process = subprocess.Popen(
            task.command.split(),
            cwd=task.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.running[task.name] = process
        threading.Thread(target=self._stream_output, args=(task.name, process), daemon=True).start()
        self._emit_state()

    def _stream_output(self, name: str, process: subprocess.Popen) -> None:
        assert process.stdout
        for line in process.stdout:
            self.task_output.emit(name, line.rstrip())
        return_code = process.wait()
        self.running.pop(name, None)
        self._last_results[name] = return_code
        self.task_finished.emit(name, return_code)
        self._start_ready_tasks()
        self._emit_state()

    def cancel_all(self) -> None:
        for process in list(self.running.values()):
            process.terminate()
        self.running.clear()
        self._queue.clear()
        self.queue_changed.emit([])
        self._emit_state()

    def _emit_state(self) -> None:
        if self.running:
            self.state_changed.emit("running")
        elif self._queue:
            self.state_changed.emit("queued")
        else:
            self.state_changed.emit("idle")

    def recent_results(self) -> dict[str, int]:
        return dict(self._last_results)

