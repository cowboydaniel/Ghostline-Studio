"""AI client stubs."""
from __future__ import annotations

from dataclasses import dataclass

from ghostline.core.config import ConfigManager


@dataclass
class AIResponse:
    text: str


class DummyBackend:
    def __init__(self, _config: ConfigManager) -> None:
        pass

    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        decorated = prompt if not context else f"[context]\n{context}\n\n{prompt}"
        return AIResponse(text=f"Echo: {decorated}")


class AIClient:
    """Factory for AI backends. Currently provides dummy implementation."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        self.backend_type = self.config.get("ai", {}).get("backend", "dummy")
        self.backend = self._create_backend()

    def _create_backend(self):
        return DummyBackend(self.config)

    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        return self.backend.send(prompt, context)

