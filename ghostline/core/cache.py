"""Cache utilities for AI, LSP, and semantic layers."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


@dataclass
class CacheEntry:
    value: Any
    timestamp: float
    ttl: float | None = None

    def expired(self) -> bool:
        return self.ttl is not None and (time.time() - self.timestamp) > self.ttl


class CacheManager:
    """Simple in-memory cache with automatic cleanup of expired entries."""

    def __init__(self, auto_cleanup: bool = True, cleanup_interval: float = 300) -> None:
        """
        Initialize cache manager.

        Args:
            auto_cleanup: Whether to automatically cleanup expired entries
            cleanup_interval: How often to run cleanup (in seconds)
        """
        self._entries: Dict[str, CacheEntry] = {}
        self._cleanup_interval = cleanup_interval
        self._cleanup_thread: threading.Thread | None = None
        self._stop_cleanup = threading.Event()

        if auto_cleanup:
            self._start_cleanup_thread()

    def get(self, key: str, factory: Optional[Callable[[], Any]] = None, ttl: float | None = None) -> Any:
        entry = self._entries.get(key)
        if entry and not entry.expired():
            return entry.value
        if factory:
            value = factory()
            self.set(key, value, ttl=ttl)
            return value
        return None

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        self._entries[key] = CacheEntry(value, time.time(), ttl)

    def cleanup(self) -> None:
        """Manually cleanup expired entries."""
        to_remove = [key for key, entry in self._entries.items() if entry.expired()]
        for key in to_remove:
            self._entries.pop(key, None)

    def _start_cleanup_thread(self) -> None:
        """Start background thread for automatic cleanup."""
        def cleanup_worker() -> None:
            while not self._stop_cleanup.wait(self._cleanup_interval):
                self.cleanup()

        self._cleanup_thread = threading.Thread(
            target=cleanup_worker,
            daemon=True,
            name="CacheCleanup"
        )
        self._cleanup_thread.start()

    def shutdown(self) -> None:
        """Stop cleanup thread and clear cache."""
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=1)
        self._entries.clear()

    def __del__(self) -> None:
        """Ensure cleanup thread is stopped on garbage collection."""
        try:
            self.shutdown()
        except Exception:
            pass  # Ignore errors during cleanup in __del__


class FileSignatureCache(CacheManager):
    """Caches file signatures to avoid repeated hashing across systems."""

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root

    def signature(self, file_path: Path) -> str:
        stat = file_path.stat()
        key = str(file_path)
        cached = self.get(key)
        if cached:
            return cached
        signature = f"{stat.st_mtime}-{stat.st_size}"
        self.set(key, signature, ttl=60)
        return signature

