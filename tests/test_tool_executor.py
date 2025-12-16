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
    assert result.metadata == {
        "missing_parameters": ["path"],
        "provided_args": {},
    }

    history = executor.get_history()
    assert history[-1]["tool"] == "read_file"
    assert history[-1]["status"] == "error"


def test_execute_treats_none_as_missing(tmp_path):
    executor = ToolExecutor(tmp_path)

    result = executor.execute("read_file", {"path": None})

    assert "Missing required parameter(s)" in result.output
    assert result.output.endswith("path")
    assert result.metadata == {
        "missing_parameters": ["path"],
        "provided_args": {"path": None},
    }

    history = executor.get_history()
    assert history[-1]["tool"] == "read_file"
    assert history[-1]["status"] == "error"


def test_logging_captures_missing_parameter_details(tmp_path, caplog):
    """Test that missing parameters are logged with full details for debugging."""
    import logging

    caplog.set_level(logging.DEBUG)
    executor = ToolExecutor(tmp_path)

    # Call with empty args
    result = executor.execute("read_file", {})

    # Check that debug log captures the tool call
    assert any("Executing tool: read_file" in record.message for record in caplog.records)

    # Check that warning log captures the validation failure
    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_records) == 1
    assert "Tool validation failed for read_file" in warning_records[0].message
    assert "Missing: ['path']" in warning_records[0].message
    assert "Raw args: {}" in warning_records[0].message


def test_logging_captures_none_parameter(tmp_path, caplog):
    """Test that None parameters are logged explicitly for debugging."""
    import logging

    caplog.set_level(logging.DEBUG)
    executor = ToolExecutor(tmp_path)

    # Call with None path
    result = executor.execute("read_file", {"path": None})

    # Check debug log shows the None value
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert any("'path': None" in record.message for record in debug_records)

    # Check warning log shows the None value
    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("'path': None" in record.message for record in warning_records)
