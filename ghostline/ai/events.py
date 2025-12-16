"""Event primitives for streaming agentic interactions.

These dataclasses normalize streaming output across providers so the
``AgenticClient`` can orchestrate tool calls and return consistent events to
consumers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """Types of events emitted by the agentic streaming loop."""

    TEXT_DELTA = "text_delta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DONE = "done"


class ApprovalMode(str, Enum):
    """Levels of user approval required before executing tools."""

    AUTO = "auto"
    WRITE_APPROVAL = "write"
    ALL_APPROVAL = "all"


@dataclass
class Event:
    """Base event class for type hints."""

    type: EventType


@dataclass
class TextDeltaEvent(Event):
    """Incremental text emitted by the model."""

    text: str

    def __init__(self, text: str) -> None:
        super().__init__(EventType.TEXT_DELTA)
        self.text = text


@dataclass
class ToolCallEvent(Event):
    """Model-issued request to execute a tool."""

    call_id: str
    name: str
    arguments: Dict[str, Any]

    def __init__(self, call_id: str, name: str, arguments: Dict[str, Any]):
        super().__init__(EventType.TOOL_CALL)
        self.call_id = call_id
        self.name = name
        self.arguments = arguments


@dataclass
class ToolResultEvent(Event):
    """Result of a tool execution emitted back to the consumer."""

    call_id: str
    name: str
    output: str
    metadata: Optional[Dict[str, Any]]

    def __init__(self, call_id: str, name: str, output: str, metadata: Optional[Dict[str, Any]] = None):
        super().__init__(EventType.TOOL_RESULT)
        self.call_id = call_id
        self.name = name
        self.output = output
        self.metadata = metadata


@dataclass
class DoneEvent(Event):
    """Signals completion of a streaming round."""

    text: str
    stop_reason: Optional[str] = None

    def __init__(self, text: str = "", stop_reason: Optional[str] = None):
        super().__init__(EventType.DONE)
        self.text = text
        self.stop_reason = stop_reason
