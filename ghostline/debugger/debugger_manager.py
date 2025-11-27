"""Lightweight wrapper around debugpy for Ghostline."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QObject, Signal

from ghostline.debugger.breakpoints import BreakpointStore


class DebuggerManager(QObject):
    output = Signal(str)
    state_changed = Signal(str)
    variables_ready = Signal(dict)
    callstack_ready = Signal(list)

    def __init__(self, breakpoint_store: BreakpointStore | None = None) -> None:
        super().__init__()
        self.breakpoints = breakpoint_store or BreakpointStore.instance()
        self.process: subprocess.Popen | None = None

    def launch(self, script: str, args: Iterable[str] | None = None) -> None:
        command = [sys.executable, "-m", "debugpy", "--listen", "5678", script]
        if args:
            command.extend(args)
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(Path(script).parent),
            )
            self.state_changed.emit("running")
            self.output.emit("Debug session started on port 5678")
        except FileNotFoundError:
            self.state_changed.emit("error")
            self.output.emit("debugpy not available. Install with `pip install debugpy`.")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.state_changed.emit("stopped")
            self.output.emit("Debug session terminated")

    def pause(self) -> None:
        # Placeholder hook for future DAP integration.
        self.state_changed.emit("paused")

    def step(self, action: str = "over") -> None:
        self.output.emit(f"Step {action} requested (DAP stub)")

    def refresh_breakpoints(self, path: str) -> list[int]:
        return self.breakpoints.list_for(path)
