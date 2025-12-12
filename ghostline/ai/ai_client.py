"""AI client stubs."""
from __future__ import annotations

import json
import socket
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Generator
from urllib import request
from urllib.error import HTTPError, URLError

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

    def on_file_opened(self, path: Path, text: str) -> None:
        """Handle file-open events without performing network I/O."""


class HTTPBackend:
    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        ai_cfg = config.get("ai", {}) if config else {}
        providers = ai_cfg.get("providers", {}) if ai_cfg else {}
        self.endpoint = ai_cfg.get("endpoint", "http://localhost:11434")
        self.model = ai_cfg.get("model", "")
        self.api_key = ai_cfg.get("api_key")
        self.temperature = ai_cfg.get("temperature", 0.2)
        # Default to None (no timeout) for AI generation which can take minutes
        # Users can set ai.timeout_seconds in config if they want a timeout
        self.timeout = ai_cfg.get("timeout_seconds")
        self._providers = providers

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post(self, url: str, payload: dict) -> dict:
        client = getattr(self, "_client", None)
        if client:
            return client._call_backend_sync(url, payload, headers=self._headers(), timeout=self.timeout)

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=self._headers())
        with request.urlopen(req, timeout=self.timeout) as resp:  # type: ignore[arg-type]
            return json.loads(resp.read().decode("utf-8"))

    def on_file_opened(self, path: Path, text: str) -> None:
        """Default hook for file-open events; subclasses may override."""


class OllamaBackend(HTTPBackend):
    def __init__(self, config: ConfigManager) -> None:
        super().__init__(config)
        ollama_cfg = self._providers.get("ollama", {}) if hasattr(self, "_providers") else {}
        default_host = self.endpoint or "http://localhost:11434"
        self.host = (ollama_cfg.get("host") or default_host).rstrip("/")
        self.endpoint = self.host
        self.model = self.model or ollama_cfg.get("default_model", "")

    def probe_server(self, timeout: float = 0.3) -> bool:
        """Quickly verify that the Ollama server is responding."""

        url = f"{self.host.rstrip('/')}/api/tags"
        req = request.Request(url, headers=self._headers())
        try:
            with request.urlopen(req, timeout=timeout) as resp:  # type: ignore[arg-type]
                return resp.status == 200
        except Exception:  # noqa: BLE001
            get_logger(__name__).debug("Ollama probe failed for %s", url, exc_info=True)
            return False

    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        body = {"model": self.model or "codellama", "prompt": prompt, "stream": False}
        base = self.host.rstrip("/")
        response = self._post(f"{base}/api/generate", body)
        return AIResponse(text=response.get("response", ""))

    def stream(self, prompt: str, context: str | None = None) -> Generator[str, None, None]:
        yield self.send(prompt, context).text

    def on_file_opened(self, path: Path, text: str) -> None:
        """Hook for file-open events dispatched from the AI client."""
        _ = (path, text)


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

    def on_file_opened(self, path: Path, text: str) -> None:
        """Hook for file-open events dispatched from the AI client."""
        _ = (path, text)


class ClaudeBackend(HTTPBackend):
    """Backend for Anthropic's Claude API using the Messages API format."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__(config)
        self.logger = get_logger(__name__)
        ai_cfg = config.get("ai", {}) if config else {}
        claude_cfg = self._providers.get("claude", {}) if hasattr(self, "_providers") else {}

        # Get API key from Claude config or fallback to ai.api_key
        self.api_key = claude_cfg.get("api_key") or ai_cfg.get("claude_api_key") or self.api_key

        # Set endpoint
        self.endpoint = "https://api.anthropic.com"

        # Get model - prefer Claude config, then last_used_model if it's a Claude model, then fallback
        self.model = claude_cfg.get("default_model") or ai_cfg.get("model", "")
        if not self.model or not self.model.startswith("claude"):
            # Get enabled models
            enabled = claude_cfg.get("enabled_models", [])
            if enabled:
                self.model = enabled[0]
            else:
                # Use the latest versioned Claude Sonnet 4.5 model (not -latest which is invalid)
                self.model = "claude-sonnet-4-5-20250929"

        # Log configuration for debugging
        has_api_key = bool(self.api_key)
        self.logger.info("[Claude] Initialized with model=%s, has_api_key=%s, endpoint=%s", self.model, has_api_key, self.endpoint)

    def _headers(self) -> dict[str, str]:
        """Return headers for Anthropic API requests."""
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def send(self, prompt: str, context: str | None = None) -> AIResponse:
        """Send a non-streaming request to Claude API."""
        # Check if API key is configured
        if not self.api_key:
            error_msg = "Claude API key not configured. Please set ai.providers.claude.api_key in your configuration."
            self.logger.error("[Claude] %s", error_msg)
            return AIResponse(text=error_msg)

        content = prompt if not context else f"[context]\n{context}\n\n{prompt}"

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": content}],
        }

        url = f"{self.endpoint}/v1/messages"

        try:
            data = json.dumps(payload).encode("utf-8")
            req = request.Request(url, data=data, headers=self._headers())

            with request.urlopen(req, timeout=self.timeout) as resp:
                response_data = json.loads(resp.read().decode("utf-8"))

            # Extract text from response
            text = self._extract_text_from_response(response_data)
            return AIResponse(text=text)

        except HTTPError as exc:
            # Read error response body for better debugging
            try:
                error_body = exc.read().decode("utf-8")
                error_data = json.loads(error_body)
                self.logger.error("[Claude] HTTP %s error: %s", exc.code, error_data)
            except Exception:
                self.logger.error("[Claude] HTTP %s error (could not read response body)", exc.code)
            self.logger.error("[Claude] Request payload: %s", json.dumps(payload, indent=2))
            raise
        except Exception as exc:
            self.logger.error("[Claude] Error in send: %s", exc)
            raise

    def stream(self, prompt: str, context: str | None = None) -> Generator[str, None, None]:
        """Send a streaming request to Claude API."""
        # Check if API key is configured
        if not self.api_key:
            error_msg = "Claude API key not configured. Please set ai.providers.claude.api_key in your configuration."
            self.logger.error("[Claude] %s", error_msg)
            yield error_msg
            return

        content = prompt if not context else f"[context]\n{context}\n\n{prompt}"

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": content}],
            "stream": True,
        }

        url = f"{self.endpoint}/v1/messages"

        try:
            data = json.dumps(payload).encode("utf-8")
            req = request.Request(url, data=data, headers=self._headers())

            with request.urlopen(req, timeout=self.timeout) as resp:
                # Read streaming response line by line
                for line in resp:
                    line_str = line.decode("utf-8").strip()

                    # Skip empty lines
                    if not line_str:
                        continue

                    # Parse Server-Sent Events format
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]  # Remove "data: " prefix

                        # Skip event type markers
                        if data_str in ["[DONE]", ""]:
                            continue

                        try:
                            event_data = json.loads(data_str)

                            # Handle different event types
                            event_type = event_data.get("type")

                            if event_type == "content_block_delta":
                                # Extract delta text from content block
                                delta = event_data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    if text:
                                        yield text

                            elif event_type == "message_delta":
                                # Handle message-level deltas if needed
                                delta = event_data.get("delta", {})
                                # Could extract additional info here if needed
                                pass

                        except json.JSONDecodeError:
                            self.logger.debug("[Claude] Failed to parse streaming event: %s", data_str)
                            continue

        except HTTPError as exc:
            # Read error response body for better debugging
            try:
                error_body = exc.read().decode("utf-8")
                error_data = json.loads(error_body)
                self.logger.error("[Claude] HTTP %s error in stream: %s", exc.code, error_data)
            except Exception:
                self.logger.error("[Claude] HTTP %s error in stream (could not read response body)", exc.code)
            self.logger.error("[Claude] Request payload: %s", json.dumps(payload, indent=2))
            raise
        except Exception as exc:
            self.logger.error("[Claude] Error in stream: %s", exc)
            raise

    def _extract_text_from_response(self, response_data: dict) -> str:
        """Extract text content from a Claude API response."""
        content = response_data.get("content", [])

        if not content:
            return ""

        # Content is a list of content blocks
        text_parts = []
        for block in content:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        return "".join(text_parts)

    def on_file_opened(self, path: Path, text: str) -> None:
        """Hook for file-open events dispatched from the AI client."""
        # Could implement context management here if needed
        _ = (path, text)


class AIClient:
    """Factory for AI backends. Currently provides dummy implementation."""

    def _call_backend_sync(
        self, url: str, payload: dict | None = None, *, headers: dict[str, str] | None = None, timeout: float | None = None
    ) -> dict:
        """Perform a synchronous backend call; the only place for blocking I/O."""

        data = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
        req = request.Request(url, data=data, headers=headers or {})
        with request.urlopen(req, timeout=timeout or None) as resp:  # type: ignore[arg-type]
            return json.loads(resp.read().decode("utf-8"))

    def call_backend_in_background(self, url: str, payload: dict | None, *, purpose: str = "") -> None:
        """Fire-and-forget wrapper for backend probes that must not block UI."""

        self.logger.info("Starting background AI backend warmup for %s (%s)", url, purpose)

        def worker() -> None:
            try:
                self._call_backend_sync(url, payload)
            except Exception:  # noqa: BLE001
                self.logger.exception("Background AI backend call failed (%s): %s", purpose, url)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _ollama_is_running(self, timeout: float = 0.3) -> bool:
        """Return True if Ollama is responding on the configured host."""

        backend = self.backends.get("ollama")
        probe = getattr(backend, "probe_server", None)
        if callable(probe):
            return bool(probe(timeout=timeout))

        try:
            base = self.settings.ollama_host.rstrip("/")
            with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as r:
                return r.status == 200
        except Exception:
            return False

    def _ensure_ollama_running(self, probe_timeout: float = 0.3, max_wait_seconds: float = 10.0) -> None:
        """Start Ollama only if it is not already running, and wait for readiness."""

        if self._ollama_is_running(timeout=probe_timeout):
            return  # Already running

        # Try launching the Ollama server
        try:
            self._ollama_process = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.logger.info("Started Ollama server with `ollama serve` (PID: %s).", self._ollama_process.pid)
        except Exception as exc:
            self.logger.error("Failed to start Ollama server: %s", exc)
            return

        # Wait up to 10 seconds for Ollama to become ready
        deadline = time.monotonic() + max_wait_seconds
        while time.monotonic() < deadline:
            if self._ollama_is_running(timeout=probe_timeout):
                self.logger.info("Ollama server is now ready.")
                return
            time.sleep(0.2)

        self.logger.error("Ollama did not become ready within timeout.")

    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        self.logger = get_logger(__name__)
        self._http_error_counts: dict[str, int] = {}
        self._ollama_process: subprocess.Popen | None = None
        ai_settings = self.config.get("ai", {}) if self.config else {}
        providers = ai_settings.get("providers", {}) if ai_settings else {}
        self.settings = SimpleNamespace(allow_openai=bool(ai_settings.get("allow_openai", True)))
        self.settings.ollama_host = (
            providers.get("ollama", {}).get("host")
            or ai_settings.get("endpoint")
            or "http://localhost:11434"
        ).rstrip("/")
        self.settings.timeout_seconds = ai_settings.get("timeout_seconds", 30)
        self.backend_type = self.config.get("ai", {}).get("backend", "dummy")
        self.disabled = self.backend_type in {"none", "disabled"}
        self._backends: dict[str, object] = {}
        self.backend = self._create_backend()
        self.secondary_backend_type = self.config.get("ai", {}).get("secondary_backend")
        self.secondary_backend = self._create_backend(self.secondary_backend_type) if self.secondary_backend_type else None
        self.active_model: ModelDescriptor | None = None
        openai_models = ai_settings.get("providers", {}).get("openai", {}).get("enabled_models", []) or []
        claude_models = ai_settings.get("providers", {}).get("claude", {}).get("enabled_models", []) or []
        self.backends = {
            "ollama": self._create_backend("ollama"),
            "openai": self._create_backend("openai"),
            "claude": self._create_backend("claude"),
            "openai_models": [model.lower() for model in openai_models],
            "claude_models": [model.lower() for model in claude_models],
        }

    def _create_backend(self, backend_type: str | None = None):
        backend = backend_type or self.backend_type
        if backend in self._backends:
            return self._backends[backend]
        if backend == "ollama":
            instance = OllamaBackend(self.config)
        elif backend == "openai":
            instance = OpenAICompatibleBackend(self.config)
        elif backend == "claude":
            instance = ClaudeBackend(self.config)
        else:
            instance = DummyBackend(self.config)
        setattr(instance, "name", backend)
        setattr(instance, "_client", self)
        self._backends[backend] = instance
        return instance

    def _get_backend_for_model(self, model_name: str):
        """Return the correct backend and never fall back to OpenAI."""
        model_name = (model_name or "").lower()

        # Detect Claude models
        if model_name.startswith("claude"):
            return self.backends["claude"]

        # Detect Ollama models
        if model_name.startswith("ollama:") or "ollama" in model_name:
            return self.backends["ollama"]

        # Detect OpenAI models
        if model_name in self.backends.get("openai_models", []):
            return self.backends["openai"]

        # If we don't recognise the model, assume Ollama rather than OpenAI
        return self.backends["ollama"]

    def _backend_for_model(self, model: ModelDescriptor | None):
        ai_settings = self.config.get("ai", {}) if self.config else {}
        model_name = (
            model.id
            if model
            else (self.active_model.id if self.active_model else ai_settings.get("model", ""))
        )
        backend = self._get_backend_for_model(model_name)
        backend_type = getattr(backend, "name", self.backend_type)
        if model and hasattr(backend, "model"):
            backend.model = model.id  # type: ignore[attr-defined]
        return backend, backend_type

    def _ensure_backend_sync(self, backend_type: str | None, probe_timeout: float) -> None:
        if backend_type == "ollama":
            self._ensure_ollama_running(probe_timeout=probe_timeout)

    def ensure_backend_for_user_action(self, backend_type: str | None = None) -> None:
        """Allow explicit user actions to perform a blocking backend warmup."""

        target = backend_type or getattr(self.backend, "name", self.backend_type)
        probe_timeout = min(self.settings.timeout_seconds, 1.0)
        self._ensure_backend_sync(target, probe_timeout=probe_timeout)

    def ensure_backend_in_background(self, backend_type: str | None = None, probe_timeout: float = 0.3) -> None:
        """Warm up the backend asynchronously to avoid UI stalls."""

        target = backend_type or getattr(self.backend, "name", self.backend_type)
        thread = threading.Thread(
            target=self._ensure_backend_sync,
            kwargs={"backend_type": target, "probe_timeout": probe_timeout},
            daemon=True,
        )
        thread.start()

    def _friendly_http_error(self, backend: object, status: int) -> str:
        endpoint = getattr(backend, "endpoint", "the configured AI endpoint")
        if status == 404:
            hint = (
                "Check the `ai.endpoint` path (Ollama default: /api/generate) "
                "or OpenAI-style base URL ending with /v1, and verify the model name."
            )
            return f"AI backend at {endpoint} returned 404 (not found). {hint}"
        if status == 401:
            hint = "Verify your API key or token in settings for this endpoint."
            return f"AI backend at {endpoint} returned 401 (unauthorized). {hint}"
        return f"AI backend at {endpoint} returned HTTP {status}."

    def _record_http_error(self, backend: object, status: int) -> str | None:
        backend_name = getattr(backend, "name", None)
        if status not in {401, 404} or not backend_name or not isinstance(backend, HTTPBackend):
            return None

        count = self._http_error_counts.get(backend_name, 0) + 1
        self._http_error_counts[backend_name] = count

        if count > 1:
            endpoint = getattr(backend, "endpoint", "the configured AI endpoint")
            dummy = DummyBackend(self.config)
            setattr(dummy, "name", backend_name)
            self._backends[backend_name] = dummy
            self.logger.warning(
                "Switching AI backend '%s' to DummyBackend after repeated HTTP %s responses from %s.",
                backend_name,
                status,
                endpoint,
            )
            return "Repeated authentication or routing failures detected; switched to the local echo fallback for this session."
        return None

    def send(self, prompt: str, context: str | None = None, model: ModelDescriptor | None = None) -> AIResponse:
        if self.disabled:
            return AIResponse(text="AI backend disabled due to previous errors.")

        backend, _ = self._backend_for_model(model)
        if backend.name == "ollama":
            self.ensure_backend_for_user_action(backend_type="ollama")
        self.active_model = model or self.active_model
        try:
            return backend.send(prompt, context)
        except HTTPError as exc:
            message = self._friendly_http_error(backend, getattr(exc, "code", 0))
            fallback_note = self._record_http_error(backend, getattr(exc, "code", 0))
            if fallback_note:
                message = f"{message} {fallback_note}"
            self.logger.error("HTTP error from AI backend: %s", exc)
            return AIResponse(text=message)
        except TimeoutError:
            timeout = getattr(backend, "timeout", None) or getattr(backend, "timeout_seconds", None)
            endpoint = getattr(backend, "endpoint", "the configured AI endpoint")
            timeout_hint = f" after {timeout} seconds" if timeout else ""
            message = (
                f"AI backend request to {endpoint} timed out{timeout_hint}. "
                "Set `ai.timeout_seconds` in settings to increase timeout (default: no timeout)."
            )
            self.logger.error(message)
            return AIResponse(text=message)
        except URLError as exc:
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
        backend, _ = self._backend_for_model(model)
        self.active_model = model or self.active_model
        if backend.name == "ollama":
            self.ensure_backend_for_user_action(backend_type="ollama")
        if backend.name == "openai" and not self.settings.allow_openai:
            raise RuntimeError("OpenAI backend disabled, refusing to send API requests.")
        try:
            if hasattr(backend, "stream"):
                yield from backend.stream(prompt, context)
                return
            yield self.send(prompt, context, model=model).text
        except HTTPError as exc:
            message = self._friendly_http_error(backend, getattr(exc, "code", 0))
            fallback_note = self._record_http_error(backend, getattr(exc, "code", 0))
            if fallback_note:
                message = f"{message} {fallback_note}"
            self.logger.error("HTTP error during AI streaming: %s", exc)
            yield message
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("AI streaming failure: %s", exc)
            self.disabled = True
            yield "AI backend unavailable. Check logs for details."

    def on_file_opened(self, path: Path, text: str) -> None:
        """Public entry called from the UI thread when a file is opened."""
        if self.disabled:
            return

        backend, backend_type = self._backend_for_model(self.active_model)
        handler = getattr(backend, "on_file_opened", None)
        if not callable(handler):
            return

        if backend_type == "openai" and not self.settings.allow_openai:
            self.logger.info("OpenAI backend disabled; skipping file-open job for %s", path)
            return

        self.backend = backend
        if backend_type == "ollama":
            self.ensure_backend_in_background(backend_type="ollama", probe_timeout=0.3)
        self.logger.info(
            "Scheduling AI file-open job for %s with backend %s", path, backend_type or backend.__class__.__name__
        )
        thread = threading.Thread(
            target=self._run_file_opened_job,
            args=(backend, Path(path), text),
            daemon=True,
        )
        thread.start()

    def _run_file_opened_job(self, backend: object, path: Path, text: str) -> None:
        self.logger.info("Starting AI file-open job for %s", path)
        try:
            handler = getattr(backend, "on_file_opened", None)
            if callable(handler):
                handler(path, text)
        except Exception:
            self.logger.exception("Error running AI file-open job for %s", path)
        finally:
            self.logger.info("Completed AI file-open job for %s", path)

