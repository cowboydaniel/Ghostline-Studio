from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class SearchHit:
    path: Path
    line: int
    text: str


class RipgrepScanner:
    def __init__(self) -> None:
        self._has_rg = shutil.which("rg") is not None

    def search(self, root: Path, query: str) -> list[SearchHit]:
        if self._has_rg:
            return self._search_with_ripgrep(root, query)
        return self._python_search(root, query)

    def _search_with_ripgrep(self, root: Path, query: str) -> list[SearchHit]:
        try:
            completed = subprocess.run(
                ["rg", "--vimgrep", "--no-heading", "--color", "never", query, str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return []

        output = completed.stdout if completed.returncode in {0, 1} else ""
        hits: list[SearchHit] = []
        for line in output.splitlines():
            parts = line.split(":", 3)
            if len(parts) < 4:
                continue
            path, line_no, _col, text = parts
            try:
                hits.append(SearchHit(Path(path), int(line_no), text))
            except ValueError:
                continue
        return hits

    def _python_search(self, root: Path, query: str) -> list[SearchHit]:
        hits: list[SearchHit] = []
        if not query:
            return hits
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        for file_path in root.rglob("*"):
            if file_path.is_dir():
                continue
            try:
                for idx, line in enumerate(file_path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                    if pattern.search(line):
                        hits.append(SearchHit(file_path, idx, line.strip()))
            except OSError:
                continue
        return hits


class SearchPanel(QDockWidget):
    """Dockable Find/Replace in Files panel with ripgrep fallback."""

    def __init__(
        self,
        workspace_provider: Callable[[], str | None],
        open_callback: Callable[[str, int], None],
        parent=None,
    ) -> None:
        super().__init__("Search", parent)
        self.workspace_provider = workspace_provider
        self.open_callback = open_callback
        self._scanner = RipgrepScanner()
        self._hits: list[SearchHit] = []

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        input_row = QHBoxLayout()
        self.query_input = QLineEdit(self)
        self.query_input.setPlaceholderText("Find in files…")
        self.query_input.returnPressed.connect(self._run_search)
        input_row.addWidget(self.query_input)

        self.replace_input = QLineEdit(self)
        self.replace_input.setPlaceholderText("Replace with…")
        input_row.addWidget(self.replace_input)

        self.search_button = QPushButton("Find", self)
        self.search_button.clicked.connect(self._run_search)
        input_row.addWidget(self.search_button)

        self.replace_button = QPushButton("Replace All", self)
        self.replace_button.clicked.connect(self._replace_all)
        input_row.addWidget(self.replace_button)

        layout.addLayout(input_row)

        self.results = QListWidget(self)
        self.results.itemActivated.connect(self._open_hit)
        layout.addWidget(self.results, 1)

        self.status_label = QLabel("", self)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.status_label)

        container.setLayout(layout)
        self.setWidget(container)

    def open_with_query(self, query: str) -> None:
        self.query_input.setText(query)
        self._run_search()

    def _workspace_root(self) -> Path | None:
        root = self.workspace_provider()
        return Path(root) if root else None

    def _run_search(self) -> None:
        root = self._workspace_root()
        if not root:
            QMessageBox.information(self, "Search", "Open a workspace to search through files.")
            return
        query = self.query_input.text().strip()
        self.results.clear()
        if not query:
            self.status_label.setText("Enter text to search")
            return
        self._hits = self._scanner.search(root, query)
        for hit in self._hits:
            item = QListWidgetItem(f"{hit.path.relative_to(root)}:{hit.line} — {hit.text}")
            item.setData(Qt.ItemDataRole.UserRole, hit)
            self.results.addItem(item)
        if self._hits:
            self.status_label.setText(f"{len(self._hits)} result(s)")
        else:
            self.status_label.setText("No results")

    def _replace_all(self) -> None:
        root = self._workspace_root()
        if not root:
            return
        find_text = self.query_input.text()
        replace_text = self.replace_input.text()
        if not find_text:
            return

        replaced_files = 0
        for hit in self._group_hits_by_file(self._hits):
            try:
                text = hit.read_text(encoding="utf-8")
            except OSError:
                continue
            new_text = text.replace(find_text, replace_text)
            if new_text != text:
                replaced_files += 1
                hit.write_text(new_text, encoding="utf-8")
        self.status_label.setText(f"Replaced in {replaced_files} file(s)")
        self._run_search()

    def _group_hits_by_file(self, hits: Iterable[SearchHit]) -> set[Path]:
        return {hit.path for hit in hits}

    def _open_hit(self, item: QListWidgetItem) -> None:
        hit: SearchHit | None = item.data(Qt.ItemDataRole.UserRole)
        if hit:
            self.open_callback(str(hit.path), hit.line - 1)
