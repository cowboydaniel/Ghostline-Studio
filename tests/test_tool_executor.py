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

if "tiktoken" not in sys.modules:
    tiktoken_stub = types.ModuleType("tiktoken")

    class _DummyEncoding:
        def encode(self, text: str):
            return [0] * len(text)

    tiktoken_stub.get_encoding = lambda *_args, **_kwargs: _DummyEncoding()
    tiktoken_stub.encoding_for_model = lambda *_args, **_kwargs: _DummyEncoding()
    sys.modules["tiktoken"] = tiktoken_stub

from ghostline.ai.tools.executor import ToolExecutor


def test_execute_handles_missing_required_args(tmp_path):
    executor = ToolExecutor(tmp_path)

    result = executor.execute("read_file", {})

    assert "Missing required parameter(s)" in result.output
    assert result.output.endswith("path")

    history = executor.get_history()
    assert history[-1]["tool"] == "read_file"
    assert history[-1]["status"] == "error"
