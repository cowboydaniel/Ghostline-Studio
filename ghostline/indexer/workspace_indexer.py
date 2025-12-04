"""Workspace-aware file indexing helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from ghostline.core.logging import get_logger
from ghostline.core.threads import BackgroundWorkers

logger = get_logger(__name__)


@dataclass
class IndexedFile:
    """In-memory representation of an indexed file."""

    path: Path
    content: str
    mtime: float

    def snippet(self, max_chars: int = 600) -> str:
        """Return a shortened preview of file contents."""

        return self.content[:max_chars]


class WorkspaceIndexer:
    """Indexes workspace files and provides lightweight retrieval APIs."""

    def __init__(
        self,
        workspace_provider: Callable[[], Path | str | None],
        *,
        workers: BackgroundWorkers | None = None,
        max_file_bytes: int = 400_000,
        include_hidden: bool = False,
    ) -> None:
        self.workspace_provider = workspace_provider
        self.workers = workers or BackgroundWorkers()
        self.max_file_bytes = max_file_bytes
        self.include_hidden = include_hidden
        self._files: dict[Path, IndexedFile] = {}
        self._memory_overrides: dict[Path, str] = {}
        self._recent: list[Path] = []
        self._symbol_index: dict[str, set[Path]] = {}
        self._generation = 0

    @property
    def generation(self) -> int:
        """Incrementing counter used to invalidate caches."""

        return self._generation

    def set_workspace(self, path: Path | str | None) -> None:
        self._files.clear()
        self._memory_overrides.clear()
        self._recent.clear()
        self._symbol_index.clear()
        self._generation += 1
        if path:
            self._schedule_index(Path(path))

    def _schedule_index(self, root: Path) -> None:
        if not root.exists():
            return
        self.workers.submit("workspace-index", self._index_path, root)

    def rebuild(self, paths: Iterable[str] | None = None) -> None:
        workspace = self.workspace_provider()
        if paths:
            for raw in paths:
                self.workers.submit(f"workspace-index:{raw}", self._index_path, Path(raw))
            return
        if workspace:
            self._schedule_index(Path(workspace))

    def _index_path(self, path: Path) -> None:
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    self._maybe_index_file(child)
        elif path.is_file():
            self._maybe_index_file(path)

    def _maybe_index_file(self, path: Path) -> None:
        if not self.include_hidden and any(part.startswith(".") for part in path.parts):
            return
        try:
            if path.stat().st_size > self.max_file_bytes:
                logger.debug("Skipping large file %s", path)
                return
        except OSError:
            return

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            logger.debug("Unable to read %s for indexing", path)
            return

        self._files[path] = IndexedFile(path, content, path.stat().st_mtime)
        self._generation += 1
        self._recent.append(path)
        self._recent = self._recent[-20:]
        self._index_symbols(path, content)

    def update_memory_snapshot(self, path: Path | str, content: str) -> None:
        """Store an in-memory version of a file (e.g., unsaved editor buffer)."""

        resolved = Path(path)
        self._memory_overrides[resolved] = content
        self._generation += 1
        if resolved not in self._recent:
            self._recent.append(resolved)
            self._recent = self._recent[-20:]
        self._index_symbols(resolved, content)

    def get(self, path: Path | str) -> IndexedFile | None:
        resolved = Path(path)
        if resolved in self._memory_overrides:
            return IndexedFile(resolved, self._memory_overrides[resolved], 0)
        return self._files.get(resolved)

    def find_by_name(self, term: str, limit: int = 5) -> list[IndexedFile]:
        term_lower = term.lower()
        matches = [
            file
            for file in self._files.values()
            if term_lower in file.path.name.lower() or term_lower in str(file.path).lower()
        ]
        return matches[:limit]

    def search(self, query: str, limit: int = 5) -> list[IndexedFile]:
        tokens = [token.lower() for token in query.split() if len(token) > 3]
        if not tokens:
            return []

        scored: list[tuple[int, IndexedFile]] = []
        for file in self._files.values():
            text = file.content.lower()
            score = sum(text.count(token) for token in tokens)
            if score:
                scored.append((score, file))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [file for _, file in scored[:limit]]

    def symbols_for(self, symbol: str, limit: int = 5) -> list[IndexedFile]:
        """Return files that define or import a given symbol."""

        paths = list(self._symbol_index.get(symbol.lower(), set()))[:limit]
        results: list[IndexedFile] = []
        for path in paths:
            indexed = self.get(path)
            if indexed:
                results.append(indexed)
        return results

    # Internal ---------------------------------------------------------
    def _index_symbols(self, path: Path, content: str) -> None:
        tokens = []
        for line in content.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("def ") or line_stripped.startswith("class "):
                name = line_stripped.split(" ", 1)[1].split("(", 1)[0].split(":", 1)[0]
                tokens.append(name)
            elif line_stripped.startswith("import ") or line_stripped.startswith("from "):
                parts = line_stripped.replace("from", "").replace("import", "").replace(",", " ").split()
                tokens.extend(parts)
        for token in tokens:
            key = token.lower()
            self._symbol_index.setdefault(key, set()).add(path)

    def recent_files(self) -> Sequence[Path]:
        return tuple(self._recent)

    def shutdown(self) -> None:
        self.workers.shutdown()
