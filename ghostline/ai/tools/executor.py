"""Provider-agnostic tool execution layer.

Implements the tool behaviours described in ``AGENTIC.md`` with workspace-aware
path resolution, safe defaults, and output truncation to keep responses within
provider token budgets.
"""
from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timedelta
import logging
import subprocess
import sys
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List

from .sandbox import apply_command_sandbox


MAX_OUTPUT_LENGTH = 4000
MAX_FILE_READ_BYTES = 200_000
SENSITIVE_FILENAMES = {
    ".env",
    ".env.local",
    "id_rsa",
    "id_dsa",
    "credentials",
    "secrets",
    "aws_access_keys",
    "google_application_credentials.json",
}
SENSITIVE_DIR_PARTS = {".ssh", ".aws", ".git"}


@dataclass
class ToolResult:
    name: str
    output: str
    metadata: dict[str, Any] | None = None


class ToolExecutor:
    """Execute tools requested by AI agents."""

    def __init__(
        self,
        workspace_root: Path | str,
        *,
        allowed_roots: Iterable[Path | str] | None = None,
        max_calls_per_minute: int | None = None,
        output_budget: int | None = None,
    ):
        workspace = Path(workspace_root).resolve()
        self.workspace = workspace
        self.allowed_roots: list[Path] = [workspace]
        if allowed_roots:
            for root in allowed_roots:
                root_path = Path(root).resolve()
                if root_path not in self.allowed_roots:
                    self.allowed_roots.append(root_path)
        self.max_calls_per_minute = max_calls_per_minute
        self.output_budget = output_budget
        self.call_history: Deque[dict[str, Any]] = deque(maxlen=200)
        self.call_timestamps: Deque[datetime] = deque()
        self.allowed_tools: Dict[str, Callable[..., str]] = {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "edit_file": self.edit_file,
            "search_code": self.search_code,
            "search_symbols": self.search_symbols,
            "list_directory": self.list_directory,
            "get_file_info": self.get_file_info,
            "create_directory": self.create_directory,
            "delete_file": self.delete_file,
            "rename_file": self.rename_file,
            "run_command": self.run_command,
            "run_python": self.run_python,
        }

    def execute(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Execute a tool and return the result payload."""
        if tool_name not in self.allowed_tools:
            result = ToolResult(tool_name, f"Error: Unknown tool '{tool_name}'")
            self._record_history(tool_name, args, result)
            return result

        rate_limit_error = self._check_rate_limit()
        if rate_limit_error:
            result = ToolResult(tool_name, rate_limit_error)
            self._record_history(tool_name, args, result)
            return result

        validation_error, missing_params = self._validate_required_args(
            self.allowed_tools[tool_name], args
        )
        if validation_error:
            hint = (
                " Try using list_directory or search_code to find the right path "
                "before retrying path-dependent tools like read_file."
            )
            validation_error = validation_error + hint if missing_params else validation_error
            sanitized_args = self._sanitize_args(args)
            metadata = {
                "missing_parameters": missing_params,
                "provided_args": sanitized_args,
            }
            result = ToolResult(tool_name, validation_error, metadata)
            self._record_history(tool_name, args, result)
            return result

        self._register_call_timestamp()

        try:
            output = self.allowed_tools[tool_name](**args)
            if isinstance(output, ToolResult):
                result = output
            else:
                result = ToolResult(tool_name, str(output))
            return result
        except Exception as exc:  # pragma: no cover - defensive catch
            logging.exception("Tool execution failed for %s", tool_name)
            result = ToolResult(tool_name, f"Error executing {tool_name}: {exc}")
        finally:
            self._record_history(tool_name, args, locals().get("result"))

        return result

    def read_file(self, path: str) -> str:
        """Read file contents with truncation."""
        full_path = self._ensure_file(path)
        if isinstance(full_path, str):
            return full_path

        size = full_path.stat().st_size
        if size > MAX_FILE_READ_BYTES:
            content = full_path.read_text(encoding="utf-8")[:MAX_FILE_READ_BYTES]
            return self._truncate_output(
                content + "\n\n[file truncated due to size and token budget limits]"
            )

        content = full_path.read_text(encoding="utf-8")
        return self._truncate_output(content)

    def write_file(self, path: str, content: str) -> ToolResult:
        """Write content to file, creating parent directories as needed."""
        full_path = self._resolve_path(path)
        if isinstance(full_path, str):
            return ToolResult("write_file", full_path)

        previous_content = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        metadata = self._build_change_metadata(path, previous_content, content)
        return ToolResult("write_file", f"Successfully wrote {len(content)} bytes to {path}", metadata)

    def edit_file(self, path: str, edits: List[Dict[str, str]]) -> ToolResult:
        """Apply search-replace edits to a file."""
        full_path = self._ensure_file(path)
        if isinstance(full_path, str):
            return ToolResult("edit_file", full_path)

        original_content = full_path.read_text(encoding="utf-8")
        content = original_content
        applied = 0
        for edit in edits:
            old = edit.get("old", "")
            new = edit.get("new", "")
            if old not in content:
                return ToolResult("edit_file", f"Error: Could not find text to replace: {old[:50]}...")
            content = content.replace(old, new, 1)
            applied += 1

        full_path.write_text(content, encoding="utf-8")
        metadata = self._build_change_metadata(path, original_content, content)
        return ToolResult("edit_file", f"Successfully applied {applied} edit(s) to {path}", metadata)

    def search_code(self, query: str, regex: bool = False, file_pattern: str | None = None) -> str:
        """Search for code in the workspace using ripgrep when available."""
        cmd = ["rg", "-n"]
        if not regex:
            cmd.append("-F")
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        cmd.extend([query, str(self.workspace)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError:
            return "Error: ripgrep (rg) is not installed in the environment."

        if result.returncode == 2:
            return self._truncate_output(result.stderr or "Search failed")

        output = result.stdout.strip()
        if not output:
            return "No matches found."

        return self._truncate_output(output)

    def search_symbols(self, name: str, kind: str = "all") -> str:
        """Find functions or classes by name using ripgrep heuristics."""
        patterns: List[str] = []
        target = name.strip()
        if kind in {"function", "all"}:
            patterns.append(fr"^\s*def\s+{target}\b")
        if kind in {"class", "all"}:
            patterns.append(fr"^\s*class\s+{target}\b")

        if not patterns:
            return "Error: Invalid kind specified."

        results: List[str] = []
        for pattern in patterns:
            search_result = self.search_code(pattern, regex=True)
            if search_result and not search_result.startswith("Error") and search_result != "No matches found.":
                results.append(f"Matches for pattern '{pattern}':\n{search_result}")

        if not results:
            return "No matches found."

        combined = "\n\n".join(results)
        return self._truncate_output(combined)

    def list_directory(self, path: str = ".", recursive: bool = False) -> str:
        """List directory contents with optional recursion."""
        full_path = self._resolve_path(path)
        if isinstance(full_path, str):
            return full_path

        if not full_path.exists() or not full_path.is_dir():
            return f"Error: Not a directory: {path}"

        if recursive:
            files = list(full_path.rglob("*"))
        else:
            files = list(full_path.iterdir())

        files = files[:200]
        relative_paths = [str(f.relative_to(self.workspace)) for f in files]
        return "\n".join(relative_paths) if relative_paths else "(empty)"

    def get_file_info(self, path: str) -> str:
        """Return basic metadata about a file."""
        full_path = self._resolve_path(path)
        if isinstance(full_path, str):
            return full_path

        if not full_path.exists():
            return f"Error: File not found: {path}"

        stat = full_path.stat()
        info = {
            "path": str(full_path.relative_to(self.workspace)),
            "type": "directory" if full_path.is_dir() else "file",
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "modified_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
        return json.dumps(info, indent=2)

    def create_directory(self, path: str) -> str:
        """Create a directory."""
        full_path = self._resolve_path(path)
        if isinstance(full_path, str):
            return full_path

        full_path.mkdir(parents=True, exist_ok=True)
        return f"Created directory: {path}"

    def delete_file(self, path: str) -> ToolResult:
        """Delete a file if it exists."""
        full_path = self._resolve_path(path)
        if isinstance(full_path, str):
            return ToolResult("delete_file", full_path)

        if not full_path.exists():
            return ToolResult("delete_file", f"Error: File not found: {path}")
        if full_path.is_dir():
            return ToolResult("delete_file", f"Error: {path} is a directory; delete_file only handles files")

        previous = full_path.read_text(encoding="utf-8")
        full_path.unlink()
        metadata = {"path": str(Path(path)), "previous_content": previous}
        return ToolResult("delete_file", f"Deleted file: {path}", metadata)

    def rename_file(self, old_path: str, new_path: str) -> ToolResult:
        """Rename or move a file inside the workspace."""
        source = self._resolve_path(old_path)
        target = self._resolve_path(new_path)
        if isinstance(source, str):
            return ToolResult("rename_file", source)
        if isinstance(target, str):
            return ToolResult("rename_file", target)

        if not source.exists():
            return ToolResult("rename_file", f"Error: File not found: {old_path}")

        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        metadata = {"path": str(Path(new_path)), "previous_path": str(Path(old_path))}
        return ToolResult("rename_file", f"Renamed {old_path} to {new_path}", metadata)

    def run_command(self, command: str, cwd: str | None = None) -> ToolResult:
        """Run a shell command within the workspace using sandboxed policies."""
        work_dir = self._resolve_path(cwd) if cwd else self.workspace
        if isinstance(work_dir, str):
            return ToolResult("run_command", work_dir)

        sandboxed = apply_command_sandbox(command)
        if isinstance(sandboxed, str):
            return ToolResult("run_command", sandboxed)

        result = subprocess.run(
            sandboxed.argv,
            shell=sandboxed.shell,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=sandboxed.timeout,
        )
        output = (result.stdout or "") + (result.stderr or "")
        truncated = self._truncate_output(output or f"Command exited with code {result.returncode} (no output)")
        return ToolResult("run_command", truncated)

    def run_python(self, code: str) -> ToolResult:
        """Execute Python code in a subprocess."""
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = (result.stdout or "") + (result.stderr or "")
        truncated = self._truncate_output(output or f"Python exited with code {result.returncode} (no output)")
        return ToolResult("run_python", truncated)

    def _ensure_file(self, path: str) -> Path | str:
        full_path = self._resolve_path(path)
        if isinstance(full_path, str):
            return full_path
        if not full_path.exists():
            return f"Error: File not found: {path}"
        if not full_path.is_file():
            return f"Error: Not a file: {path}"
        return full_path

    def _resolve_path(self, path: str | None) -> Path | str:
        """Resolve a path relative to the workspace and enforce boundaries."""
        if path is None:
            return self.workspace

        candidate = Path(path)
        candidate = candidate if candidate.is_absolute() else (self.workspace / candidate)
        resolved = candidate.resolve()

        if not any(self._is_subpath(resolved, root) for root in self.allowed_roots):
            return "Error: Access outside of workspace is not allowed"

        if self._is_sensitive_path(resolved):
            return "Error: Access to sensitive files is blocked"

        return resolved

    def _truncate_output(self, text: str) -> str:
        max_allowed = MAX_OUTPUT_LENGTH
        if self.output_budget is not None:
            max_allowed = min(max_allowed, max(self.output_budget, 0))
        if max_allowed <= 0:
            return "[output suppressed: token budget exhausted]"

        truncated = text
        if len(truncated) > max_allowed:
            truncated = truncated[:max_allowed] + "\n\n[truncated]"

        self._consume_output_budget(len(truncated))
        return truncated

    def _build_change_metadata(
        self,
        path: str,
        previous_content: str | None,
        new_content: str,
        *,
        previous_path: str | None = None,
    ) -> dict[str, Any]:
        """Generate metadata including a unified diff for UI display."""

        import difflib

        before = (previous_content or "").splitlines()
        after = new_content.splitlines()
        diff_lines = difflib.unified_diff(
            before,
            after,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
        diff_text = "\n".join(diff_lines)
        metadata: dict[str, Any] = {
            "path": str(Path(path)),
            "diff": diff_text,
            "previous_content": previous_content,
            "new_content": new_content,
        }
        if previous_path:
            metadata["previous_path"] = previous_path
        return metadata

    def undo_change(self, metadata: dict[str, Any]) -> ToolResult:
        """Restore a file to its previous contents when available."""

        path = metadata.get("path")
        if not path:
            return ToolResult("undo", "Error: No path provided for undo")

        previous_content = metadata.get("previous_content")
        if previous_content is None:
            return ToolResult("undo", "Error: No previous content available to restore")

        full_path = self._resolve_path(path)
        if isinstance(full_path, str):
            return ToolResult("undo", full_path)

        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(str(previous_content), encoding="utf-8")
        return ToolResult("undo", f"Restored {path}")

    def get_history(self) -> list[dict[str, Any]]:
        """Return the tool invocation history as a list for downstream consumers."""

        return list(self.call_history)

    def _consume_output_budget(self, length: int) -> None:
        if self.output_budget is None:
            return
        self.output_budget = max(self.output_budget - length, 0)

    def _is_subpath(self, path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    def _is_sensitive_path(self, path: Path) -> bool:
        parts = {part.lower() for part in path.parts}
        if any(sensitive_part.lower() in parts for sensitive_part in SENSITIVE_DIR_PARTS):
            return True

        filename = path.name.lower()
        return filename in {name.lower() for name in SENSITIVE_FILENAMES}

    def _check_rate_limit(self) -> str | None:
        if not self.max_calls_per_minute:
            return None

        self._prune_timestamps()
        if len(self.call_timestamps) >= self.max_calls_per_minute:
            return "Error: Tool rate limit exceeded; please wait before sending more tool calls."

        return None

    def _register_call_timestamp(self) -> None:
        if self.max_calls_per_minute:
            self.call_timestamps.append(datetime.utcnow())

    def _prune_timestamps(self) -> None:
        cutoff = datetime.utcnow() - timedelta(minutes=1)
        while self.call_timestamps and self.call_timestamps[0] < cutoff:
            self.call_timestamps.popleft()

    def _record_history(self, tool_name: str, args: Dict[str, Any], result: ToolResult | None) -> None:
        sanitized_args = self._sanitize_args(args)

        entry = {
            "tool": tool_name,
            "args": sanitized_args,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "ok" if result and not str(result.output).startswith("Error") else "error",
        }
        if result:
            entry["output_preview"] = str(result.output)[:200]
        self.call_history.append(entry)

        self._log_if_error(tool_name, sanitized_args, result)

    def _validate_required_args(
        self, tool: Callable[..., Any], args: Dict[str, Any]
    ) -> tuple[str | None, list[str]]:
        """Ensure required parameters are provided before invoking a tool."""

        signature = inspect.signature(tool)
        missing: list[str] = []
        for name, param in signature.parameters.items():
            if param.kind in {param.VAR_POSITIONAL, param.VAR_KEYWORD}:
                continue
            if param.default is param.empty and (
                name not in args or args.get(name) is None
            ):
                missing.append(name)

        if missing:
            joined = ", ".join(missing)
            return (
                f"Error: Missing required parameter(s) for {tool.__name__}: {joined}",
                missing,
            )

        return None, []

    def _sanitize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        sanitized_args: Dict[str, Any] = {}
        for key, value in args.items():
            if isinstance(value, str) and len(value) > 200:
                sanitized_args[key] = value[:200] + "..."
            else:
                sanitized_args[key] = value
        return sanitized_args

    def _log_if_error(self, tool_name: str, args: Dict[str, Any], result: ToolResult | None) -> None:
        if not result:
            return

        output_text = str(result.output)
        if not output_text.startswith("Error"):
            return

        logging.error("Tool %s failed with args=%s: %s", tool_name, args, output_text)
