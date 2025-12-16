"""Ollama provider adapter with optional tool support."""
from __future__ import annotations

import json
from importlib import import_module
from typing import Any, Dict, Generator, Iterable, List, Optional

from ghostline.ai.events import DoneEvent, TextDeltaEvent, ToolCallEvent


class OllamaProvider:
    """Stream responses from Ollama and surface tool calls when supported."""

    def __init__(self, model: str, temperature: float | None = None):
        self.model = model
        self.ollama = import_module("ollama")  # type: ignore
        self.temperature = temperature if temperature is not None else 0.2
        self._tools_supported: Optional[bool] = None

    def _format_messages(self, messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for message in messages:
            entry: Dict[str, Any] = {"role": message.get("role", "user")}
            if message.get("role") == "tool":
                entry.update({"content": message.get("content"), "tool_call_id": message.get("tool_call_id"), "name": message.get("name")})
            else:
                entry["content"] = message.get("content")
                if message.get("tool_calls"):
                    entry["tool_calls"] = message.get("tool_calls")
            formatted.append(entry)
        return formatted

    def _supports_tools(self) -> bool:
        if self._tools_supported is not None:
            return self._tools_supported
        try:
            details = self.ollama.show(self.model)
            capabilities = details.get("model_info", {}).get("capabilities") or details.get("details", {}).get("capabilities")
            if isinstance(capabilities, list):
                self._tools_supported = "tools" in capabilities or "tool_calls" in capabilities
            elif isinstance(capabilities, dict):
                self._tools_supported = bool(capabilities.get("tools") or capabilities.get("tool_calls"))
            else:
                self._tools_supported = False
        except Exception:
            self._tools_supported = False
        return self._tools_supported

    def stream(
        self, messages: Iterable[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[object, None, None]:
        """Yield text deltas, tool calls, and completion markers."""

        supports_tools = self._supports_tools()
        pending_calls: Dict[str, Dict[str, Any]] = {}
        accumulated_text: List[str] = []
        finish_reason: Optional[str] = None

        stream = self.ollama.chat(
            model=self.model,
            messages=self._format_messages(messages),
            stream=True,
            options={"temperature": self.temperature},
            tools=tools if supports_tools else None,
        )

        for chunk in stream:
            message = chunk.get("message", {})
            if message.get("content"):
                accumulated_text.append(message.get("content", ""))
                yield TextDeltaEvent(message.get("content", ""))

            for call in message.get("tool_calls", []) or []:
                call_id = call.get("id") or str(len(pending_calls))
                name = call.get("function", {}).get("name", "")
                arguments_chunk = call.get("function", {}).get("arguments", "")
                call_state = pending_calls.setdefault(call_id, {"id": call_id, "name": name, "arguments": ""})
                if name:
                    call_state["name"] = name
                call_state["arguments"] += arguments_chunk

            if chunk.get("done"):
                finish_reason = chunk.get("done_reason") or finish_reason
                break

        for data in pending_calls.values():
            parsed_args: Dict[str, Any]
            try:
                parsed_args = json.loads(data.get("arguments") or "{}")
            except json.JSONDecodeError:
                parsed_args = {"raw": data.get("arguments", "")}
            yield ToolCallEvent(call_id=data.get("id", ""), name=data.get("name", ""), arguments=parsed_args)

        yield DoneEvent(text="".join(accumulated_text), stop_reason=finish_reason or ("tool_calls" if pending_calls else None))
