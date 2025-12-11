"""Model registry and discovery helpers for Ghostline AI."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any
from urllib import request

from ghostline.core.logging import get_logger


@dataclass
class ModelDescriptor:
    """Description of an AI model exposed in the UI."""

    id: str
    label: str
    provider: str
    kind: str = "code"
    enabled: bool = True
    description: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ModelDescriptor":
        return cls(
            id=payload.get("id", ""),
            label=payload.get("label") or payload.get("id", ""),
            provider=payload.get("provider", "openai"),
            kind=payload.get("kind", "code"),
            enabled=bool(payload.get("enabled", True)),
            description=payload.get("description"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "provider": self.provider,
            "kind": self.kind,
            "enabled": self.enabled,
            "description": self.description,
        }


def default_openai_models() -> list[ModelDescriptor]:
    """Curated OpenAI models recommended for coding."""

    return [
        ModelDescriptor("gpt-5.1", "GPT-5.1", "openai", "code", True, "Best for coding and agentic tasks"),
        ModelDescriptor("gpt-5.1-mini", "GPT-5.1 mini", "openai", "code", True, "Fast, lower cost"),
        ModelDescriptor("gpt-4.1", "GPT-4.1", "openai", "code", True, "Balanced coding model"),
        ModelDescriptor("gpt-4.1-mini", "GPT-4.1 mini", "openai", "code", True, "Speed focused"),
        ModelDescriptor("gpt-4.1-nano", "GPT-4.1 nano", "openai", "code", True, "Lightweight tasks"),
    ]


class OllamaModelDiscovery:
    """Discover installed Ollama models without impacting the UI."""

    def __init__(self, host: str = "http://localhost:11434", timeout: int = 5) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.logger = get_logger(__name__)

    def discover(self) -> list[ModelDescriptor]:
        models = self._discover_via_http()
        if models:
            return models

        models = self._discover_via_cli()
        if models:
            return models

        self.logger.warning("No Ollama models discovered; falling back to cloud providers only.")
        return []

    def _discover_via_http(self) -> list[ModelDescriptor]:
        url = f"{self.host}/api/tags"
        try:
            with request.urlopen(url, timeout=self.timeout) as resp:  # type: ignore[arg-type]
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Ollama HTTP discovery failed: %s", exc)
            return []

        models: list[ModelDescriptor] = []
        for item in payload.get("models", []) or payload.get("tags", []):
            name = item.get("name")
            if not name:
                continue
            models.append(ModelDescriptor(name, name, "ollama", "code", True))
        return models

    def _discover_via_cli(self) -> list[ModelDescriptor]:
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError:
            self.logger.debug("ollama CLI not found; skipping CLI discovery.")
            return []
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Ollama CLI discovery failed: %s", exc)
            return []

        if result.returncode != 0:
            self.logger.warning("Ollama CLI returned error: %s", result.stderr.strip())
            return []

        models: list[ModelDescriptor] = []
        stdout = result.stdout.strip()
        if stdout.startswith("["):
            try:
                payload = json.loads(stdout)
                for item in payload:
                    name = item.get("name")
                    if name:
                        models.append(ModelDescriptor(name, name, "ollama", "code", True))
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                self.logger.debug("Unable to parse ollama list JSON: %s", exc)
                return []
        else:
            for line in stdout.splitlines():
                if not line.strip():
                    continue
                models.append(ModelDescriptor(line.split()[0], line.split()[0], "ollama", "code", True))

        return models


class ModelRegistry:
    """Central source of available AI models and provider settings."""

    def __init__(self, config, discovery: OllamaModelDiscovery | None = None) -> None:
        from ghostline.core.config import ConfigManager  # Local import to avoid cycles

        self.config: ConfigManager = config
        self.discovery = discovery or OllamaModelDiscovery(
            host=self._ollama_settings().get("host", "http://localhost:11434")
        )
        self.logger = get_logger(__name__)
        self._ensure_defaults()

    def _ai_settings(self) -> dict[str, Any]:
        return self.config.settings.setdefault("ai", {})

    def _provider_settings(self) -> dict[str, Any]:
        return self._ai_settings().setdefault("providers", {})

    def _openai_settings(self) -> dict[str, Any]:
        return self._provider_settings().setdefault("openai", {})

    def _ollama_settings(self) -> dict[str, Any]:
        return self._provider_settings().setdefault("ollama", {})

    def _claude_settings(self) -> dict[str, Any]:
        return self._provider_settings().setdefault("claude", {})

    def _ensure_defaults(self) -> None:
        openai_cfg = self._openai_settings()
        if not openai_cfg.get("available_models"):
            openai_cfg["available_models"] = [model.to_dict() for model in default_openai_models()]
        if "enabled_models" not in openai_cfg:
            openai_cfg["enabled_models"] = [model["id"] for model in openai_cfg["available_models"] if model.get("enabled", True)]
        if "base_url" not in openai_cfg:
            openai_cfg["base_url"] = self._ai_settings().get("openai_endpoint", "https://api.openai.com")
        if "api_key" not in openai_cfg:
            openai_cfg["api_key"] = self._ai_settings().get("api_key", "")

        ollama_cfg = self._ollama_settings()
        if "host" not in ollama_cfg:
            ollama_cfg["host"] = self._ai_settings().get("endpoint", "http://localhost:11434")
        ollama_cfg.setdefault("enabled", True)
        ollama_cfg.setdefault("last_seen_models", [])

        claude_cfg = self._claude_settings()
        if "api_key" not in claude_cfg:
            claude_cfg["api_key"] = self._ai_settings().get("claude_api_key", "")
        if "enabled_models" not in claude_cfg:
            claude_cfg["enabled_models"] = ["claude-3-5-sonnet-latest"]
        if "default_model" not in claude_cfg:
            claude_cfg["default_model"] = "claude-3-5-sonnet-latest"

    def openai_models(self) -> list[ModelDescriptor]:
        cfg = self._openai_settings()
        enabled_ids = set(cfg.get("enabled_models", []))
        models = [ModelDescriptor.from_dict(m) for m in cfg.get("available_models", [])]
        for model in models:
            model.enabled = model.id in enabled_ids and model.enabled
        return models

    def enabled_openai_models(self) -> list[ModelDescriptor]:
        return [model for model in self.openai_models() if model.enabled]

    def ollama_models(self) -> list[ModelDescriptor]:
        if not self._ollama_settings().get("enabled", True):
            return []
        models = self.discovery.discover()
        self._ollama_settings()["last_seen_models"] = [model.id for model in models]
        return models

    def claude_models(self) -> list[ModelDescriptor]:
        """Return available Claude models."""
        cfg = self._claude_settings()
        enabled_ids = set(cfg.get("enabled_models", []))

        # Hardcoded list of Claude models
        all_claude_models = [
            ModelDescriptor("claude-3-5-sonnet-latest", "Claude 3.5 Sonnet", "claude", "code", True, "Fast, versatile model"),
            ModelDescriptor("claude-3-opus-latest", "Claude 3 Opus", "claude", "code", True, "Most capable model"),
            ModelDescriptor("claude-3-haiku-latest", "Claude 3 Haiku", "claude", "code", True, "Fastest model"),
        ]

        for model in all_claude_models:
            model.enabled = model.id in enabled_ids

        return all_claude_models

    def enabled_claude_models(self) -> list[ModelDescriptor]:
        """Return only enabled Claude models."""
        return [model for model in self.claude_models() if model.enabled]

    def available_models(self) -> list[ModelDescriptor]:
        return self.enabled_openai_models() + self.enabled_claude_models() + self.ollama_models()

    def set_enabled_openai_models(self, enabled_ids: list[str]) -> None:
        cfg = self._openai_settings()
        cfg["enabled_models"] = enabled_ids

    def last_used_model(self) -> ModelDescriptor | None:
        payload = self._ai_settings().get("last_used_model")
        if not payload:
            return None
        try:
            return ModelDescriptor.from_dict(payload)
        except Exception:  # noqa: BLE001
            return None

    def set_last_used_model(self, model: ModelDescriptor) -> None:
        self._ai_settings()["last_used_model"] = model.to_dict()

