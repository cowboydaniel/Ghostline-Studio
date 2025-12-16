"""Tool definition utilities for provider-specific formatting.

This module maintains a canonical tool schema aligned with the tables in
``AGENTIC.md`` and exposes helpers to translate that schema into the structures
expected by Anthropic, OpenAI, and Ollama tool-calling interfaces.
"""
from __future__ import annotations

from typing import Any, Dict, List


CANONICAL_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read contents of a file",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or workspace-relative path to the file",
            }
        },
        "required": ["path"],
    },
    {
        "name": "search_code",
        "description": "Search for text or regex patterns in the workspace",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "regex": {
                "type": "boolean",
                "description": "Treat the query as a regular expression",
                "default": False,
            },
            "file_pattern": {
                "type": ["string", "null"],
                "description": "Optional glob to limit files (e.g. *.py)",
                "default": None,
            },
        },
        "required": ["query"],
    },
    {
        "name": "search_symbols",
        "description": "Find functions or classes by name",
        "properties": {
            "name": {
                "type": "string",
                "description": "Symbol name to search for",
            },
            "kind": {
                "type": "string",
                "enum": ["function", "class", "all"],
                "description": "Type of symbol to search for",
                "default": "all",
            },
        },
        "required": ["name"],
    },
    {
        "name": "list_directory",
        "description": "List files in a directory",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path relative to workspace",
                "default": ".",
            },
            "recursive": {
                "type": "boolean",
                "description": "Recurse into subdirectories",
                "default": False,
            },
        },
        "required": [],
    },
    {
        "name": "get_file_info",
        "description": "Get file metadata (size, modified time)",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to workspace",
            }
        },
        "required": ["path"],
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to write relative to workspace",
            },
            "content": {
                "type": "string",
                "description": "Full file contents to write",
            },
        },
        "required": ["path", "content"],
    },
    {
        "name": "edit_file",
        "description": "Apply targeted edits to a file",
        "properties": {
            "path": {"type": "string", "description": "File to edit"},
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "old": {
                            "type": "string",
                            "description": "Existing text to replace",
                        },
                        "new": {
                            "type": "string",
                            "description": "Replacement text",
                        },
                    },
                    "required": ["old", "new"],
                },
                "description": "List of search-replace operations",
            },
        },
        "required": ["path", "edits"],
    },
    {
        "name": "create_directory",
        "description": "Create a new folder",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to create",
            }
        },
        "required": ["path"],
    },
    {
        "name": "delete_file",
        "description": "Delete a file (with confirmation)",
        "properties": {
            "path": {"type": "string", "description": "File to delete"}
        },
        "required": ["path"],
    },
    {
        "name": "rename_file",
        "description": "Rename or move a file",
        "properties": {
            "old_path": {
                "type": "string",
                "description": "Original path of the file",
            },
            "new_path": {
                "type": "string",
                "description": "New path for the file",
            },
        },
        "required": ["old_path", "new_path"],
    },
    {
        "name": "run_command",
        "description": "Run a shell command inside the workspace",
        "properties": {
            "command": {"type": "string", "description": "Shell command"},
            "cwd": {
                "type": ["string", "null"],
                "description": "Optional working directory relative to workspace",
                "default": None,
            },
        },
        "required": ["command"],
    },
    {
        "name": "run_python",
        "description": "Execute Python code",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute",
            }
        },
        "required": ["code"],
    },
]


class UnsupportedProviderError(ValueError):
    """Raised when an unknown provider is requested."""


def get_tool_definitions(provider: str) -> List[Dict[str, Any]]:
    """Return provider-formatted tool schemas.

    Args:
        provider: Provider key (``anthropic``, ``openai``, or ``ollama``).

    Raises:
        UnsupportedProviderError: If an unknown provider string is supplied.
    """

    normalized = provider.lower()
    if normalized == "anthropic":
        return [_to_anthropic_schema(tool) for tool in CANONICAL_TOOLS]
    if normalized in {"openai", "ollama"}:
        return [_to_openai_like_schema(tool) for tool in CANONICAL_TOOLS]
    raise UnsupportedProviderError(f"Unsupported provider: {provider}")


def _to_anthropic_schema(tool: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "input_schema": {
            "type": "object",
            "properties": tool.get("properties", {}),
            "required": tool.get("required", []),
        },
    }


def _to_openai_like_schema(tool: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": tool.get("properties", {}),
                "required": tool.get("required", []),
            },
        },
    }
