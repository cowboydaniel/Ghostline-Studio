"""OpenAI provider adapter with streaming and tool-call parsing."""
from __future__ import annotations

import json
from importlib import import_module
from typing import Any, Dict, Generator, Iterable, List, Optional

from ghostline.ai.events import DoneEvent, TextDeltaEvent, ToolCallEvent


class OpenAIProvider:
    """Stream chat completions with tool calling for OpenAI models."""

    def __init__(self, model: str, api_key: Optional[str] = None, temperature: float | None = None):
        openai_mod = import_module("openai")
        OpenAI = getattr(openai_mod, "OpenAI")

        self.model = model
        self.client = OpenAI(api_key=api_key)
        self.temperature = temperature if temperature is not None else 0.2

    def _format_messages(self, messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for message in messages:
            if message.get("role") == "tool":
                formatted.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.get("tool_call_id"),
                        "name": message.get("name"),
                        "content": message.get("content"),
                    }
                )
            else:
                formatted.append({"role": message.get("role", "user"), "content": message.get("content"), "tool_calls": message.get("tool_calls")})
        return formatted

    def stream(
        self, messages: Iterable[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[object, None, None]:
        """Yield text deltas, tool calls, and completion markers."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._format_messages(messages),
                tools=tools,
                stream=True,
                temperature=self.temperature,
            )
        except Exception:
            raise

        accumulated_text: List[str] = []
        pending_calls: Dict[str, Dict[str, Any]] = {}
        finish_reason: Optional[str] = None

        for chunk in response:
            choices = getattr(chunk, "choices", [])
            if not choices:
                continue
            delta = getattr(choices[0], "delta", {})
            finish_reason = getattr(choices[0], "finish_reason", finish_reason)

            content = getattr(delta, "content", None)
            if isinstance(content, list):
                for part in content:
                    text = getattr(part, "text", None)
                    if text:
                        accumulated_text.append(text)
                        yield TextDeltaEvent(text)
            elif isinstance(content, str):
                accumulated_text.append(content)
                yield TextDeltaEvent(content)

            tool_calls = getattr(delta, "tool_calls", None) or []
            for call in tool_calls:
                call_id = getattr(call, "id", None) or str(getattr(call, "index", len(pending_calls)))
                function = getattr(call, "function", None)
                name = getattr(function, "name", "") if function else ""
                arguments_chunk = getattr(function, "arguments", "") if function else ""
                call_state = pending_calls.setdefault(call_id, {"id": call_id, "name": name, "arguments": ""})
                if name:
                    call_state["name"] = name
                call_state["arguments"] += arguments_chunk

        for data in pending_calls.values():
            parsed_args: Dict[str, Any]
            try:
                parsed_args = json.loads(data.get("arguments") or "{}")
            except json.JSONDecodeError:
                parsed_args = {"raw": data.get("arguments", "")}
            yield ToolCallEvent(call_id=data.get("id", ""), name=data.get("name", ""), arguments=parsed_args)

        yield DoneEvent(text="".join(accumulated_text), stop_reason=finish_reason)
