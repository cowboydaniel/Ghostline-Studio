"""Threading helpers for background work."""
from __future__ import annotations

import concurrent.futures
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

SHUTTING_DOWN = False

logger = logging.getLogger(__name__)


class BackgroundWorkers:
    """Shared thread pool for non-UI tasks."""

    def __init__(self, max_workers: int | None = None) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, concurrent.futures.Future] = {}

    def submit(self, key: str, func: Callable, *args, **kwargs) -> concurrent.futures.Future:
        global SHUTTING_DOWN
        if SHUTTING_DOWN:
            return None  # type: ignore[return-value]
        self.cancel(key)
        try:
            future = self._executor.submit(func, *args, **kwargs)
        except RuntimeError:
            return None  # type: ignore[return-value]
        self._tasks[key] = future
        return future

    def cancel(self, key: str) -> None:
        future = self._tasks.pop(key, None)
        if future and not future.done():
            future.cancel()

    def shutdown(self, wait: bool = False) -> None:
        global SHUTTING_DOWN
        SHUTTING_DOWN = True
        for key, future in list(self._tasks.items()):
            if not future.done():
                future.cancel()
            self._tasks.pop(key, None)
        try:
            self._executor.shutdown(wait=wait, cancel_futures=True)
        except TypeError:
            self._executor.shutdown(wait=wait)


class WorkerPool:
    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def shutdown(self, wait: bool = False):
        """Mark the pool as shutting down and stop accepting new work."""
        global SHUTTING_DOWN
        SHUTTING_DOWN = True
        try:
            self._executor.shutdown(wait=wait, cancel_futures=True)
        except TypeError:
            # Python < 3.9 does not support cancel_futures, ignore
            self._executor.shutdown(wait=wait)

    def submit(self, name: str, func, *args, **kwargs):
        global SHUTTING_DOWN
        if SHUTTING_DOWN:
            return None
        try:
            return self._executor.submit(func, *args, **kwargs)
        except RuntimeError:
            return None
