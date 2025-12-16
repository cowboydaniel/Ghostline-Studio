"""Anthropic provider adapter with streaming tool-call extraction."""
from __future__ import annotations

import json
import logging
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

            # Handle tool response messages (convert from OpenAI format to Anthropic format)
            if role == "tool":
                # Anthropic expects tool results as user messages with tool_result content blocks
                formatted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": message.get("tool_call_id"),
                        "content": content or "",
                    }]
                })
            elif tool_calls:
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

        formatted_messages = self._format_messages(messages)

        # Extract system message (Anthropic requires it as a separate parameter)
        system_message = None
        non_system_messages = []
        for msg in formatted_messages:
            if msg.get("role") == "system":
                # Combine multiple system messages if present
                content = msg.get("content", "")
                if system_message:
                    system_message += "\n\n" + content
                else:
                    system_message = content
            else:
                non_system_messages.append(msg)

        # Log the request details for debugging
        logging.debug("Anthropic API request - model: %s, num_messages: %d, num_tools: %d, has_system: %s",
                     self.model, len(non_system_messages), len(tools) if tools else 0, bool(system_message))

        # Log system message if present
        if system_message:
            system_preview = system_message[:200] + "..." if len(system_message) > 200 else system_message
            logging.debug("Anthropic system message: %r", system_preview)

        # Log the messages (truncated for readability)
        for i, msg in enumerate(non_system_messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                content_preview = content[:200] + "..." if len(content) > 200 else content
                logging.debug("Anthropic message[%d] role=%s content=%r", i, role, content_preview)
            elif isinstance(content, list):
                logging.debug("Anthropic message[%d] role=%s content=<list with %d blocks>", i, role, len(content))

        if tools:
            # Log tool summary
            logging.debug("Anthropic tools being sent: %s",
                         [{"name": t.get("name"),
                           "has_params": bool(t.get("input_schema", {}).get("properties"))}
                          for t in tools])

            # Log detailed tool schemas for critical tools
            for tool in tools:
                name = tool.get("name", "")
                if name in {"read_file", "list_directory", "write_file"}:
                    logging.debug("Anthropic tool '%s' full schema: %s", name, json.dumps(tool, indent=2))

        tool_uses: Dict[str, Dict[str, Any]] = {}
        accumulated_text: List[str] = []

        # Build API call parameters
        api_params: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": non_system_messages,
            "temperature": self.temperature,
        }

        # Add system parameter if we have a system message
        if system_message:
            api_params["system"] = system_message

        # Add tools if provided
        if tools:
            api_params["tools"] = tools

        with self.client.messages.stream(**api_params) as stream:  # type: ignore[attr-defined]
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
                        # Check if input is already provided (for small tool calls)
                        input_data = getattr(block, "input", None)
                        if input_data is not None:
                            # Input provided immediately, serialize it
                            tool_uses[block.id] = {"id": block.id, "name": block.name, "arguments": json.dumps(input_data)}
                        else:
                            # Input will be streamed via input_json_delta events
                            tool_uses[block.id] = {"id": block.id, "name": block.name, "arguments": ""}
                elif event_type == "message_stop":
                    stop_reason = getattr(event, "stop_reason", None)
                    for data in tool_uses.values():
                        parsed_args: Dict[str, Any]
                        raw_arguments = data.get("arguments") or ""

                        # Log what Anthropic actually returned
                        logging.debug(
                            "Anthropic tool call - name: %s, raw_arguments: %r, call_id: %s",
                            data.get("name"),
                            raw_arguments,
                            data.get("id"),
                        )

                        try:
                            parsed_args = json.loads(raw_arguments or "{}")
                        except json.JSONDecodeError:
                            logging.warning(
                                "Failed to parse Anthropic tool arguments for %s: %r",
                                data.get("name"),
                                raw_arguments,
                            )
                            parsed_args = {"raw": raw_arguments}

                        # Warn if arguments are empty when we expected some
                        if not parsed_args or parsed_args == {}:
                            logging.warning(
                                "Anthropic returned empty arguments for tool call: %s (call_id: %s)",
                                data.get("name"),
                                data.get("id"),
                            )

                        yield ToolCallEvent(call_id=data.get("id", ""), name=data.get("name", ""), arguments=parsed_args)
                    yield DoneEvent(text="".join(accumulated_text), stop_reason=stop_reason)
