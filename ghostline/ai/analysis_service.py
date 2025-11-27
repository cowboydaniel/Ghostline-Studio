"""Background AI analysis service."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Iterable

from PySide6.QtCore import QObject, Signal

from ghostline.ai.ai_client import AIClient
from ghostline.core.threads import BackgroundWorkers

logger = logging.getLogger(__name__)


@dataclass
class AISuggestion:
    title: str
    detail: str
    severity: str = "info"
    source: str = "ai-analysis"


class AnalysisService(QObject):
    """Runs lightweight AI checks when files or diagnostics change."""

    suggestions_changed = Signal(list)

    def __init__(self, client: AIClient, workers: BackgroundWorkers | None = None, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self._workers = workers or BackgroundWorkers()
        self._suggestions: list[AISuggestion] = []

    def on_file_saved(self, path: str, content: str) -> None:
        self._enqueue(f"Review recent save for {path}", content)

    def on_workspace_changed(self, path: str) -> None:
        self._enqueue("Inspect workspace changes", path)

    def on_diagnostics(self, diagnostics: Iterable[dict]) -> None:
        joined = "\n".join([d.get("message", "") for d in diagnostics])
        if joined:
            self._enqueue("Review diagnostics", joined)

    def _enqueue(self, intent: str, context: str) -> None:
        logger.debug("AI analysis queued: %s", intent)
        self._workers.submit("analysis", lambda: self._run_query(intent, context))

    def _run_query(self, intent: str, context: str) -> None:
        prompt = f"Provide concise suggestions for the following event: {intent}. Limit to 3 bullet points.\n{context}"
        response = self.client.send(prompt)
        self._suggestions.append(AISuggestion(title=intent, detail=response.text))
        self.suggestions_changed.emit(self._suggestions.copy())

    def suggestions(self) -> list[AISuggestion]:
        return list(self._suggestions)

    def clear(self) -> None:
        self._suggestions.clear()
        self.suggestions_changed.emit([])
