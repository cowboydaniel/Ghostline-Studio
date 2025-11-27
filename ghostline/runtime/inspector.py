"""Runtime inspector capturing live execution data."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from time import time
from typing import Callable

from PySide6.QtCore import QObject, Signal

from ghostline.semantic.graph import SemanticGraph


@dataclass
class RuntimeObservation:
    timestamp: float
    path: str
    calls: list[str] = field(default_factory=list)
    memory_usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None


class RuntimeInspector(QObject):
    """Listen to runtime events and merge them into the semantic graph."""

    observation_added = Signal(RuntimeObservation)

    def __init__(self, graph: SemanticGraph, parent=None) -> None:
        super().__init__(parent)
        self.graph = graph
        self._lock = threading.Lock()
        self._observations: list[RuntimeObservation] = []

    def record_call_path(self, path: str, calls: list[str]) -> None:
        observation = RuntimeObservation(timestamp=time(), path=path, calls=calls)
        self._store(observation)

    def record_exception(self, path: str, message: str) -> None:
        observation = RuntimeObservation(timestamp=time(), path=path, error=message)
        self._store(observation)

    def record_memory(self, path: str, usage: dict[str, int]) -> None:
        observation = RuntimeObservation(timestamp=time(), path=path, memory_usage=usage)
        self._store(observation)

    def _store(self, observation: RuntimeObservation) -> None:
        with self._lock:
            self._observations.append(observation)
        self.graph.annotate_runtime(observation)
        self.observation_added.emit(observation)

    def recent(self) -> list[RuntimeObservation]:
        with self._lock:
            return list(self._observations[-20:])
