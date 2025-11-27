"""Cache utilities for AI, LSP, and semantic layers."""
from __future__ import annotations

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
    """Simple in-memory cache with optional persistence hooks."""

    def __init__(self) -> None:
        self._entries: Dict[str, CacheEntry] = {}

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
        to_remove = [key for key, entry in self._entries.items() if entry.expired()]
        for key in to_remove:
            self._entries.pop(key, None)


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

