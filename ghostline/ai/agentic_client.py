"""Agentic AI client that orchestrates multi-round tool use."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional

from ghostline.ai.events import DoneEvent, Event, EventType, TextDeltaEvent, ToolCallEvent, ToolResultEvent
from ghostline.ai.providers import AnthropicProvider, OpenAIProvider, OllamaProvider
from ghostline.ai.tools.definitions import get_tool_definitions
from ghostline.ai.tools.executor import ToolExecutor


class AgenticClient:
    """High-level agentic client that streams events across provider calls."""

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        workspace_root: str | Path = ".",
        max_rounds: int = 4,
        temperature: float | None = None,
    ) -> None:
        self.provider_name = provider.lower()
        self.model = model
        self.api_key = api_key
        self.max_rounds = max_rounds
        self.temperature = temperature
        self.tool_executor = ToolExecutor(workspace_root)
        self.provider = self._init_provider()

    def _init_provider(self):
        if self.provider_name == "anthropic":
            return AnthropicProvider(self.model, api_key=self.api_key, temperature=self.temperature)
        if self.provider_name == "openai":
            return OpenAIProvider(self.model, api_key=self.api_key, temperature=self.temperature)
        if self.provider_name == "ollama":
            return OllamaProvider(self.model, temperature=self.temperature)
        raise ValueError(f"Unsupported provider: {self.provider_name}")

    def stream(
        self,
        messages: Iterable[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Generator[Event, None, None]:
        """Stream events through multi-round tool execution."""

        conversation: List[Dict[str, Any]] = list(messages)
        tools = tools or get_tool_definitions(self.provider_name)
        round_index = 0

        while True:
            if round_index >= self.max_rounds:
                yield DoneEvent(text="", stop_reason="max_rounds")
                break

            pending_calls: List[ToolCallEvent] = []
            final_done: Optional[DoneEvent] = None

            for event in self.provider.stream(conversation, tools=tools):
                yield event
                if event.type == EventType.TOOL_CALL and isinstance(event, ToolCallEvent):
                    pending_calls.append(event)
                elif event.type == EventType.DONE and isinstance(event, DoneEvent):
                    final_done = event

            if not pending_calls:
                if not final_done:
                    yield DoneEvent(text="", stop_reason="stop")
                break

            assistant_message: Dict[str, Any] = {"role": "assistant"}
            if final_done and final_done.text:
                assistant_message["content"] = final_done.text

            tool_calls_payload: List[Dict[str, Any]] = []
            for call in pending_calls:
                tool_calls_payload.append(
                    {
                        "id": call.call_id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                    }
                )
            if tool_calls_payload:
                assistant_message["tool_calls"] = tool_calls_payload

            if assistant_message:
                conversation.append(assistant_message)

            for call in pending_calls:
                result_text = self.tool_executor.execute(call.name, call.arguments)
                yield ToolResultEvent(call_id=call.call_id, name=call.name, output=result_text)
                conversation.append({
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "name": call.name,
                    "content": result_text,
                })

            round_index += 1
