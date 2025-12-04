"""Context assembly for AI prompts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from ghostline.ai.workspace_memory import WorkspaceMemory
from ghostline.indexer.workspace_indexer import IndexedFile, WorkspaceIndexer
from ghostline.semantic.index_manager import SemanticIndexManager
from ghostline.search.symbol_search import SymbolSearcher


@dataclass
class ContextChunk:
    """A small, labelled unit of context sent to the AI backend."""

    title: str
    content: str
    source_path: Path | None = None
    reason: str = ""


class ContextEngine:
    """Collects contextual snippets for AI prompts."""

    def __init__(
        self,
        indexer: WorkspaceIndexer,
        semantic_index: SemanticIndexManager | None = None,
        symbol_searcher: SymbolSearcher | None = None,
        memory: WorkspaceMemory | None = None,
        *,
        max_snippet_chars: int = 800,
        max_results: int = 5,
    ) -> None:
        self.indexer = indexer
        self.semantic_index = semantic_index
        self.symbol_searcher = symbol_searcher
        self.memory = memory
        self.max_snippet_chars = max_snippet_chars
        self.max_results = max_results
        self._pinned: list[ContextChunk] = []
        self._cache_key: tuple[int, str] | None = None
        self._cached_context: tuple[str, list[ContextChunk]] | None = None

    def on_workspace_changed(self, root: Path | str | None) -> None:
        self._pinned.clear()
        self._cache_key = None
        self._cached_context = None
        self.indexer.set_workspace(root)

    def pin_context(self, chunk: ContextChunk) -> None:
        self._pinned.append(chunk)
        # Prevent runaway pinning
        self._pinned = self._pinned[-10:]

    def unpin(self, title: str) -> None:
        self._pinned = [chunk for chunk in self._pinned if chunk.title != title]

    def pinned(self) -> Sequence[ContextChunk]:
        return tuple(self._pinned)

    def build_context(
        self,
        prompt: str,
        *,
        instructions: str = "",
        active_document: tuple[Path | str, str] | None = None,
        open_documents: Iterable[tuple[Path | str | None, str]] | None = None,
    ) -> tuple[str, list[ContextChunk]]:
        cache_key = (self.indexer.generation, prompt + instructions)
        if cache_key == self._cache_key and self._cached_context:
            return self._cached_context

        chunks: list[ContextChunk] = []
        if instructions.strip():
            chunks.append(ContextChunk("Custom instructions", instructions.strip(), None, "User instruction"))

        chunks.extend(self._pinned)

        if active_document:
            active_path, text = active_document
            path_obj = Path(active_path) if active_path else None
            self.indexer.update_memory_snapshot(path_obj or "<active>", text)
            chunks.append(
                ContextChunk(
                    f"Active: {path_obj.name if path_obj else 'document'}",
                    text[: self.max_snippet_chars],
                    path_obj,
                    "Active editor",
                )
            )

        if open_documents:
            for other_path, text in list(open_documents)[:3]:
                if active_document and other_path == active_document[0]:
                    continue
                if text.strip():
                    path_obj = Path(other_path) if other_path else None
                    chunks.append(
                        ContextChunk(
                            f"Open: {path_obj.name if path_obj else 'Untitled'}",
                            text[: self.max_snippet_chars // 2],
                            path_obj,
                            "Open buffer",
                        )
                    )

        chunks.extend(self._mentions(prompt))
        chunks.extend(self._semantic_recent())
        chunks.extend(self._symbol_matches(prompt))
        chunks.extend(self._keyword_search(prompt))

        combined = self._format_chunks(chunks)
        self._cache_key = cache_key
        self._cached_context = (combined, chunks)
        return combined, chunks

    def _mentions(self, prompt: str) -> list[ContextChunk]:
        mentions = [token[1:] for token in prompt.split() if token.startswith("@") and len(token) > 1]
        chunks: list[ContextChunk] = []
        for mention in mentions:
            matches = self.indexer.find_by_name(mention, limit=2)
            for match in matches:
                chunks.append(self._chunk_from_indexed(match, f"Explicit mention @{mention}"))
        return chunks

    def _semantic_recent(self) -> list[ContextChunk]:
        if not self.semantic_index:
            return []
        results: list[ContextChunk] = []
        for path in self.semantic_index.recent_paths():
            indexed = self.indexer.get(path)
            if indexed:
                results.append(self._chunk_from_indexed(indexed, "Recent semantic change"))
        return results[: self.max_results]

    def _keyword_search(self, prompt: str) -> list[ContextChunk]:
        matches = self.indexer.search(prompt, limit=self.max_results)
        return [self._chunk_from_indexed(match, "Keyword match") for match in matches]

    def _symbol_matches(self, prompt: str) -> list[ContextChunk]:
        tokens = [token.strip(".,()") for token in prompt.split() if len(token) > 3]
        chunks: list[ContextChunk] = []
        seen_paths: set[Path] = set()

        for token in tokens:
            for indexed in self.indexer.symbols_for(token, limit=2):
                if indexed.path in seen_paths:
                    continue
                seen_paths.add(indexed.path)
                chunks.append(self._chunk_from_indexed(indexed, f"Symbol mention: {token}"))

        if self.semantic_index:
            for node in self.semantic_index.graph.nodes():
                if any(token.lower() in node.name.lower() for token in tokens):
                    indexed = self.indexer.get(node.file)
                    if indexed and indexed.path not in seen_paths:
                        seen_paths.add(indexed.path)
                        chunks.append(self._chunk_from_indexed(indexed, f"Semantic graph: {node.name}"))
        return chunks[: self.max_results]

    def _chunk_from_indexed(self, indexed: IndexedFile, reason: str) -> ContextChunk:
        return ContextChunk(
            title=indexed.path.name,
            content=indexed.snippet(self.max_snippet_chars),
            source_path=indexed.path,
            reason=reason,
        )

    def _format_chunks(self, chunks: Iterable[ContextChunk]) -> str:
        blocks = []
        if self.memory:
            memory_block = self.memory.as_prompt_context()
            if memory_block:
                blocks.append(f"[workspace-memory]\n{memory_block}")

        for chunk in chunks:
            header = f"[context: {chunk.title}]"
            if chunk.reason:
                header += f" ({chunk.reason})"
            body = chunk.content.strip()
            blocks.append(f"{header}\n{body}")
        return "\n\n".join(blocks)
