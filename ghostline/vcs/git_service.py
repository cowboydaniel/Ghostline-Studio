"""Git service providing advanced operations."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable

from ghostline.core.logging import get_logger

logger = get_logger(__name__)


class GitService:
    def __init__(self, workspace: str | None = None) -> None:
        self.workspace = Path(workspace) if workspace else None

    def _run(self, args: list[str]) -> str:
        cwd = str(self.workspace) if self.workspace else None
        try:
            result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            logger.debug("Git command failed: git %s (exit code %d): %s", " ".join(args), exc.returncode, exc.stderr)
            return ""
        except FileNotFoundError:
            logger.error("Git executable not found. Please ensure git is installed and in PATH.")
            return ""
        except Exception as exc:
            logger.error("Unexpected error running git command: %s", exc)
            return ""

    def set_workspace(self, workspace: Path | None) -> None:
        self.workspace = workspace

    def is_repo(self) -> bool:
        result = self._run(["rev-parse", "--is-inside-work-tree"])
        return result.strip().lower() == "true"

    def stash(self, message: str = "WIP") -> str:
        return self._run(["stash", "push", "-m", message])

    def apply_stash(self, ref: str = "stash@{0}") -> str:
        return self._run(["stash", "apply", ref])

    def drop_stash(self, ref: str = "stash@{0}") -> str:
        return self._run(["stash", "drop", ref])

    def history(self) -> list[str]:
        log = self._run(["log", "--oneline", "-n", "50"])
        return log.splitlines() if log else []

    def branches(self) -> list[str]:
        out = self._run(["branch", "--format", "%(refname:short)"])
        return out.splitlines() if out else []

    def graph(self) -> str:
        return self._run(["log", "--graph", "--oneline", "--decorate", "--all"])

    def diff_commit(self, ref: str) -> str:
        return self._run(["show", ref])

    def merge_conflicts(self) -> str:
        return self._run(["diff", "--name-only", "--diff-filter=U"])

    def create_branch(self, name: str, checkout: bool = False) -> str:
        """Create a branch if it does not exist and optionally check it out."""

        if name in self.branches():
            if checkout:
                self._run(["checkout", name])
            return name
        self._run(["branch", name])
        if checkout:
            self._run(["checkout", name])
        return name
