"""AI command helpers."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from ghostline.ai.ai_client import AIClient
from ghostline.ai.refactor_pipeline import RefactorRequest, RefactorPipeline, run_code_action
from ghostline.editor.code_editor import CodeEditor


def explain_selection(editor: CodeEditor, client: AIClient) -> None:
    cursor = editor.textCursor()
    text = cursor.selectedText() or editor.toPlainText()
    response = client.send(f"Explain the following code:\n{text}")
    QMessageBox.information(editor, "AI Explain", response.text)


def refactor_selection(editor: CodeEditor, client: AIClient) -> None:
    pipeline = RefactorPipeline(client)
    request = RefactorRequest(action="improve_readability", prompt_hint="Refactor this selection")
    pipeline.run(editor, request)


def ai_code_actions(editor: CodeEditor, client: AIClient) -> None:
    if not editor:
        return
    pipeline = RefactorPipeline(client)
    actions = {
        "Improve readability": "improve_readability",
        "Optimize imports": "optimize_imports",
        "Convert to dataclass": "convert_to_dataclass",
        "Generate missing tests": "generate_tests",
    }
    # Default to readability if no selection dialog is available.
    action_key = next(iter(actions.values()))
    run_code_action(editor, client, action_key, "AI Code Action")

