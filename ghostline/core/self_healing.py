"""Detect and repair broken tooling setups."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

from PySide6.QtCore import QObject, Signal

from ghostline.core.config import ConfigManager


@dataclass
class HealthIssue:
    title: str
    detail: str
    severity: str = "warn"
    suggested_fix: str = ""


class SelfHealingService(QObject):
    """Minimal detector for missing tools and inconsistent configs."""

    issues_changed = Signal(list)

    def __init__(self, config: ConfigManager, workspace_provider: Callable[[], str | None]) -> None:
        super().__init__()
        self.config = config
        self.workspace_provider = workspace_provider
        self.issues: list[HealthIssue] = []

    def scan(self) -> None:
        self.issues = []
        self._check_virtualenv()
        self._check_formatter_settings()
        self._check_lsp_servers()
        self.issues_changed.emit(self.issues)

    def _check_virtualenv(self) -> None:
        workspace = self.workspace_provider()
        if workspace and not (Path(workspace) / ".venv").exists():
            self.issues.append(
                HealthIssue(
                    title="Missing virtual environment",
                    detail="No .venv detected. Create one to isolate dependencies.",
                    severity="info",
                    suggested_fix="python -m venv .venv",
                )
            )

    def _check_formatter_settings(self) -> None:
        formatter_cfg = self.config.get("formatter", {})
        if formatter_cfg and formatter_cfg.get("line_length", 0) <= 0:
            self.issues.append(
                HealthIssue(
                    title="Formatter misconfigured",
                    detail="Line length missing; using default 88.",
                    severity="warn",
                    suggested_fix="Set formatter.line_length in settings",
                )
            )

    def _check_lsp_servers(self) -> None:
        lsp_cfg = self.config.get("lsp", {})
        servers = lsp_cfg.get("servers", {})
        if not servers:
            self.issues.append(
                HealthIssue(
                    title="No LSP servers configured",
                    detail="Configure language servers to enable diagnostics.",
                    severity="error",
                    suggested_fix="Add entries under lsp.servers",
                )
            )

    def propose_repairs(self) -> list[str]:
        return [issue.suggested_fix for issue in self.issues if issue.suggested_fix]
