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

from ghostline.ai.model_registry import ModelDescriptor
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
        providers = ai_cfg.get("providers", {}) if ai_cfg else {}
        self.endpoint = ai_cfg.get("endpoint", "http://localhost:11434")
        self.model = ai_cfg.get("model", "")
        self.api_key = ai_cfg.get("api_key")
        self.temperature = ai_cfg.get("temperature", 0.2)
        self.timeout = ai_cfg.get("timeout_seconds", 30)
        self._providers = providers

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
    def __init__(self, config: ConfigManager) -> None:
        super().__init__(config)
        ollama_cfg = self._providers.get("ollama", {}) if hasattr(self, "_providers") else {}
        self.endpoint = ollama_cfg.get("host", self.endpoint)
        self.model = self.model or ollama_cfg.get("default_model", "")

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
        openai_cfg = self._providers.get("openai", {}) if hasattr(self, "_providers") else {}
        self.endpoint = openai_cfg.get("base_url") or ai_cfg.get("openai_endpoint", "https://api.openai.com")
        self.endpoint = self.endpoint.rstrip("/")
        self.api_key = openai_cfg.get("api_key") or self.api_key
        if openai_cfg.get("enabled_models") and not self.model:
            self.model = openai_cfg.get("enabled_models", ["gpt-4.1"])[0]
        base_url = self.endpoint
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        client_config: dict[str, str] = {"base_url": base_url}
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
            input=[{"role": "user", "content": [{"type": "input_text", "text": content}]}],
            temperature=self.temperature,
            stream=True,
        )

        for event in stream:
            payload = self._extract_text_payload(event)
            if payload:
                yield payload

    @staticmethod
    def _extract_text_payload(event: object) -> str | None:
        """Normalize any textual payload from a Responses API streaming event."""

        def _extract(obj: object | None) -> str | None:
            if obj is None:
                return None
            if isinstance(obj, str):
                return obj
            if isinstance(obj, dict):
                for key in ("output_text", "delta", "data", "text"):
                    value = obj.get(key)
                    if value:
                        nested = _extract(value)
                        if nested:
                            return nested
                return None

            for key in ("output_text", "delta", "data", "text"):
                value = getattr(obj, key, None)
                if value:
                    nested = _extract(value)
                    if nested:
                        return nested

            return None

        return _extract(event)


class AIClient:
    """Factory for AI backends. Currently provides dummy implementation."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        self.logger = get_logger(__name__)
        self.backend_type = self.config.get("ai", {}).get("backend", "dummy")
        self.disabled = self.backend_type in {"none", "disabled"}
        self._backends: dict[str, object] = {}
        self.backend = self._create_backend()
        self.secondary_backend_type = self.config.get("ai", {}).get("secondary_backend")
        self.secondary_backend = self._create_backend(self.secondary_backend_type) if self.secondary_backend_type else None
        self._ollama_started = False
        self.active_model: ModelDescriptor | None = None

    def _create_backend(self, backend_type: str | None = None):
        backend = backend_type or self.backend_type
        if backend in self._backends:
            return self._backends[backend]
        if backend == "ollama":
            instance = OllamaBackend(self.config)
        elif backend == "openai":
            instance = OpenAICompatibleBackend(self.config)
        else:
            instance = DummyBackend(self.config)
        self._backends[backend] = instance
        return instance

    def _maybe_start_ollama(self, backend_type: str) -> bool:
        if backend_type != "ollama" or self._ollama_started:
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

    def _retry_after_start(
        self, backend_type: str, prompt: str, context: str | None = None
    ) -> AIResponse | None:
        if not self._maybe_start_ollama(backend_type):
            return None

        try:
            backend = self._create_backend(backend_type)
            return backend.send(prompt, context)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("AI retry after Ollama start failed: %s", exc)
            return None

    def _backend_for_model(self, model: ModelDescriptor | None):
        backend_type = self.backend_type
        if model:
            backend_type = model.provider
        backend = self._create_backend(backend_type)
        if model and hasattr(backend, "model"):
            backend.model = model.id  # type: ignore[attr-defined]
        return backend, backend_type

    def send(self, prompt: str, context: str | None = None, model: ModelDescriptor | None = None) -> AIResponse:
        if self.disabled:
            return AIResponse(text="AI backend disabled due to previous errors.")

        backend, backend_type = self._backend_for_model(model)
        self.active_model = model or self.active_model
        try:
            return backend.send(prompt, context)
        except TimeoutError:
            retry = self._retry_after_start(backend_type, prompt, context)
            if retry:
                return retry

            timeout = getattr(backend, "timeout", None) or getattr(backend, "timeout_seconds", None)
            endpoint = getattr(backend, "endpoint", "the configured AI endpoint")
            timeout_hint = f" after {timeout} seconds" if timeout else ""
            message = (
                f"AI backend request to {endpoint} timed out"
                f"{timeout_hint}. Ensure your Ollama server is running (try `ollama serve`)"
                " and increase `ai.timeout_seconds` in settings if responses are slow."
            )
            self.logger.error(message)
            return AIResponse(text=message)
        except URLError as exc:
            retry = self._retry_after_start(backend_type, prompt, context)
            if retry:
                return retry

            endpoint = getattr(backend, "endpoint", "the configured AI endpoint")
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

    def combined_send(
        self, prompt: str, builder: PromptBuilder, mode: str = "sequential", model: ModelDescriptor | None = None
    ) -> AIResponse:
        """Merge local+remote model context for richer reasoning."""

        built_prompt = builder.build(prompt, mode)
        primary = self.send(built_prompt, model=model)
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

    def stream(self, prompt: str, context: str | None = None, model: ModelDescriptor | None = None):
        if self.disabled:
            yield "AI backend disabled due to previous errors."
            return
        backend, backend_type = self._backend_for_model(model)
        self.active_model = model or self.active_model
        try:
            if hasattr(backend, "stream"):
                yield from backend.stream(prompt, context)
                return
            yield self.send(prompt, context, model=model).text
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("AI streaming failure: %s", exc)
            self.disabled = True
            yield "AI backend unavailable. Check logs for details."

