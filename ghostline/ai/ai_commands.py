"""AI command helpers."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from ghostline.ai.ai_client import AIClient
from ghostline.editor.code_editor import CodeEditor


def explain_selection(editor: CodeEditor, client: AIClient) -> None:
    cursor = editor.textCursor()
    text = cursor.selectedText() or editor.toPlainText()
    response = client.send(f"Explain the following code:\n{text}")
    QMessageBox.information(editor, "AI Explain", response.text)


def refactor_selection(editor: CodeEditor, client: AIClient) -> None:
    cursor = editor.textCursor()
    text = cursor.selectedText() or editor.toPlainText()
    response = client.send(f"Suggest a refactor for this code:\n{text}")
    QMessageBox.information(editor, "AI Refactor", response.text)

