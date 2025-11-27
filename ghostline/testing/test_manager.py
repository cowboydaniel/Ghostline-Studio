"""Lightweight test runner integration."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from ghostline.semantic.query import SemanticQueryEngine


class TestManager:
    def __init__(self, task_manager, workspace_provider, semantic_query: SemanticQueryEngine | None = None) -> None:
        self.task_manager = task_manager
        self._workspace_provider = workspace_provider
        self.semantic_query = semantic_query

    def _workspace(self) -> Path | None:
        path = self._workspace_provider()
        return Path(path) if path else None

    def framework(self) -> str | None:
        workspace = self._workspace()
        if not workspace:
            return None
        if (workspace / "pytest.ini").exists() or shutil.which("pytest"):
            return "pytest"
        if shutil.which("python"):
            return "unittest"
        return None

    def run_all(self) -> None:
        self._run_command(self._build_command())

    def run_file(self, path: str) -> None:
        command = self._build_command(path)
        self._run_command(command)

    def run_relevant(self, changed: str) -> None:
        for test in self.relevant_tests([changed]):
            self.run_file(test)

    def relevant_tests(self, changes: Iterable[str]) -> list[str]:
        candidates: set[str] = set()
        workspace = self._workspace()
        if not workspace:
            return []
        for change in changes:
            path = Path(change)
            if "test" in path.name:
                candidates.add(str(path))
            if self.semantic_query:
                for node in self.semantic_query.find_usages(path.stem):
                    if node.file.name.startswith("test"):
                        candidates.add(str(node.file))
        if not candidates:
            for item in workspace.glob("tests/test_*.py"):
                candidates.add(str(item))
        return sorted(candidates)

    def run_coverage(self, target: str | None = None) -> None:
        workspace = self._workspace()
        target_arg = Path(target).name if target else ""
        command = f"coverage run -m pytest {target_arg}".strip()
        self._run_command(command)

    def _build_command(self, target: str | None = None) -> str:
        framework = self.framework() or "pytest"
        if framework == "pytest":
            return "pytest" if not target else f"pytest {Path(target).name}"
        return "python -m unittest discover"

    def _run_command(self, command: str) -> None:
        workspace = self._workspace()
        cwd = str(workspace) if workspace else ""
        self.task_manager.run_command("Tests", command, cwd=cwd)

