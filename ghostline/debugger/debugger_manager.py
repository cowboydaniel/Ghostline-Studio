"""Lightweight wrapper around debugpy for Ghostline."""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Iterable, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from ghostline.core.logging import get_logger
from ghostline.debugger.breakpoints import BreakpointStore
from ghostline.debugger.configuration import LaunchConfigurationManager

if TYPE_CHECKING:
    from ghostline.runtime.inspector import RuntimeInspector


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
        self.runtime_inspector: RuntimeInspector | None = None
        self._workspace: Path | None = None
        self._config_manager = LaunchConfigurationManager()
        self._last_launch: tuple[str, list[str], str | None] | None = None

        # Register cleanup handler for subprocess cleanup
        import atexit
        atexit.register(self._cleanup_process)

    def set_runtime_inspector(self, inspector: RuntimeInspector) -> None:
        self.runtime_inspector = inspector

    def set_workspace(self, workspace: Path | None) -> None:
        self._workspace = workspace
        self._config_manager.set_workspace(workspace)

    def _cleanup_process(self) -> None:
        """Cleanup debugger subprocess to prevent resource leaks."""
        if self.process and self.process.poll() is None:
            try:
                self.logger.info("Terminating debugger process (PID: %s)", self.process.pid)
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                    self.logger.info("Debugger process terminated gracefully")
                except subprocess.TimeoutExpired:
                    self.logger.warning("Debugger process did not terminate, killing it")
                    self.process.kill()
                    self.process.wait()
            except Exception as exc:
                self.logger.error("Failed to cleanup debugger process: %s", exc)
            finally:
                self.process = None

    def launch(self, script: str, args: Iterable[str] | None = None, cwd: str | None = None) -> None:
        command = [sys.executable, "-m", "debugpy", "--listen", "5678", script]
        if args:
            command.extend(args)
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=cwd or str(Path(script).parent),
            )
            self._last_launch = (script, list(args) if args else [], cwd)
            self.state_changed.emit("running")
            self.output.emit("Debug session started on port 5678")
            threading.Thread(target=self._watch_process, daemon=True).start()
        except FileNotFoundError:
            self.state_changed.emit("error")
            self.output.emit("debugpy not available. Install with `pip install debugpy`.")

    def launch_for_file(self, file_path: Path, configuration_name: str | None = None) -> None:
        config = self._config_manager.resolve_configuration(configuration_name, file_path)
        if not config:
            self.output.emit("No debug configuration available. Use Add Configuration to create one.")
            self.state_changed.emit("error")
            return
        self.output.emit(f"Launching debug config: {config.name}")
        self.output.emit(f"Program: {config.program}")
        self.launch(config.program, config.args, cwd=config.cwd)

    def restart(self) -> None:
        if not self._last_launch:
            self.output.emit("No previous debug session to restart.")
            return
        script, args, cwd = self._last_launch
        self.output.emit("Restarting debug session...")
        self.stop()
        self.launch(script, args, cwd=cwd)

    def stop(self) -> None:
        """Stop the debugger session cleanly."""
        self._cleanup_process()
        self.state_changed.emit("stopped")
        self.output.emit("Debug session terminated")

    def pause(self) -> None:
        # Placeholder hook for future DAP integration.
        self.state_changed.emit("paused")

    def step(self, action: str = "over") -> None:
        self.output.emit(f"Step {action} requested (debugpy adapter not wired yet)")

    def continue_execution(self) -> None:
        if not self.process:
            self.output.emit("No active debug session to continue.")
            return
        try:
            if hasattr(self.process, "send_signal"):
                import signal

                self.process.send_signal(signal.SIGCONT)
            self.output.emit("Continue requested")
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Failed to continue process: %s", exc)
            self.output.emit(f"Unable to continue process: {exc}")

    def configuration_names(self) -> list[str]:
        return [cfg.name for cfg in self._config_manager.list_configurations()]

    def ensure_launch_file(self) -> Path | None:
        return self._config_manager.ensure_file()

    def add_configuration(self, config: dict) -> None:
        self._config_manager.add_configuration(config)

    def launch_file_path(self) -> Path | None:
        return self._config_manager.config_path()

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
                    if self.runtime_inspector:
                        self.runtime_inspector.record_call_path("debug-session", [cleaned])
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Debugger output read failed: %s", exc)
        finally:
            if self.process and self.process.poll() not in (0, None):
                self.state_changed.emit("error")
                self.output.emit("Debugger crashed. Session detached safely.")
