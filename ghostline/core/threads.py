"""Threading helpers for background work."""
from __future__ import annotations

import concurrent.futures
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class BackgroundWorkers:
    """Shared thread pool for non-UI tasks."""

    def __init__(self, max_workers: int | None = None) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, concurrent.futures.Future] = {}

    def submit(self, key: str, func: Callable, *args, **kwargs) -> concurrent.futures.Future:
        self.cancel(key)
        future = self._executor.submit(func, *args, **kwargs)
        self._tasks[key] = future
        return future

    def cancel(self, key: str) -> None:
        future = self._tasks.pop(key, None)
        if future and not future.done():
            future.cancel()

    def shutdown(self) -> None:
        for key, future in list(self._tasks.items()):
            if not future.done():
                future.cancel()
            self._tasks.pop(key, None)
        self._executor.shutdown(wait=False)
