"""Minimal JSON-RPC client for talking to language servers."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QProcess, QByteArray, Signal
from shiboken6 import isValid

logger = logging.getLogger(__name__)


class LSPClient(QObject):
    """Starts an LSP server process and handles JSON-RPC messaging."""

    response_received = Signal(dict)
    notification_received = Signal(dict)
    started = Signal()

    def __init__(self, command: list[str], workdir: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.command = command
        self.workdir = workdir
        self.process = QProcess(self)
        self._id_counter = 0
        self._buffer = b""

        self.process.readyReadStandardOutput.connect(self._on_ready_read)
        self.process.started.connect(self._on_started)
        self.process.errorOccurred.connect(self._on_error)

    def start(self) -> None:
        if not self.command:
            raise RuntimeError("No command configured for LSP client")
        program, *args = self.command
        self._command = program
        self._args = args
        self.process.setWorkingDirectory(self.workdir or "")
        logger.info("Starting LSP client: %r %r", self._command, self._args)
        self.process.start(program, args)

    def stop(self) -> None:
        if not isValid(self.process):
            return
        if self.process.state() == QProcess.Running:
            try:
                self.send_request("shutdown", {})
            except Exception:
                logger.debug("Failed to send LSP shutdown request", exc_info=True)
            try:
                self.send_notification("exit", {})
            except Exception:
                logger.debug("Failed to send LSP exit notification", exc_info=True)
            self.process.terminate()
            finished = self.process.waitForFinished(2000)
            if not finished and self.process.state() != QProcess.NotRunning:
                logger.warning("LSP client did not terminate gracefully; killing process")
                self.process.kill()
                self.process.waitForFinished(1000)

    def send_request(self, method: str, params: dict[str, Any] | None = None) -> int:
        self._id_counter += 1
        payload = {"jsonrpc": "2.0", "id": self._id_counter, "method": method}
        if params is not None:
            payload["params"] = params
        self._send_payload(payload)
        return self._id_counter

    def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._send_payload(payload)

    # JSON-RPC plumbing
    def _send_payload(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        message = f"Content-Length: {len(data)}\r\n\r\n".encode("utf-8") + data
        self.process.write(QByteArray(message))
        logger.debug("LSP -> %s", payload)

    def _on_started(self) -> None:  # pragma: no cover - Qt started callback
        logger.info("LSP client started successfully: %r %r", self._command, self._args)
        self.started.emit()

    def _on_ready_read(self) -> None:
        """Handle incoming data from LSP process with safety checks."""
        # Validate process is still valid and running
        if not isValid(self.process):
            logger.warning("Received data from invalid LSP process")
            return

        if self.process.state() != QProcess.Running:
            logger.debug("Received data from non-running LSP process")
            return

        try:
            data = bytes(self.process.readAllStandardOutput())
            self._buffer += data

            while True:
                message, rest = self._extract_message(self._buffer)
                if message is None:
                    break
                self._buffer = rest
                self._handle_message(message)
        except Exception:
            logger.exception("Error reading LSP output")

    def _extract_message(self, data: bytes) -> tuple[dict[str, Any] | None, bytes]:
        header_end = data.find(b"\r\n\r\n")
        if header_end == -1:
            return None, data
        headers = data[:header_end].decode("utf-8", errors="ignore")
        content_length = 0
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-length"):
                try:
                    content_length = int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
        body_start = header_end + 4
        if len(data) < body_start + content_length:
            return None, data
        body = data[body_start : body_start + content_length]
        try:
            return json.loads(body.decode("utf-8")), data[body_start + content_length :]
        except json.JSONDecodeError:
            logger.warning("Failed to decode LSP message: %s", body)
            return None, data[body_start + content_length :]

    def _handle_message(self, message: dict[str, Any]) -> None:
        logger.debug("LSP <- %s", message)
        if "id" in message:
            self.response_received.emit(message)
        elif "method" in message:
            self.notification_received.emit(message)

    def _on_error(self, error) -> None:  # pragma: no cover - Qt error callback
        if error == QProcess.ProcessError.FailedToStart:
            logger.error(
                "LSP failed to start for %r %r. Check that the configured command exists and is executable.",
                self._command,
                self._args,
            )
        else:
            logger.error("LSP client process error: %s", error)

