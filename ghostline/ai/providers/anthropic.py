"""Anthropic provider adapter with streaming tool-call extraction."""
from __future__ import annotations

import json
from importlib import import_module
from typing import Any, Dict, Generator, Iterable, List, Optional

from ghostline.ai.events import DoneEvent, TextDeltaEvent, ToolCallEvent


class AnthropicProvider:
    """Stream responses and surface tool calls for Anthropic models."""

    def __init__(self, model: str, api_key: Optional[str] = None, temperature: float | None = None):
        anthropic = import_module("anthropic")  # type: ignore

        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)
        self.temperature = temperature if temperature is not None else 0.2

    def _format_messages(self, messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content")
            tool_calls = message.get("tool_calls")
            if tool_calls:
                # Anthropic expects the tool calls as content blocks on the assistant message
                content_blocks: List[Dict[str, Any]] = []
                if content:
                    content_blocks.append({"type": "text", "text": content})
                for call in tool_calls:
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": call.get("id"),
                            "name": call.get("function", {}).get("name"),
                            "input": json.loads(call.get("function", {}).get("arguments", "{}")),
                        }
                    )
                formatted.append({"role": role, "content": content_blocks})
            else:
                formatted.append({"role": role, "content": content})
        return formatted

    def stream(
        self, messages: Iterable[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[object, None, None]:
        """Yield text deltas, tool calls, and completion markers."""

        tool_uses: Dict[str, Dict[str, Any]] = {}
        accumulated_text: List[str] = []

        with self.client.messages.stream(  # type: ignore[attr-defined]
            model=self.model,
            messages=self._format_messages(messages),
            tools=tools,
            temperature=self.temperature,
        ) as stream:
            for event in stream:
                event_type = getattr(event, "type", None)
                if event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    block = getattr(event, "content_block", None)
                    if getattr(delta, "type", None) == "text_delta":
                        text = getattr(delta, "text", "")
                        if text:
                            accumulated_text.append(text)
                            yield TextDeltaEvent(text)
                    elif getattr(delta, "type", None) == "input_json_delta" and getattr(block, "type", None) == "tool_use":
                        partial = getattr(delta, "partial_json", "")
                        if partial:
                            tool_data = tool_uses.setdefault(block.id, {"id": block.id, "name": block.name, "arguments": ""})
                            tool_data["arguments"] += partial
                elif event_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if getattr(block, "type", None) == "tool_use":
                        tool_uses[block.id] = {"id": block.id, "name": block.name, "arguments": ""}
                elif event_type == "message_stop":
                    stop_reason = getattr(event, "stop_reason", None)
                    for data in tool_uses.values():
                        parsed_args: Dict[str, Any]
                        try:
                            parsed_args = json.loads(data.get("arguments") or "{}")
                        except json.JSONDecodeError:
                            parsed_args = {"raw": data.get("arguments", "")}
                        yield ToolCallEvent(call_id=data.get("id", ""), name=data.get("name", ""), arguments=parsed_args)
                    yield DoneEvent(text="".join(accumulated_text), stop_reason=stop_reason)
