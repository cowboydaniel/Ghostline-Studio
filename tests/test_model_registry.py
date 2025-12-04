import subprocess

import pytest

from ghostline.ai.model_registry import ModelRegistry, OllamaModelDiscovery
from ghostline.core.config import ConfigManager


class DummyDiscovery:
    def __init__(self, models=None):
        self.models = models or []

    def discover(self):
        return self.models


def test_can_toggle_enabled_openai_models():
    config = ConfigManager()
    registry = ModelRegistry(config, discovery=DummyDiscovery())

    initial_enabled = [model.id for model in registry.enabled_openai_models()]
    assert "gpt-5.1" in initial_enabled

    registry.set_enabled_openai_models(["gpt-4.1"])
    updated = [model.id for model in registry.enabled_openai_models()]

    assert updated == ["gpt-4.1"]


def test_ollama_discovery_gracefully_handles_missing(monkeypatch):
    discovery = OllamaModelDiscovery()

    def fake_urlopen(*_args, **_kwargs):  # pragma: no cover - executed via discovery
        raise ConnectionError("offline")

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=["ollama", "list"], returncode=1, stdout="", stderr="error")

    monkeypatch.setattr("ghostline.ai.model_registry.request.urlopen", fake_urlopen)
    monkeypatch.setattr("ghostline.ai.model_registry.subprocess.run", fake_run)

    models = discovery.discover()

    assert models == []
