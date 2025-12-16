"""OpenAI provider adapter with streaming and tool-call parsing."""
from __future__ import annotations

import json
import logging
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

        formatted_messages = self._format_messages(messages)

        # Log the request details for debugging
        logging.debug("OpenAI API request - model: %s, num_messages: %d, num_tools: %d",
                     self.model, len(formatted_messages), len(tools) if tools else 0)

        # Log the messages (truncated for readability)
        for i, msg in enumerate(formatted_messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                content_preview = content[:200] + "..." if len(content) > 200 else content
                logging.debug("OpenAI message[%d] role=%s content=%r", i, role, content_preview)

        if tools:
            # Log tool summary
            logging.debug("OpenAI tools being sent: %s",
                         [{"name": t.get("function", {}).get("name"),
                           "has_params": bool(t.get("function", {}).get("parameters", {}).get("properties"))}
                          for t in tools])

            # Log detailed tool schemas for critical tools
            for tool in tools:
                func = tool.get("function", {})
                name = func.get("name", "")
                if name in {"read_file", "list_directory", "write_file"}:
                    params = func.get("parameters", {})
                    logging.debug("OpenAI tool '%s' full schema: %s", name, json.dumps(func, indent=2))

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
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
                name = getattr(function, "name", None) or ""
                arguments_chunk = getattr(function, "arguments", "") if function else ""
                call_state = pending_calls.setdefault(call_id, {"id": call_id, "name": name, "arguments": ""})
                if name:
                    call_state["name"] = name
                call_state["arguments"] += arguments_chunk

        for data in pending_calls.values():
            parsed_args: Dict[str, Any]
            raw_arguments = data.get("arguments") or ""

            # Log what OpenAI actually returned
            logging.debug(
                "OpenAI tool call - name: %s, raw_arguments: %r, call_id: %s",
                data.get("name"),
                raw_arguments,
                data.get("id"),
            )

            try:
                parsed_args = json.loads(raw_arguments or "{}")
            except json.JSONDecodeError:
                logging.warning(
                    "Failed to parse OpenAI tool arguments for %s: %r",
                    data.get("name"),
                    raw_arguments,
                )
                parsed_args = {"raw": raw_arguments}

            # Warn if arguments are empty when we expected some
            if not parsed_args or parsed_args == {}:
                logging.warning(
                    "OpenAI returned empty arguments for tool call: %s (call_id: %s)",
                    data.get("name"),
                    data.get("id"),
                )

            name = data.get("name") or ""
            if not name:
                continue
            yield ToolCallEvent(call_id=data.get("id", ""), name=name, arguments=parsed_args)

        yield DoneEvent(text="".join(accumulated_text), stop_reason=finish_reason)
