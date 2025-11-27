"""Coordinator for language server clients."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterable

import yaml

from PySide6.QtCore import QObject, Signal

from ghostline.core.config import ConfigManager
from ghostline.lang.diagnostics import Diagnostic
from ghostline.lang.lsp_client import LSPClient
from ghostline.workspace.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


class LSPManager(QObject):
    """Manage language server lifecycles and route editor events."""

    lsp_error = Signal(str)

    def __init__(self, config: ConfigManager, workspace_manager: WorkspaceManager, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.workspace_manager = workspace_manager
        self.clients: dict[str, dict[str, LSPClient]] = {}
        self._diag_callbacks: list[Callable[[list[Diagnostic]], None]] = []
        self._pending: dict[int, Callable[[dict], None]] = {}
        self._language_map = self._build_language_map()
        self._ensure_default_servers()

    # Client management
    def _language_for_file(self, path: str) -> str | None:
        suffix = Path(path).suffix.lower()
        return self._language_map.get(suffix)

    def _build_language_map(self) -> dict[str, str]:
        """Map file extensions to configured languages."""
        mapping: dict[str, str] = {
            ".py": "python",
            ".ts": "typescript",
            ".js": "typescript",
            ".c": "c_cpp",
            ".h": "c_cpp",
            ".cpp": "c_cpp",
            ".cc": "c_cpp",
            ".hpp": "c_cpp",
            ".java": "java",
            ".rs": "rust",
        }
        overrides = self.config.get("lsp", {}).get("extension_map", {})
        mapping.update({f".{k.lstrip('.')}": v for k, v in overrides.items()})
        return mapping

    def _ensure_default_servers(self) -> None:
        """Merge packaged defaults into user configuration if missing."""
        bundled_cfg_path = Path(__file__).resolve().parent / "lsp_config.yaml"
        bundled = yaml.safe_load(bundled_cfg_path.read_text()) if bundled_cfg_path.exists() else {}
        servers = bundled.get("servers", {})
        cfg = self.config.get("lsp", {})
        cfg.setdefault("servers", {})
        for name, definition in servers.items():
            cfg["servers"].setdefault(name, definition)
        extension_map = bundled.get("extension_map", {})
        cfg.setdefault("extension_map", {})
        cfg["extension_map"] = {**extension_map, **cfg["extension_map"]}
        self.config.settings["lsp"] = cfg

    def _get_client(self, language: str) -> LSPClient | None:
        workspace = self.workspace_manager.current_workspace or str(Path(path := ".").resolve())
        lang_clients = self.clients.setdefault(workspace, {})
        if language in lang_clients:
            return lang_clients[language]
        server_cfg = self.config.get("lsp", {}).get("servers", {}).get(language)
        if not server_cfg:
            logger.warning("No LSP server configured for %s", language)
            self.lsp_error.emit(f"No LSP configured for {language}")
            return None
        command = [server_cfg.get("command")] + list(server_cfg.get("args", []))
        try:
            client = LSPClient(command, workdir=workspace)
        except FileNotFoundError:
            message = f"LSP server for {language} not found. Install: {server_cfg.get('command')}"
            logger.error(message)
            self.lsp_error.emit(message)
            return None
        client.notification_received.connect(self._handle_notification)
        client.response_received.connect(self._handle_response)
        client.start()
        lang_clients[language] = client
        self._initialize(client, workspace)
        return client

    def _initialize(self, client: LSPClient, workspace: str) -> None:
        root_uri = Path(workspace).resolve().as_uri()
        client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": root_uri,
                "capabilities": {},
                "workspaceFolders": [{"uri": root_uri, "name": Path(workspace).name}],
            },
        )
        client.send_notification("initialized", {})

    # Document events
    def open_document(self, path: str, text: str) -> None:
        language = self._language_for_file(path)
        if not language:
            return
        client = self._get_client(language)
        if not client:
            return
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": Path(path).resolve().as_uri(),
                    "languageId": language,
                    "version": 1,
                    "text": text,
                }
            },
        )

    def change_document(self, path: str, text: str, version: int) -> None:
        language = self._language_for_file(path)
        client = self._get_client(language) if language else None
        if not client:
            return
        client.send_notification(
            "textDocument/didChange",
            {
                "textDocument": {
                    "uri": Path(path).resolve().as_uri(),
                    "version": version,
                },
                "contentChanges": [{"text": text}],
            },
        )

    def close_document(self, path: str) -> None:
        language = self._language_for_file(path)
        client = self._get_client(language) if language else None
        if not client:
            return
        client.send_notification(
            "textDocument/didClose",
            {"textDocument": {"uri": Path(path).resolve().as_uri()}},
        )

    # Feature requests
    def request_completions(self, path: str, position: dict[str, int], callback: Callable[[dict], None] | None = None) -> int | None:
        language = self._language_for_file(path)
        client = self._get_client(language) if language else None
        if not client:
            return None
        request_id = client.send_request(
            "textDocument/completion",
            {"textDocument": {"uri": Path(path).resolve().as_uri()}, "position": position},
        )
        if callback:
            self._pending[request_id] = callback
        return request_id

    def request_hover(self, path: str, position: dict[str, int], callback: Callable[[dict], None] | None = None) -> int | None:
        language = self._language_for_file(path)
        client = self._get_client(language) if language else None
        if not client:
            return None
        request_id = client.send_request(
            "textDocument/hover",
            {"textDocument": {"uri": Path(path).resolve().as_uri()}, "position": position},
        )
        if callback:
            self._pending[request_id] = callback
        return request_id

    # Diagnostics
    def subscribe_diagnostics(self, callback: Callable[[list[Diagnostic]], None]) -> None:
        self._diag_callbacks.append(callback)

    def _handle_notification(self, message: Dict[str, Any]) -> None:
        method = message.get("method")
        params = message.get("params", {})
        if method == "textDocument/publishDiagnostics":
            diagnostics = []
            uri = params.get("uri", "")
            file_path = Path(uri.replace("file://", ""))
            for diag in params.get("diagnostics", []):
                range_ = diag.get("range", {})
                start = range_.get("start", {})
                diagnostics.append(
                    Diagnostic(
                        file=str(file_path),
                        line=start.get("line", 0),
                        col=start.get("character", 0),
                        severity=str(diag.get("severity", "info")),
                        message=diag.get("message", ""),
                    )
                )
            for callback in self._diag_callbacks:
                callback(diagnostics)

    def _handle_response(self, message: Dict[str, Any]) -> None:
        request_id = message.get("id")
        if request_id in self._pending:
            callback = self._pending.pop(request_id)
            callback(message)

