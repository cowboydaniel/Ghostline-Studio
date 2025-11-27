"""Lightweight wrapper around debugpy for Ghostline."""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QObject, Signal

from ghostline.core.logging import get_logger
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
        self.logger = get_logger(__name__)

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
            threading.Thread(target=self._watch_process, daemon=True).start()
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

    def propose_watchpoints(self, variables: list[str]) -> list[str]:
        """Suggest watchpoints when breakpoints are hit."""

        self.output.emit(f"Proposed watchpoints: {', '.join(variables)}")
        return variables

    def refresh_breakpoints(self, path: str) -> list[int]:
        return self.breakpoints.list_for(path)

    def _watch_process(self) -> None:
        if not self.process or not self.process.stdout:
            return
        try:
            for line in self.process.stdout:
                cleaned = line.rstrip()
                if cleaned:
                    self.output.emit(cleaned)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Debugger output read failed: %s", exc)
        finally:
            if self.process and self.process.poll() not in (0, None):
                self.state_changed.emit("error")
                self.output.emit("Debugger crashed. Session detached safely.")
