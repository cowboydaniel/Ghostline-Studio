"""Sandbox hooks for command execution.

Currently provides a passthrough implementation; future phases can extend this
module to enforce allowlists, block networked commands, or route commands
through a restricted sandbox.
"""
from __future__ import annotations


def apply_command_sandbox(command: str) -> str:
    """Adjust or reject commands before execution.

    Args:
        command: The raw shell command requested by the AI agent.

    Returns:
        A sanitized command string. For now this is a passthrough placeholder
        that enables future sandbox integrations without changing the executor
        signature.
    """

    return command
