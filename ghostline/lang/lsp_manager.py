"""Coordinator for language server clients."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterable

import yaml

from PySide6.QtCore import QObject, Signal

from ghostline.core.config import ConfigManager
from ghostline.core.logging import LOG_FILE
from ghostline.lang.diagnostics import Diagnostic
from ghostline.lang.lsp_client import LSPClient
from ghostline.workspace.workspace_manager import WorkspaceManager
from ghostline.core.self_healing import SelfHealingService, HealthIssue

logger = logging.getLogger(__name__)


class LSPManager(QObject):
    """Manage language server lifecycles and route editor events."""

    lsp_error = Signal(str)
    lsp_notice = Signal(str)

    def __init__(self, config: ConfigManager, workspace_manager: WorkspaceManager, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.workspace_manager = workspace_manager
        self.clients: dict[str, dict[str, dict[str, LSPClient]]] = {}
        self._diag_callbacks: list[Callable[[list[Diagnostic]], None]] = []
        self._pending: dict[int, Callable[[dict], None]] = {}
        self._language_map = self._build_language_map()
        self._ensure_default_servers()
        self.self_healing = SelfHealingService(config, lambda: self.workspace_manager.current_workspace)

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

    def _role_definitions(self, language: str) -> dict[str, list[dict[str, Any]]]:
        servers_cfg = self.config.get("lsp", {}).get("servers", {})
        entry = servers_cfg.get(language) or {}
        if entry.get("command"):
            return {"primary": [entry]}
        role_map: dict[str, list[dict[str, Any]]] = {}
        for role in ("primary", "analyzers", "formatter"):
            value = entry.get(role)
            if not value:
                continue
            if isinstance(value, list):
                role_map[role] = value
            else:
                role_map[role] = [value]
        return role_map

    def _get_client(self, language: str, role: str = "primary") -> LSPClient | None:
        workspace = self.workspace_manager.current_workspace or str(Path(path := ".").resolve())
        lang_clients = self.clients.setdefault(workspace, {}).setdefault(language, {})
        if role in lang_clients:
            return lang_clients[role]
        role_defs = self._role_definitions(language)
        definitions = role_defs.get(role)
        if not definitions:
            logger.warning("No %s LSP server configured for %s", role, language)
            self.lsp_error.emit(f"No {role} LSP configured for {language}")
            return None
        cfg = definitions[0]
        command = [cfg.get("command")] + list(cfg.get("args", []))
        try:
            client = LSPClient(command, workdir=workspace)
        except FileNotFoundError:
            message = f"LSP server for {language} not found. Install: {cfg.get('command')}"
            logger.error(message)
            self.lsp_error.emit(message)
            return None
        self._register_client_hooks(language, workspace, role, client)
        client.notification_received.connect(self._handle_notification)
        client.response_received.connect(self._handle_response)
        client.start()
        lang_clients[role] = client
        self._initialize(client, workspace)
        return client

    def _register_client_hooks(self, language: str, workspace: str, role: str, client: LSPClient) -> None:
        def _handle_exit(_code, _status=None):
            logger.error("LSP server for %s (%s) exited unexpectedly in %s", language, role, workspace)
            self._notify_failure(language)
            self._drop_client(language, workspace, role)

        client.process.finished.connect(_handle_exit)
        client.process.errorOccurred.connect(lambda err: self._notify_failure(language, str(err)))

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

    def _drop_client(self, language: str, workspace: str, role: str) -> None:
        if workspace in self.clients and language in self.clients[workspace]:
            client = self.clients[workspace][language].pop(role, None)
            if client:
                client.stop()

    def restart_language_server(self, language: str) -> None:
        """Restart the language server for a specific language in the current workspace."""

        workspace = self.workspace_manager.current_workspace or str(Path(".").resolve())
        self._drop_client(language, workspace, "primary")
        self._notify_restart(language)
        self._get_client(language)

    def _notify_failure(self, language: str, error_detail: str | None = None) -> None:
        detail_hint = f" See log for details: {LOG_FILE}" if LOG_FILE else ""
        message = f"LSP server for {language} stopped.{detail_hint}"
        if error_detail:
            logger.error("LSP failure for %s: %s", language, error_detail)
        self.lsp_error.emit(message)
        if self.config.self_healing_enabled():
            self.self_healing.scan()

    def _notify_restart(self, language: str) -> None:
        self.lsp_notice.emit(f"Restarting {language} language server...")

    def _clients_for_language(self, language: str) -> list[LSPClient]:
        clients: list[LSPClient] = []
        for role in self._role_definitions(language).keys():
            client = self._get_client(language, role)
            if client:
                clients.append(client)
        return clients

    # Document events
    def open_document(self, path: str, text: str) -> None:
        language = self._language_for_file(path)
        if not language:
            return
        for client in self._clients_for_language(language):
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
        if not language:
            return
        for client in self._clients_for_language(language):
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
        if not language:
            return
        for client in self._clients_for_language(language):
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

