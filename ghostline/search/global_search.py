"""Workspace-wide text search."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Callable

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


@dataclass
class GlobalSearchResult:
    path: Path
    line: int
    content: str


def search_workspace(root: str, query: str) -> List[GlobalSearchResult]:
    results: List[GlobalSearchResult] = []
    if not query:
        return results
    root_path = Path(root)
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    for file in root_path.rglob("*"):
        if file.is_dir():
            continue
        try:
            for idx, line in enumerate(file.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                if pattern.search(line):
                    results.append(GlobalSearchResult(file, idx, line.strip()))
        except OSError:
            continue
    return results


class GlobalSearchDialog(QDialog):
    def __init__(self, workspace_root: Callable[[], str | None], open_callback: Callable[[str, int], None], parent=None) -> None:
        super().__init__(parent)
        self.workspace_root = workspace_root
        self.open_callback = open_callback
        self.setWindowTitle("Global Search")

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Find in workspace...")
        self.button = QPushButton("Search", self)
        self.button.clicked.connect(self._perform_search)
        self.input.returnPressed.connect(self._perform_search)

        self.results = QListWidget(self)
        self.results.itemActivated.connect(self._open_result)

        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(self.button)

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.results)

    def _perform_search(self) -> None:
        root = self.workspace_root()
        if not root:
            return
        self.results.clear()
        for result in search_workspace(root, self.input.text()):
            item = QListWidgetItem(f"{result.path.relative_to(root)}:{result.line}  {result.content}")
            item.setData(256, result)
            self.results.addItem(item)

    def _open_result(self, item: QListWidgetItem) -> None:
        result: GlobalSearchResult | None = item.data(256)
        if result:
            self.open_callback(str(result.path), result.line - 1)
            self.close()
