"""Interactive playground and walkthrough dialogs for Ghostline."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class EditorPlaygroundDialog(QDialog):
    """Show markdown help and editable live examples side-by-side."""

    def __init__(self, open_file_callback: Callable[[str], None] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editor Playground")
        self.setModal(False)
        self._open_file_callback = open_file_callback
        self._scratch_files: list[Path] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_markdown_help(), "Markdown Help")
        tabs.addTab(self._build_examples_tab(), "Live Examples")
        layout.addWidget(tabs)

    def _build_markdown_help(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        help_text = QPlainTextEdit(widget)
        help_text.setReadOnly(True)
        help_text.setPlainText(
            """
# Ghostline Editor Playground

Experiment with Markdown and editor behaviours. The help below is live—copy a block and paste it into a file to see syntax highlighting and previews.

## Markdown cheatsheet
- Headings: `#`, `##`, `###`
- Lists: `- item` or `1. item`
- Code fences: ```python ... ``` with language hints
- Links: `[Ghostline Docs](https://github.com/ghostline-studio/Ghostline-Studio#readme)`
- Tables: use `|` separators and `---` for headers

## Tips
- Use the Live Examples tab to tweak runnable snippets.
- Copy snippets into a new editor tab to interact with LSP and AI.
- Toggle word wrap from the View menu to match your editing style.
"""
        )

        layout.addWidget(help_text)
        return widget

    def _build_examples_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Live, editable snippets you can copy into the editor:"))

        for title, code, suffix in (
            (
                "Python quickstart",
                """def greet(name: str) -> str:\n    return f"Hello, {name}!"\n\nif __name__ == "__main__":\n    print(greet("Ghostline"))\n""",
                ".py",
            ),
            (
                "Markdown preview",
                """# Welcome to Ghostline\n\n- ✅ Tasks panel tracks builds and tests\n- 🧭 Navigation assistant helps jump to symbols\n- 🧪 Try inline code: `print('hi')`\n\n[Visit the docs](https://github.com/ghostline-studio/Ghostline-Studio#readme)\n""",
                ".md",
            ),
            (
                "JSON settings seed",
                """{\n  "ghostline": {\n    "theme": "ghost_dark",\n    "autosave": true\n  },\n  "project": {\n    "lint": "ruff",\n    "tests": "pytest"\n  }\n}\n""",
                ".json",
            ),
        ):
            layout.addWidget(self._build_example_block(title, code, suffix))

        layout.addStretch(1)
        return widget

    def _build_example_block(self, title: str, code: str, suffix: str) -> QWidget:
        container = QWidget(self)
        block_layout = QVBoxLayout(container)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(6)

        block_layout.addWidget(QLabel(title))
        editor = QPlainTextEdit(container)
        editor.setPlainText(code)
        block_layout.addWidget(editor)

        if self._open_file_callback:
            open_btn = QPushButton("Open in editor", container)
            open_btn.clicked.connect(lambda _=None, ed=editor, suf=suffix: self._export_example(ed.toPlainText(), suf))
            block_layout.addWidget(open_btn, alignment=Qt.AlignLeft)

        return container

    def _export_example(self, text: str, suffix: str) -> None:
        scratch = Path(tempfile.mkstemp(prefix="ghostline_playground_", suffix=suffix)[1])
        scratch.write_text(text, encoding="utf-8")
        self._scratch_files.append(scratch)
        if self._open_file_callback:
            self._open_file_callback(str(scratch))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        for path in self._scratch_files:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        self._scratch_files.clear()
        super().closeEvent(event)


class WalkthroughDialog(QDialog):
    """Step-by-step walkthrough with deep links to the documentation."""

    def __init__(self, docs_url: QUrl, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ghostline Walkthrough")
        self.setModal(False)
        self._docs_url = docs_url

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        intro = QLabel(
            "Follow the guided steps below to explore Ghostline Studio. Each step links to the docs for more detail.",
            self,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        steps = (
            ("1. Open a workspace", "Use File → Open Folder to select your project."),
            ("2. Run a command", "Press Ctrl+Shift+P to launch the Command Palette."),
            ("3. Chat with Ghostline AI", "Open the AI dock and ask for a code explanation."),
            ("4. Inspect diagnostics", "Use the Problems tab to jump to issues."),
            ("5. Explore terminals", "Create a new terminal session for quick tasks."),
        )

        for title, detail in steps:
            label = QLabel(f"<b>{title}</b><br/>{detail}")
            label.setWordWrap(True)
            layout.addWidget(label)

        docs_link = QPushButton("Open Documentation", self)
        docs_link.clicked.connect(lambda: QDesktopServices.openUrl(self._docs_url))
        layout.addWidget(docs_link, alignment=Qt.AlignLeft)

        self.setMinimumWidth(420)
