"""Automated maintenance daemon for Ghostline Studio."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

from PySide6.QtCore import QObject, Signal

from ghostline.ai.ai_client import AIClient
from ghostline.core.threads import BackgroundWorkers
from ghostline.semantic.graph import SemanticGraph
from ghostline.semantic.index_manager import SemanticIndexManager
from ghostline.vcs.git_service import GitService


@dataclass
class MaintenanceAction:
    """Action proposed by the maintenance daemon."""

    title: str
    description: str
    files: list[Path] = field(default_factory=list)
    kind: str = "refactor"


@dataclass
class MaintenanceFinding:
    """Represents a detected issue in the repository."""

    label: str
    detail: str
    severity: str = "info"
    actions: list[MaintenanceAction] = field(default_factory=list)


class MaintenanceDaemon(QObject):
    """Periodically inspects the workspace for decay or drift."""

    findings_changed = Signal(list)

    def __init__(
        self,
        client: AIClient,
        index_manager: SemanticIndexManager,
        workspace_provider: Callable[[], str | None],
        git_service: GitService | None = None,
        workers: BackgroundWorkers | None = None,
    ) -> None:
        super().__init__()
        self.client = client
        self.index_manager = index_manager
        self.workspace_provider = workspace_provider
        self.git_service = git_service or GitService(workspace_provider())
        self.workers = workers or BackgroundWorkers()
        self.findings: list[MaintenanceFinding] = []
        self.last_scan_at: float = 0

    def trigger_idle_scan(self) -> None:
        self._scan(reason="idle")

    def on_file_saved(self, path: str) -> None:
        self._scan(reason=f"file_saved:{path}")

    def on_dependency_installed(self, package: str) -> None:
        self._scan(reason=f"dependency:{package}")

    def _scan(self, reason: str) -> None:
        now = time.time()
        if now - self.last_scan_at < 5:
            return
        self.last_scan_at = now
        self.workers.submit("maintenance-scan", lambda: self._run_scan(reason))

    def _run_scan(self, reason: str) -> None:
        workspace = self.workspace_provider()
        graph = self.index_manager.graph
        findings: list[MaintenanceFinding] = []
        findings.extend(self._detect_duplicates(graph))
        findings.extend(self._detect_architecture_anomalies(graph))
        findings.extend(self._detect_api_drift(graph))
        ai_context = self._build_context(reason)
        ai_response = self.client.send(
            "Provide 3 maintenance suggestions based on the current workspace state.",
            context=ai_context,
        )
        if ai_response.text:
            findings.append(
                MaintenanceFinding(
                    label="AI recommendations",
                    detail=ai_response.text,
                    severity="info",
                )
            )
        self.findings = findings
        self.findings_changed.emit(findings)

    def _detect_duplicates(self, graph: SemanticGraph) -> list[MaintenanceFinding]:
        findings: list[MaintenanceFinding] = []
        seen: dict[str, list[Path]] = {}
        for node in graph.nodes():
            seen.setdefault(node.name, []).append(node.file)
        for name, locations in seen.items():
            if len(locations) > 1:
                findings.append(
                    MaintenanceFinding(
                        label=f"Duplicate symbol: {name}",
                        detail="Symbol appears across multiple files; consider extraction.",
                        severity="warn",
                        actions=[
                            MaintenanceAction(
                                title="Propose module extraction",
                                description=f"Extract shared logic for {name}.",
                                files=list({Path(p) for p in locations}),
                                kind="module-extraction",
                            )
                        ],
                    )
                )
        return findings

    def _detect_architecture_anomalies(self, graph: SemanticGraph) -> list[MaintenanceFinding]:
        findings: list[MaintenanceFinding] = []
        for cycle in graph.find_cycles():
            label = " -> ".join(node.name for node in cycle)
            findings.append(
                MaintenanceFinding(
                    label=f"Cycle detected: {label}",
                    detail="Cyclic dependency may indicate architectural drift.",
                    severity="error",
                )
            )
        return findings

    def _detect_api_drift(self, graph: SemanticGraph) -> list[MaintenanceFinding]:
        findings: list[MaintenanceFinding] = []
        imports = graph.import_edges()
        for edge in imports:
            if edge.target.name.endswith(".deprecated"):
                findings.append(
                    MaintenanceFinding(
                        label=f"Deprecated import {edge.target.name}",
                        detail=f"{edge.source.name} still depends on deprecated API {edge.target.name}.",
                        severity="warn",
                        actions=[
                            MaintenanceAction(
                                title="Queue rename",
                                description=f"Replace {edge.target.name} usage.",
                                files=[edge.source.file],
                                kind="rename",
                            )
                        ],
                    )
                )
        return findings

    def _build_context(self, reason: str) -> str:
        workspace = self.workspace_provider() or "workspace"
        recent = ", ".join(str(p) for p in self.index_manager.recent_paths())
        return f"Workspace: {workspace}\nReason: {reason}\nRecent changes: {recent}"

    def propose_branch(self) -> str:
        """Create a dedicated maintenance branch if needed."""

        branch_name = "maintenance-ghostline"
        existing = self.git_service.branches()
        if branch_name in existing:
            return branch_name
        self.git_service.create_branch(branch_name)
        return branch_name

    def export_actions(self) -> List[MaintenanceAction]:
        actions: list[MaintenanceAction] = []
        for finding in self.findings:
            actions.extend(finding.actions)
        return actions
