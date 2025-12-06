"""Coordinator for language server clients."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import urlparse, quote
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
        self._reported_failures: set[str] = set()
        self.self_healing = SelfHealingService(config, lambda: self.workspace_manager.current_workspace)
        self._shutting_down = False

    # Client management
    def _normalize_path(self, path):
        """Convert different path-like objects into an absolute path string.

        This deliberately avoids returning pathlib.Path objects, because on
        Python 3.12 we have seen recursion inside pathlib when dealing with
        Qt types and file: URIs.
        """
        try:
            if path is None:
                return None

            # Qt QUrl objects: use local file path
            if hasattr(path, "toLocalFile"):
                local = path.toLocalFile()
                if local:
                    return os.path.abspath(str(local))

            # os.PathLike / Path / plain string
            try:
                path_str = os.fspath(path)
            except TypeError:
                path_str = str(path)

            if not path_str:
                return None

            # Handle file: URIs such as file:/home/... or file:///home/...
            if isinstance(path_str, str) and path_str.startswith("file:"):
                parsed = urlparse(path_str)
                if parsed.scheme == "file" and parsed.path:
                    path_str = parsed.path

            return os.path.abspath(path_str)
        except Exception:
            # Do not log here to avoid recursive logging failures when
            # path / stack state is already corrupted.
            return None

    def _language_for_file(self, path):
        normalized = self._normalize_path(path)
        if not normalized:
            return None
        try:
            _, ext = os.path.splitext(normalized)
            suffix = ext.lower()
        except Exception:
            return None
        return self._language_map.get(suffix)

    def _uri_for_path(self, path):
        try:
            normalized = self._normalize_path(path)
            if not normalized:
                return None
            # Construct a POSIX-style file:// URI without using Path.as_uri
            return "file://" + quote(normalized, safe="/")
        except Exception:
            return None

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
            if entry.get("enabled", True) is False:
                return {}
            return {"primary": [entry]}
        role_map: dict[str, list[dict[str, Any]]] = {}
        for role in ("primary", "analyzers", "formatter"):
            value = entry.get(role)
            if not value:
                continue
            entries = value if isinstance(value, list) else [value]
            enabled_entries = [cfg for cfg in entries if cfg.get("enabled", True) is not False]
            if enabled_entries:
                role_map[role] = enabled_entries
        return role_map

    def _role_is_disabled(self, language: str, role: str) -> bool:
        entry = self.config.get("lsp", {}).get("servers", {}).get(language) or {}
        if entry.get("command") and role == "primary":
            return entry.get("enabled", True) is False
        role_value = entry.get(role)
        if not role_value:
            return False
        if isinstance(role_value, list):
            configs = [cfg for cfg in role_value if isinstance(cfg, dict)]
            return bool(configs) and all(cfg.get("enabled", True) is False for cfg in configs)
        if isinstance(role_value, dict):
            return role_value.get("enabled", True) is False
        return False

    def _command_for_language(self, language: str) -> str | None:
        entry = self.config.get("lsp", {}).get("servers", {}).get(language) or {}
        if entry.get("command"):
            return str(entry.get("command"))
        for role in ("primary", "formatter", "analyzers"):
            value = entry.get(role)
            if isinstance(value, list):
                for cfg in value:
                    command = cfg.get("command") if isinstance(cfg, dict) else None
                    if command:
                        return str(command)
            elif isinstance(value, dict):
                command = value.get("command")
                if command:
                    return str(command)
        return None

    def _get_client(self, language: str, role: str = "primary") -> LSPClient | None:
        workspace_path = self.workspace_manager.current_workspace or Path.cwd()
        workspace = str(workspace_path)
        lang_clients = self.clients.setdefault(workspace, {}).setdefault(language, {})
        if role in lang_clients:
            return lang_clients[role]
        role_defs = self._role_definitions(language)
        definitions = role_defs.get(role)
        if not definitions:
            if self._role_is_disabled(language, role):
                logger.info("%s LSP server for %s disabled via configuration", role, language)
                return None
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
            self._emit_failure_diagnostic(language)
            return None
        client.semantic_tokens_capable = False
        client.semantic_tokens_legend: list[str] = []
        self._register_client_hooks(language, workspace, role, client)
        client.notification_received.connect(self._handle_notification)
        client.response_received.connect(self._handle_response)
        client.start()
        lang_clients[role] = client
        self._reported_failures.discard(language)
        self._initialize(client, workspace)
        return client

    def _register_client_hooks(self, language: str, workspace: str, role: str, client: LSPClient) -> None:
        def _handle_exit(_code, _status=None):
            if getattr(self, "_shutting_down", False):
                return
            logger.error("LSP server for %s (%s) exited unexpectedly in %s", language, role, workspace)
            self._notify_failure(language)
            self._drop_client(language, workspace, role)

        def _on_proc_error(err, lang=language):
            if getattr(self, "_shutting_down", False):
                return
            self._notify_failure(lang, str(err))

        def _on_proc_finished(code, status):
            if getattr(self, "_shutting_down", False):
                return
            _handle_exit(code, status)

        client.process.finished.connect(_on_proc_finished)
        client.process.errorOccurred.connect(_on_proc_error)

    def _initialize(self, client: LSPClient, workspace: str) -> None:
        root_uri = Path(workspace).resolve().as_uri()
        request_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": root_uri,
                "capabilities": {},
                "workspaceFolders": [{"uri": root_uri, "name": Path(workspace).name}],
            },
        )

        def _handle_initialize(message: dict) -> None:
            result = message.get("result", {}) if isinstance(message, dict) else {}
            capabilities = result.get("capabilities", {}) if isinstance(result, dict) else {}
            self._configure_capabilities(client, capabilities)
            client.send_notification("initialized", {})

        self._pending[request_id] = _handle_initialize

    def _drop_client(self, language: str, workspace: str, role: str) -> None:
        if workspace in self.clients and language in self.clients[workspace]:
            client = self.clients[workspace][language].pop(role, None)
            if client:
                client.stop()

    def restart_language_server(self, language: str) -> None:
        """Restart the language server for a specific language in the current workspace."""

        workspace_path = self.workspace_manager.current_workspace or Path.cwd()
        workspace = str(workspace_path)
        self._drop_client(language, workspace, "primary")
        self._notify_restart(language)
        self._get_client(language)

    def shutdown(self):
        """Terminate all LSP clients and stop emitting diagnostics."""
        self._shutting_down = True
        for workspace, languages in list(self.clients.items()):
            for language, roles in list(languages.items()):
                for role, client in list(roles.items()):
                    try:
                        client.process.errorOccurred.disconnect()
                    except Exception:
                        pass
                    try:
                        client.process.finished.disconnect()
                    except Exception:
                        pass
                    try:
                        client.stop()
                    except Exception:
                        try:
                            client.process.kill()
                        except Exception:
                            pass
        self.clients.clear()

    def _notify_failure(self, language: str, error_detail: str | None = None) -> None:
        if getattr(self, "_shutting_down", False):
            return
        detail_hint = f" See log for details: {LOG_FILE}" if LOG_FILE else ""
        message = f"LSP server for {language} stopped.{detail_hint}"
        if error_detail:
            logger.error("LSP failure for %s: %s", language, error_detail)
        self.lsp_error.emit(message)
        self._emit_failure_diagnostic(language)
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
    def open_document(self, path: Any, text: str) -> None:
        normalized = self._normalize_path(path)
        if not normalized:
            return
        language = self._language_for_file(normalized)
        if not language:
            return
        uri = self._uri_for_path(normalized)
        if not uri:
            return
        for client in self._clients_for_language(language):
            client.send_notification(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": language,
                        "version": 1,
                        "text": text,
                    }
                },
            )

    def change_document(self, path: Any, text: str, version: int) -> None:
        normalized = self._normalize_path(path)
        if not normalized:
            return
        language = self._language_for_file(normalized)
        if not language:
            return
        uri = self._uri_for_path(normalized)
        if not uri:
            return
        for client in self._clients_for_language(language):
            client.send_notification(
                "textDocument/didChange",
                {
                    "textDocument": {
                        "uri": uri,
                        "version": version,
                    },
                    "contentChanges": [{"text": text}],
                },
            )

    def close_document(self, path: Any) -> None:
        normalized = self._normalize_path(path)
        if not normalized:
            return
        language = self._language_for_file(normalized)
        if not language:
            return
        uri = self._uri_for_path(normalized)
        if not uri:
            return
        for client in self._clients_for_language(language):
            client.send_notification(
                "textDocument/didClose",
                {"textDocument": {"uri": uri}},
            )

    # Feature requests
    def request_completions(self, path: Any, position: dict[str, int], callback: Callable[[dict], None] | None = None) -> int | None:
        normalized = self._normalize_path(path)
        if not normalized:
            return None
        language = self._language_for_file(normalized)
        client = self._get_client(language) if language else None
        if not client:
            return None
        uri = self._uri_for_path(normalized)
        if not uri:
            return None
        request_id = client.send_request(
            "textDocument/completion",
            {"textDocument": {"uri": uri}, "position": position},
        )
        if callback:
            self._pending[request_id] = callback
        return request_id

    def request_hover(self, path: Any, position: dict[str, int], callback: Callable[[dict], None] | None = None) -> int | None:
        normalized = self._normalize_path(path)
        if not normalized:
            return None
        language = self._language_for_file(normalized)
        client = self._get_client(language) if language else None
        if not client:
            return None
        uri = self._uri_for_path(normalized)
        if not uri:
            return None
        request_id = client.send_request(
            "textDocument/hover",
            {"textDocument": {"uri": uri}, "position": position},
        )
        if callback:
            self._pending[request_id] = callback
        return request_id

    def supports_semantic_tokens(self, path: Any) -> bool:
        """Return False to force the editor to use its local semantic token provider or none."""
        return False

    def request_semantic_tokens(
        self, path: Any, callback: Callable[[dict, list[str]], None] | None = None
    ) -> bool:
        normalized = self._normalize_path(path)
        if not normalized:
            return False
        language = self._language_for_file(normalized)
        client = self._get_client(language) if language else None
        if not (client and getattr(client, "semantic_tokens_capable", False)):
            return False
        uri = self._uri_for_path(normalized)
        if not uri:
            return False
        request_id = client.send_request(
            "textDocument/semanticTokens/full",
            {"textDocument": {"uri": uri}},
        )
        if callback:
            legend = getattr(client, "semantic_tokens_legend", [])
            self._pending[request_id] = lambda message: callback(message.get("result", {}), legend)
        return True

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

    def _configure_capabilities(self, client: LSPClient, capabilities: dict[str, Any]) -> None:
        semantic_provider = capabilities.get("semanticTokensProvider") if isinstance(capabilities, dict) else None
        legend: list[str] = []
        if isinstance(semantic_provider, dict):
            if isinstance(semantic_provider.get("legend"), dict):
                legend = list(semantic_provider.get("legend", {}).get("tokenTypes", []))
            elif isinstance(semantic_provider.get("legend"), list):
                legend = list(semantic_provider.get("legend", []))
        client.semantic_tokens_legend = legend
        client.semantic_tokens_capable = bool(legend)

    def _emit_failure_diagnostic(self, language: str) -> None:
        if getattr(self, "_shutting_down", False):
            return
        if language in self._reported_failures:
            return
        command = self._command_for_language(language) or "the configured language server"
        message = f"{language.capitalize()} language server failed to start. Check that {command} is installed and configured."
        diagnostic = Diagnostic(file="(LSP)", line=0, col=0, severity="Warning", message=message)
        for callback in self._diag_callbacks:
            callback([diagnostic])
        self._reported_failures.add(language)

