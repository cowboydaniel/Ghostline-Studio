"""Structured AI-driven refactor pipeline."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Iterable

from ghostline.ai.ai_client import AIClient
from ghostline.editor.code_editor import CodeEditor


@dataclass
class RefactorRequest:
    """Describe a refactor request coming from the UI."""

    action: str
    prompt_hint: str


class PatchApplicationError(RuntimeError):
    """Raised when an AI patch cannot be applied cleanly."""


class UnifiedDiffApplier:
    """Minimal unified diff applier used by the refactor pipeline."""

    def apply(self, original_text: str, patch: str) -> str:
        if not patch.strip():
            return original_text
        lines = original_text.splitlines(keepends=True)
        cursor = 0
        new_lines: list[str] = []
        target_line = 0
        for raw in patch.splitlines():
            if raw.startswith("---") or raw.startswith("+++"):
                continue
            if raw.startswith("@@"):
                match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
                if not match:
                    raise PatchApplicationError(f"Invalid hunk header: {raw}")
                target_line = int(match.group(1)) - 1
                if target_line < cursor:
                    raise PatchApplicationError("Patch overlaps previous hunks")
                new_lines.extend(lines[cursor:target_line])
                cursor = target_line
                continue
            if raw.startswith("+"):
                new_lines.append(raw[1:] + ("\n" if not raw.endswith("\n") else ""))
                continue
            if raw.startswith("-"):
                if cursor >= len(lines):
                    raise PatchApplicationError("Patch exceeds file length")
                cursor += 1
                continue
            if cursor < len(lines):
                new_lines.append(lines[cursor])
                cursor += 1
            else:
                raise PatchApplicationError("Unexpected context past file end")
        new_lines.extend(lines[cursor:])
        return "".join(new_lines)


class RefactorPipeline:
    """Run AI-driven code actions as a single undoable operation."""

    def __init__(
        self,
        client: AIClient,
        applier: UnifiedDiffApplier | None = None,
        test_selector: Callable[[str], list[str]] | None = None,
    ) -> None:
        self.client = client
        self.applier = applier or UnifiedDiffApplier()
        self.test_selector = test_selector
        self._actions: dict[str, Callable[[str], str]] = {
            "improve_readability": lambda code: f"Improve readability of this code and return a unified diff:\n{code}",
            "optimize_imports": lambda code: f"Optimize imports for this file and return a unified diff:\n{code}",
            "convert_to_dataclass": lambda code: f"Convert any plain classes to dataclasses when appropriate. Respond with unified diff.\n{code}",
            "generate_tests": lambda code: f"Generate missing tests for the following code. Respond with unified diff patch creating tests if needed.\n{code}",
        }

    def available_actions(self) -> Iterable[str]:
        return self._actions.keys()

    def run(self, editor: CodeEditor, request: RefactorRequest) -> str:
        context = self._collect_context(editor)
        prompt = self._construct_prompt(request, context)
        streamed = self._stream_response(prompt)
        patched_text = self._parse_and_apply(editor, streamed)
        self._update_editor(editor, patched_text)
        return patched_text

    def _collect_context(self, editor: CodeEditor) -> str:
        cursor = editor.textCursor()
        if cursor.hasSelection():
            return cursor.selectedText()
        return editor.toPlainText()

    def _construct_prompt(self, request: RefactorRequest, context: str) -> str:
        if request.action in self._actions:
            return self._actions[request.action](context)
        return f"{request.prompt_hint}\nReturn a unified diff for the provided code.\n{context}"

    def _stream_response(self, prompt: str) -> str:
        chunks = []
        for part in self.client.stream(prompt):
            chunks.append(part)
        return "".join(chunks)

    def _parse_and_apply(self, editor: CodeEditor, response: str) -> str:
        patch = response if "@@" in response or response.startswith("diff") else response
        before = editor.toPlainText()
        patched = self.applier.apply(before, patch)
        return patched

    def _update_editor(self, editor: CodeEditor, new_text: str) -> None:
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        editor.setPlainText(new_text)
        cursor.endEditBlock()

    def suggest_tests(self, file_path: str) -> list[str]:
        if self.test_selector:
            return self.test_selector(file_path)
        return []


def run_code_action(editor: CodeEditor, client: AIClient, action: str, hint: str = "") -> str:
    """Convenience wrapper used by menus and shortcuts."""

    pipeline = RefactorPipeline(client)
    request = RefactorRequest(action=action, prompt_hint=hint or action)
    return pipeline.run(editor, request)
