"""Provider-agnostic tool execution layer.

Implements the tool behaviours described in ``AGENTIC.md`` with workspace-aware
path resolution, safe defaults, and output truncation to keep responses within
provider token budgets.
"""
from __future__ import annotations

import json
from datetime import datetime
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

from .sandbox import apply_command_sandbox


MAX_OUTPUT_LENGTH = 4000


@dataclass
class ToolResult:
    name: str
    output: str
    metadata: dict[str, Any] | None = None


class ToolExecutor:
    """Execute tools requested by AI agents."""

    def __init__(self, workspace_root: Path | str):
        workspace = Path(workspace_root).resolve()
        self.workspace = workspace
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
            return ToolResult(tool_name, f"Error: Unknown tool '{tool_name}'")

        try:
            output = self.allowed_tools[tool_name](**args)
            if isinstance(output, ToolResult):
                return output
            return ToolResult(tool_name, str(output))
        except Exception as exc:  # pragma: no cover - defensive catch
            return ToolResult(tool_name, f"Error executing {tool_name}: {exc}")

    def read_file(self, path: str) -> str:
        """Read file contents with truncation."""
        full_path = self._ensure_file(path)
        if isinstance(full_path, str):
            return full_path

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
        """Run a shell command within the workspace."""
        work_dir = self._resolve_path(cwd) if cwd else self.workspace
        if isinstance(work_dir, str):
            return ToolResult("run_command", work_dir)

        safe_command = apply_command_sandbox(command)
        result = subprocess.run(
            safe_command,
            shell=True,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=60,
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

        try:
            resolved.relative_to(self.workspace)
        except ValueError:
            return "Error: Access outside of workspace is not allowed"

        return resolved

    def _truncate_output(self, text: str) -> str:
        if len(text) <= MAX_OUTPUT_LENGTH:
            return text
        return text[:MAX_OUTPUT_LENGTH] + "\n\n[truncated]"

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
