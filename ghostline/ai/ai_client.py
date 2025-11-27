"""AI client stubs."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Generator
from urllib import error, request

from ghostline.core.config import ConfigManager
from ghostline.core.logging import get_logger


@dataclass
class AIResponse:
    text: str


class DummyBackend:
    def __init__(self, _config: ConfigManager) -> None:
        pass

    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        decorated = prompt if not context else f"[context]\n{context}\n\n{prompt}"
        return AIResponse(text=f"Echo: {decorated}")

    def stream(self, prompt: str, context: str | None = None) -> Generator[str, None, None]:
        yield self.send(prompt, context).text


class HTTPBackend:
    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        ai_cfg = config.get("ai", {}) if config else {}
        self.endpoint = ai_cfg.get("endpoint", "http://localhost:11434")
        self.model = ai_cfg.get("model", "")

    def _post(self, url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=10) as resp:  # type: ignore[arg-type]
            return json.loads(resp.read().decode("utf-8"))


class OllamaBackend(HTTPBackend):
    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        body = {"model": self.model or "codellama", "prompt": prompt, "stream": False}
        response = self._post(f"{self.endpoint}/api/generate", body)
        return AIResponse(text=response.get("response", ""))

    def stream(self, prompt: str, context: str | None = None) -> Generator[str, None, None]:
        yield self.send(prompt, context).text


class OpenAICompatibleBackend(HTTPBackend):
    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        messages = [{"role": "user", "content": prompt}]
        body = {"model": self.model or "gpt-4o-mini", "messages": messages, "stream": False}
        response = self._post(f"{self.endpoint}/v1/chat/completions", body)
        choices = response.get("choices", [])
        text = choices[0]["message"]["content"] if choices else ""
        return AIResponse(text=text)

    def stream(self, prompt: str, context: str | None = None) -> Generator[str, None, None]:
        yield self.send(prompt, context).text


class AIClient:
    """Factory for AI backends. Currently provides dummy implementation."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        self.logger = get_logger(__name__)
        self.backend_type = self.config.get("ai", {}).get("backend", "dummy")
        self.backend = self._create_backend()
        self.disabled = False

    def _create_backend(self):
        if self.backend_type == "ollama":
            return OllamaBackend(self.config)
        if self.backend_type == "openai":
            return OpenAICompatibleBackend(self.config)
        return DummyBackend(self.config)

    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        if self.disabled:
            return AIResponse(text="AI backend disabled due to previous errors.")

        try:
            return self.backend.send(prompt, context)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("AI backend failure: %s", exc)
            self.disabled = True
            return AIResponse(text="AI backend unavailable. Check logs for details.")

    def stream(self, prompt: str, context: str | None = None):
        if self.disabled:
            yield "AI backend disabled due to previous errors."
            return
        try:
            if hasattr(self.backend, "stream"):
                yield from self.backend.stream(prompt, context)
                return
            yield self.send(prompt, context).text
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("AI streaming failure: %s", exc)
            self.disabled = True
            yield "AI backend unavailable. Check logs for details."

