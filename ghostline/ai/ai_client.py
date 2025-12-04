"""AI client stubs."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Generator
from urllib import request
from urllib.error import URLError

from openai import OpenAI

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
        self.timeout = ai_cfg.get("timeout_seconds", 30)

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
        self.endpoint = ai_cfg.get("openai_endpoint", "https://api.openai.com").rstrip("/")
        client_config: dict[str, str] = {"base_url": self.endpoint}
        if self.api_key:
            client_config["api_key"] = self.api_key
        self.client = OpenAI(**client_config)

    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        text = "".join(self.stream(prompt, context))
        return AIResponse(text=text)

    def stream(self, prompt: str, context: str | None = None) -> Generator[str, None, None]:
        content = prompt if not context else f"[context]\n{context}\n\n{prompt}"
        stream = self.client.responses.create(
            model=self.model or "gpt-4o-mini",
            input=[{"role": "user", "content": [{"type": "text", "text": content}]}],
            temperature=self.temperature,
            stream=True,
        )

        for event in stream:
            if getattr(event, "type", "") == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    yield delta
            elif getattr(event, "type", "") == "response.output_text.done":
                text = getattr(event, "text", "")
                if text:
                    yield text


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
        self._ollama_started = False

    def _create_backend(self, backend_type: str | None = None):
        backend = backend_type or self.backend_type
        if backend == "ollama":
            return OllamaBackend(self.config)
        if backend == "openai":
            return OpenAICompatibleBackend(self.config)
        return DummyBackend(self.config)

    def _maybe_start_ollama(self) -> bool:
        if self.backend_type != "ollama" or self._ollama_started:
            return False

        self._ollama_started = True
        if not self.config.get("ai", {}).get("auto_start_ollama", True):
            return False

        if not shutil.which("ollama"):
            self.logger.warning("Ollama executable not found; skipping auto-start.")
            return False

        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            time.sleep(1)
            self.logger.info("Attempted to start Ollama server with `ollama serve`.")
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Failed to auto-start Ollama: %s", exc)
            return False

    def _retry_after_start(self, prompt: str, context: str | None = None) -> AIResponse | None:
        if not self._maybe_start_ollama():
            return None

        try:
            return self.backend.send(prompt, context)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("AI retry after Ollama start failed: %s", exc)
            return None

    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        if self.disabled:
            return AIResponse(text="AI backend disabled due to previous errors.")

        try:
            return self.backend.send(prompt, context)
        except TimeoutError:
            retry = self._retry_after_start(prompt, context)
            if retry:
                return retry

            timeout = getattr(self.backend, "timeout", None) or getattr(self.backend, "timeout_seconds", None)
            endpoint = getattr(self.backend, "endpoint", "the configured AI endpoint")
            timeout_hint = f" after {timeout} seconds" if timeout else ""
            message = (
                f"AI backend request to {endpoint} timed out"
                f"{timeout_hint}. Ensure your Ollama server is running (try `ollama serve`)"
                " and increase `ai.timeout_seconds` in settings if responses are slow."
            )
            self.logger.error(message)
            return AIResponse(text=message)
        except URLError as exc:
            retry = self._retry_after_start(prompt, context)
            if retry:
                return retry

            endpoint = getattr(self.backend, "endpoint", "the configured AI endpoint")
            message = (
                f"AI backend unreachable at {endpoint}."
                " Start your Ollama server (`ollama serve`) or update the AI endpoint in settings."
            )
            self.logger.error("AI backend connection failed: %s", exc)
            return AIResponse(text=message)
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

