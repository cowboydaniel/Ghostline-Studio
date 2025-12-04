"""Tests for the AI client streaming helpers."""
from types import SimpleNamespace
import sys
import types

import pytest

if "openai" not in sys.modules:
    placeholder = types.ModuleType("openai")

    class _PlaceholderOpenAI:  # noqa: D401 - minimal stub for import
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("OpenAI client placeholder")

    placeholder.OpenAI = _PlaceholderOpenAI
    sys.modules["openai"] = placeholder

from ghostline.ai.ai_client import OpenAICompatibleBackend
from ghostline.core.config import ConfigManager


class DummyResponses:
    def __init__(self, events):
        self._events = events

    def create(self, *args, **kwargs):  # noqa: D401 - mimic OpenAI client signature
        """Return a generator that yields pre-defined events."""
        return iter(self._events)


class DummyOpenAI:
    def __init__(self, *_args, **_kwargs):
        self.responses = DummyResponses([])


@pytest.mark.parametrize(
    "events,expected",
    [
        (
            [
                SimpleNamespace(type="response.delta", delta="Hello "),
                SimpleNamespace(type="response.completed", data="World"),
            ],
            ["Hello ", "World"],
        ),
    ],
)
def test_openai_stream_emits_text_from_general_events(monkeypatch, events, expected):
    config = ConfigManager()
    config.set("ai", {"backend": "openai"})

    dummy_client = DummyOpenAI()
    dummy_client.responses = DummyResponses(events)
    monkeypatch.setattr("ghostline.ai.ai_client.OpenAI", lambda *args, **kwargs: dummy_client)

    backend = OpenAICompatibleBackend(config)
    tokens = list(backend.stream("prompt"))

    assert tokens == expected
