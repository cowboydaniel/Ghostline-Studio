"""AI client stubs."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Generator
from urllib import request
import json

from ghostline.core.config import ConfigManager
from ghostline.core.logging import get_logger
from ghostline.ai.prompt_builder import PromptBuilder


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
        self.api_key = ai_cfg.get("api_key")
        self.temperature = ai_cfg.get("temperature", 0.2)
        self.timeout = ai_cfg.get("request_timeout", 30)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post(self, url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=self._headers())
        with request.urlopen(req, timeout=self.timeout) as resp:  # type: ignore[arg-type]
            return json.loads(resp.read().decode("utf-8"))


class OllamaBackend(HTTPBackend):
    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        body = {"model": self.model or "codellama", "prompt": prompt, "stream": False}
        response = self._post(f"{self.endpoint}/api/generate", body)
        return AIResponse(text=response.get("response", ""))

    def stream(self, prompt: str, context: str | None = None) -> Generator[str, None, None]:
        yield self.send(prompt, context).text


class OpenAICompatibleBackend(HTTPBackend):
    def __init__(self, config: ConfigManager) -> None:
        super().__init__(config)
        ai_cfg = config.get("ai", {}) if config else {}
        self.endpoint = ai_cfg.get("openai_endpoint", "https://api.openai.com")

    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        messages = [{"role": "user", "content": prompt}]
        body = {
            "model": self.model or "gpt-4o-mini",
            "messages": messages,
            "stream": False,
            "temperature": self.temperature,
        }
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
        self.disabled = self.backend_type in {"none", "disabled"}
        self.backend = self._create_backend()
        self.secondary_backend_type = self.config.get("ai", {}).get("secondary_backend")
        self.secondary_backend = self._create_backend(self.secondary_backend_type) if self.secondary_backend_type else None

    def _create_backend(self, backend_type: str | None = None):
        backend = backend_type or self.backend_type
        if backend == "ollama":
            return OllamaBackend(self.config)
        if backend == "openai":
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

    def combined_send(self, prompt: str, builder: PromptBuilder, mode: str = "sequential") -> AIResponse:
        """Merge local+remote model context for richer reasoning."""

        built_prompt = builder.build(prompt, mode)
        primary = self.send(built_prompt)
        builder.update_last_response(primary.text)
        if not self.secondary_backend:
            return primary

        try:
            secondary_prompt = f"Follow-up based on primary response:\n{primary.text}\n\n{built_prompt}"
            secondary = self.secondary_backend.send(secondary_prompt)  # type: ignore[union-attr]
            combined = f"Primary: {primary.text}\nSecondary: {secondary.text}"
            return AIResponse(text=combined)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Secondary backend failure: %s", exc)
            return primary

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

