"""Persistent project-level AI memory."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class WorkspaceMemory:
    """Store project-specific preferences and patterns for AI prompts."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self.data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                self.data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.data = {}

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def remember_pattern(self, category: str, value: str) -> None:
        bucket = self.data.setdefault(category, [])
        if value not in bucket:
            bucket.append(value)
            self._save()

    def forget_pattern(self, category: str, value: str) -> None:
        bucket = self.data.get(category, [])
        if value in bucket:
            bucket.remove(value)
            self._save()

    def snapshot(self) -> dict[str, Any]:
        return dict(self.data)

    def as_prompt_context(self) -> str:
        if not self.data:
            return ""
        lines = ["Workspace memory:"]
        for key, values in self.data.items():
            joined = ", ".join(values)
            lines.append(f"- {key}: {joined}")
        return "\n".join(lines)

    def append_event(self, category: str, payload: Any) -> None:
        """Record structured events for long-horizon planning."""

        bucket = self.data.setdefault(category, [])
        bucket.append(payload)
        self._save()

