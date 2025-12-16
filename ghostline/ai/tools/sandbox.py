"""Sandbox hooks for command execution.

Provides a restricted command plan that can be expanded to enforce tighter
security policies. The goal is to minimise the surface area for shell injection
while still letting trusted commands execute during development.
"""
from __future__ import annotations

from dataclasses import dataclass
import shlex
from typing import Iterable


ALLOWED_BINARIES = {
    "ls",
    "cat",
    "python",
    "python3",
    "rg",
    "sed",
    "awk",
    "find",
    "stat",
    "head",
    "tail",
    "git",
}
BLOCKED_TOKENS = {"&&", ";", "||"}
DEFAULT_TIMEOUT = 30


@dataclass
class SandboxedCommand:
    """Concrete execution plan enforced by the sandbox layer."""

    argv: list[str]
    timeout: int = DEFAULT_TIMEOUT
    shell: bool = False


def apply_command_sandbox(command: str, *, allowed_binaries: Iterable[str] | None = None) -> SandboxedCommand | str:
    """Adjust or reject commands before execution.

    Args:
        command: The raw shell command requested by the AI agent.

    Returns:
        A :class:`SandboxedCommand` ready for execution or an error string when
        the command is rejected.
    """

    allowed = set(allowed_binaries) if allowed_binaries else ALLOWED_BINARIES

    if any(token in command for token in BLOCKED_TOKENS):
        return "Error: Command chaining is disabled in sandboxed execution"

    tokens = shlex.split(command)
    if not tokens:
        return "Error: Empty command"

    binary = tokens[0].split("/")[-1]
    if binary not in allowed:
        return f"Error: Command '{binary}' is not allowed in the sandbox"

    return SandboxedCommand(argv=tokens)
